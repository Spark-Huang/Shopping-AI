
"""
Main FastAPI application for the Shopping AI API.

This module provides the main API endpoints for the shopping assistant,
including query processing and streaming responses.
"""
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field as PydanticField
from typing import Optional, Dict
from pathlib import Path
import logging
import os
import sys
import time
import json

import requests

from .auth import require_user
from .agents.state import Cart, State
from .agents.planner import PlannerAgent
from .agents.retrieval_proxy import RetrieverAgent
from .agents.cart import CartAgent
from .agents.chatter import ChatterAgent
from .agents.summarizer import SummaryAgent
from .agents.session_titles import maybe_generate_session_title
from .graph import create_graph
from .settings import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)
TIMING_LOG = Path(
    os.getenv(
        "QUERY_TIMING_LOG",
        Path(__file__).resolve().parents[2] / ".local-run" / "query-timings.jsonl",
    )
)


def initialize_agents(config) -> Dict:
    """Initialize all agent instances."""
    return {
        'planner_agent': PlannerAgent(config=config),
        'retriever_agent': RetrieverAgent(config=config),
        'cart_agent': CartAgent(config=config),
        'chatter_agent': ChatterAgent(config=config),
        'summary_agent': SummaryAgent(config=config)
    }


# Load configuration and initialize agents
try:
    config = load_config()  # Load and validate configuration
    agents = initialize_agents(config)
    graph = create_graph(
        **agents,
        config=config
    )
except Exception as e:
    logger.error(f"Failed to initialize application: {e}")
    raise

# Initialize FastAPI app
app = FastAPI(
    title="Shopping AI API",
    description="AI-powered shopping assistant with multi-service architecture",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class QueryRequest(BaseModel):
    """Request model for shopping queries."""
    user_id: int
    query: str
    image: str = ""
    context: Optional[str] = ""
    cart: Optional[Cart] = None
    retrieved: Optional[Dict[str, str]] = {}
    safety_enabled: Optional[bool] = PydanticField(default=True, alias="safety")
    image_bool: bool = False
    language: Optional[str] = ""
    session_id: Optional[int] = None


class QueryResponse(BaseModel):
    """Response model for shopping queries."""
    response: str
    images: Dict[str, str] = {}
    timings: Dict[str, float] = {}
    timings_ms: Dict[str, float] = {}


def _persist_timings(
    user_id: int,
    query: str,
    timings: Dict[str, float],
    timings_ms: Dict[str, float],
) -> None:
    if not timings:
        return
    try:
        TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": time.time(),
            "user_id": user_id,
            "query": query,
            "timings_s": timings,
            "timings_ms": timings_ms,
        }
        with TIMING_LOG.open("a", encoding="utf-8") as timing_file:
            timing_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning(f"orchestrator | could not persist query timing: {exc}")


def create_initial_state(
    request: QueryRequest, authorization: Optional[str] = None
) -> State:
    """Create initial state from request."""
    return State(
        user_id=request.user_id,
        authorization=authorization,
        session_id=request.session_id,
        query=request.query,
        image=request.image,
        context=request.context or "",
        cart=request.cart or Cart(),
        safety_enabled=request.safety_enabled,
        language=request.language or "",
    )

def _proxy_auth(
    method: str, path: str, body: Optional[Dict], authorization: Optional[str] = None
) -> Dict:
    """Forward an auth request to the memory service and relay its answer.

    Auth failures (401/409/422) are forwarded verbatim so the web UI can
    react to wrong credentials or taken usernames.
    """
    headers = {}
    if authorization:
        headers["Authorization"] = authorization
    url = f"{config.memory_base_url}{path}"
    try:
        if method == "get":
            response = requests.get(url, headers=headers, timeout=10)
        else:
            response = requests.post(url, json=body, headers=headers, timeout=10)
        if response.status_code in (401, 409, 422):
            try:
                detail = response.json().get("detail", "Authentication failed")
            except ValueError:
                detail = "Authentication failed"
            raise HTTPException(status_code=response.status_code, detail=detail)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"orchestrator | {method} {path} | memory service call failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to reach memory service")


@app.post("/auth/register")
def auth_register(request: Dict):
    """Create an account via the memory service and return a JWT."""
    return _proxy_auth("post", "/auth/register", request)


@app.post("/auth/login")
def auth_login(request: Dict):
    """Verify credentials via the memory service and return a JWT."""
    return _proxy_auth("post", "/auth/login", request)


@app.get("/auth/me")
def auth_me(authorization: Optional[str] = Header(default=None)):
    """Introspect the bearer token via the memory service."""
    return _proxy_auth("get", "/auth/me", None, authorization)


@app.post("/query/stream")
async def process_query_stream(
    request: QueryRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    Stream responses to user queries in real-time.
    
    This endpoint provides streaming responses for responsive UIs
    and chat-like experiences.
    """
    require_user(request.user_id, authorization)
    try:
        logger.info(f"orchestrator | /query/stream | Processing streaming query for user {request.user_id}: {request.query}")
        
        # Handle image-only queries
        if request.image and not request.query:
            request.query = "The user has submitted an image, and is looking for items from the catalog that appear similar."
        
        # Create initial state
        state = create_initial_state(request, authorization)
        
        async def send_updates():
            """Generator function for streaming updates."""
            try:
                async for chunk in graph.astream(state, stream_mode="custom"):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Error in streaming: {e}")
                yield f"data: {json.dumps({'type': 'error', 'payload': str(e)})}\n\n"

        return StreamingResponse(send_updates(), media_type="text/event-stream")
        
    except Exception as e:
        logger.error(f"Error processing streaming query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/title")
async def generate_session_title(request: QueryRequest, authorization: Optional[str] = Header(default=None)):
    """Generate a session title without blocking the streamed conversation."""
    require_user(request.user_id, authorization)
    scheduled = maybe_generate_session_title(
        agents["summary_agent"], create_initial_state(request, authorization)
    )
    return {"scheduled": scheduled}

@app.post("/query/timing", response_model=QueryResponse)
async def process_query_timing(
    request: QueryRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    Process a query and return detailed timing information.

    This endpoint is useful for performance analysis and debugging.
    """
    require_user(request.user_id, authorization)
    try:
        logger.info(f"orchestrator | /query/timing | Processing timing query for user {request.user_id}: {request.query}")
        
        # Create initial state
        state = create_initial_state(request, authorization)
        
        # Process query and collect timing data
        start_time_ns = time.perf_counter_ns()
        out_state_dict = await graph.ainvoke(state)
        elapsed_ns = max(time.perf_counter_ns() - start_time_ns, 1)
        
        logger.info(
            "orchestrator | /query/timing | timings "
            f"(seconds): {out_state_dict['timings']}"
        )

        total_time = elapsed_ns / 1_000_000_000
        timings = {**out_state_dict["timings"], "total": total_time}
        timings_ms = {
            key: round(value * 1000, 3) for key, value in timings.items()
        }
        _persist_timings(request.user_id, request.query, timings, timings_ms)

        # Create response with timing information
        response = QueryResponse(
            response=out_state_dict["response"],
            images={},
            timings=timings,
            timings_ms=timings_ms,
        )

        logger.info(f"orchestrator | /query | Successfully processed timing query in {total_time:.2f}s")
        return response

    except Exception as e:
        logger.error(f"Error processing timing query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
@app.get("/sessions/{user_id}")
def session_list(user_id: int, authorization: Optional[str] = Header(default=None)):
    """Read-only proxy for a user's chat sessions."""
    require_user(user_id, authorization)
    memory_url = f"{config.memory_base_url}/user/{user_id}/sessions"
    try:
        response = requests.get(
            memory_url, headers={"Authorization": authorization}, timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("orchestrator | /sessions/%s | memory service call failed: %s", user_id, exc)
        raise HTTPException(status_code=502, detail="Failed to fetch sessions")


@app.post("/sessions/{user_id}")
def session_create(user_id: int, request: Dict, authorization: Optional[str] = Header(default=None)):
    require_user(user_id, authorization)
    try:
        response = requests.post(
            f"{config.memory_base_url}/user/{user_id}/sessions",
            json=request,
            headers={"Authorization": authorization},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("orchestrator | POST /sessions/%s failed: %s", user_id, exc)
        raise HTTPException(status_code=502, detail="Failed to create session")


@app.get("/sessions/{user_id}/{session_id}/messages")
def session_messages(user_id: int, session_id: int, authorization: Optional[str] = Header(default=None)):
    require_user(user_id, authorization)
    try:
        response = requests.get(
            f"{config.memory_base_url}/user/{user_id}/sessions/{session_id}/messages",
            headers={"Authorization": authorization},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("orchestrator | session messages read failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch session messages")


@app.delete("/sessions/{user_id}/{session_id}")
def session_delete(user_id: int, session_id: int, authorization: Optional[str] = Header(default=None)):
    require_user(user_id, authorization)
    try:
        response = requests.delete(
            f"{config.memory_base_url}/user/{user_id}/sessions/{session_id}",
            headers={"Authorization": authorization},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("orchestrator | session delete failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to delete session")


@app.get("/cart/{user_id}")
def get_cart(user_id: int, authorization: Optional[str] = Header(default=None)):
    """
    Read-only proxy to the memory service's cart endpoint.
    """
    require_user(user_id, authorization)
    memory_url = f"{config.memory_base_url}/user/{user_id}/cart"
    try:
        response = requests.get(
            memory_url, headers={"Authorization": authorization}, timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"orchestrator | /cart/{user_id} | memory service call failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch cart from memory service")


@app.post("/cart/{user_id}")
def add_cart_item(user_id: int, request: Dict, authorization: Optional[str] = Header(default=None)):
    """Persist a displayed product directly, bypassing the agent round trip."""
    require_user(user_id, authorization)
    try:
        response = requests.post(
            f"{config.memory_base_url}/user/{user_id}/cart/add",
            json={**request, "idempotent": True},
            headers={"Authorization": authorization},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"orchestrator | POST /cart/{user_id} | memory service call failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to add cart item")


@app.post("/cart/{user_id}/remove")
def remove_cart_item(user_id: int, request: Dict, authorization: Optional[str] = Header(default=None)):
    """Remove a displayed product after it has been marked as purchased."""
    require_user(user_id, authorization)
    try:
        response = requests.post(
            f"{config.memory_base_url}/user/{user_id}/cart/remove",
            json=request,
            headers={"Authorization": authorization},
            timeout=10,
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Item not in cart")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"orchestrator | POST /cart/{user_id}/remove | memory service call failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to remove cart item")


@app.get("/orders/{user_id}")
def get_orders(user_id: int, authorization: Optional[str] = Header(default=None)):
    """Read-only proxy to the memory service's manual-orders endpoint."""
    require_user(user_id, authorization)
    try:
        response = requests.get(
            f"{config.memory_base_url}/user/{user_id}/orders",
            headers={"Authorization": authorization},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"orchestrator | /orders/{user_id} | memory service call failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch orders from memory service")


@app.post("/orders/{user_id}")
def create_order(user_id: int, request: Dict, authorization: Optional[str] = Header(default=None)):
    """Proxy a manual mark-as-purchased action to memory service."""
    require_user(user_id, authorization)
    try:
        response = requests.post(
            f"{config.memory_base_url}/user/{user_id}/orders",
            json=request,
            headers={"Authorization": authorization},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"orchestrator | POST /orders/{user_id} | memory service call failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to create order in memory service")

@app.get("/context/{user_id}")
def get_context(user_id: int, authorization: Optional[str] = Header(default=None)):
    """
    Read-only proxy to the memory service's context endpoint.
    """
    require_user(user_id, authorization)
    memory_url = f"{config.memory_base_url}/user/{user_id}/context"
    try:
        response = requests.get(
            memory_url, headers={"Authorization": authorization}, timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"orchestrator | /context/{user_id} | memory service call failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch context from memory service")


@app.post("/context/{user_id}")
def add_context(user_id: int, request: Dict, authorization: Optional[str] = Header(default=None)):
    """Persist onboarding facts without requiring a full agent turn."""
    require_user(user_id, authorization)
    new_context = str(request.get("new_context", "")).strip()
    if not new_context:
        raise HTTPException(status_code=422, detail="new_context must not be empty")
    try:
        response = requests.post(
            f"{config.memory_base_url}/user/{user_id}/context/add",
            json={"new_context": new_context},
            headers={"Authorization": authorization},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"orchestrator | POST /context/{user_id} | memory service call failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to update context")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Shopping AI API",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/auth/{register,login,me}",
            "stream": "/query/stream",
            "timing": "/query/timing",
            "cart": "/cart/{user_id}",
            "orders": "/orders/{user_id}",
            "context": "/context/{user_id}",
            "health": "/health",
            "docs": "/docs"
        }
    }
