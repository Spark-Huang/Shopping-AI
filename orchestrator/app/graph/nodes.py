import json
import logging
import time

import requests
from langgraph.config import get_stream_writer

from ..agents.planner import PlannerAgent
from ..agents.state import SafetyResult, State
from ..agents.stream_buffer import StreamBuffer, detect_language
from .local_rules import _matches_local_unsafe_rules
from .routing import _format_monthly_order_summary

logger = logging.getLogger(__name__)
_config = None


class GraphNodes:
    _config = None

    @classmethod
    def configure(cls, config) -> None:
        cls._config = config


    """Container for graph node functions."""

    @staticmethod
    async def begin_buffered_stream(state: State) -> State:
        """Create the per-request buffer before chatter starts."""
        state.stream_buffer = StreamBuffer(writer=get_stream_writer())
        return state
    
    @staticmethod
    async def get_memory(state: State) -> State:
        """Retrieve user memory and cart from the memory service."""
        start = time.monotonic()
        logger.info(f"GraphNodes.get_memory() | Retrieving memory for user {state.user_id}")
        
        try:
            # Retrieve memory from the memory database
            memory_response = requests.get(
                f"{GraphNodes._config.memory_base_url}/user/{state.user_id}/context",
                headers={"Authorization": state.authorization},
                timeout=10
            )
            memory_response.raise_for_status()
            memory = memory_response.json()

            semantic_response = requests.get(
                f"{GraphNodes._config.memory_base_url}/user/{state.user_id}/memory",
                params={"query": state.query},
                headers={"Authorization": state.authorization},
                timeout=3,
            )
            semantic_response.raise_for_status()
            semantic_memory = semantic_response.json()
            
            # Retrieve cart from the memory database
            cart_response = requests.get(
                f"{GraphNodes._config.memory_base_url}/user/{state.user_id}/cart",
                headers={"Authorization": state.authorization},
                timeout=10
            )
            cart_response.raise_for_status()
            cart = cart_response.json()
            orders_response = requests.get(
                f"{GraphNodes._config.memory_base_url}/user/{state.user_id}/orders",
                headers={"Authorization": state.authorization},
                timeout=10
            )
            orders_response.raise_for_status()
            orders = orders_response.json()

            logger.info(
                f"GraphNodes.get_memory() | Memory retrieved: {memory}, "
                f"Cart: {cart}, Orders: {len(orders['orders'])}"
            )
            
            # Update state with retrieved data
            state.context = semantic_memory.get("context") or memory.get("context", "")
            state.cart.contents = cart["cart"]
            state.recent_orders.entries = orders["orders"]
            if PlannerAgent._is_spending_recall_query(state.query):
                state.response = _format_monthly_order_summary(state)
            
            end = time.monotonic()
            state.timings["memory"] = end - start
            
            return state
            
        except requests.RequestException as e:
            logger.error(f"GraphNodes.get_memory() | Failed to retrieve memory: {e}")
            # Return state with empty context/cart on failure
            state.context = ""
            state.cart.contents = []
            state.recent_orders.entries = []
            state.timings["memory"] = time.monotonic() - start
            return state
    
    @staticmethod
    async def check_input_safety(state: State) -> SafetyResult:
        """Check if the user input is safe using safety checks."""
        language = detect_language(state.query, state.language)
        if _matches_local_unsafe_rules(state.query):
            return {"is_safe": False, "language": language}
        if not state.safety_enabled:
            return {"is_safe": True, "language": language}
        
        start = time.monotonic()
        
        try:
            response = requests.post(
                f"{GraphNodes._config.safety_base_url}/safety/input",
                json={"user_id": state.user_id, "query": state.query},
                headers={"Authorization": state.authorization},
                timeout=10
            )
            response.raise_for_status()
            
            response_data = response.json()
            # Safety service returns {"response": [{"role": "assistant", "content": "..."}], ...}
            if "response" in response_data and len(response_data["response"]) > 0:
                is_safe = response_data["response"][0]["content"] == state.query
            else:
                is_safe = True  # Default to safe if structure is unexpected
            end = time.monotonic()
            
            return {
                "is_safe": is_safe,
                "language": language,
                "safety_timings": {"safety_input_check": end - start},
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to check input safety: {e}")
            # Fail-closed: when the safety service cannot be reached, only
            # queries that pass the local danger heuristics are allowed
            # through; anything matching them is blocked. This replaces the
            # previous unconditional fail-open default.
            is_safe = not _matches_local_unsafe_rules(state.query)
            if not is_safe:
                logger.warning(
                    "Input safety check unavailable; local rules flagged "
                    "query as unsafe: %r",
                    state.query,
                )
            else:
                logger.warning(
                    "Input safety check unavailable (fail-closed mode with "
                    "local rules); query passed local heuristics"
                )
            return {
                "is_safe": is_safe,
                "language": language,
                "safety_timings": {"safety_input_check": time.monotonic() - start},
            }
    
    @staticmethod
    async def check_output_safety(state: State) -> SafetyResult:
        """Check if the generated response is safe using safety checks."""
        language = detect_language(state.query, state.language)
        stream_buffer = state.stream_buffer
        if _matches_local_unsafe_rules(state.response or ""):
            if stream_buffer is not None:
                stream_buffer.discard()
            return {"is_safe": False, "language": language}
        if stream_buffer is None:
            return {"is_safe": False, "language": language}
        if not state.safety_enabled:
            stream_buffer.flush()
            return {"is_safe": True, "language": language}
        
        start = time.monotonic()
        
        try:
            response = requests.post(
                f"{GraphNodes._config.safety_base_url}/safety/output",
                json={"user_id": state.user_id, "query": state.response},
                headers={"Authorization": state.authorization},
                timeout=10
            )
            response.raise_for_status()
            
            response_data = response.json()
            # Safety service returns {"response": [{"role": "assistant", "content": "..."}], ...}
            if "response" in response_data and len(response_data["response"]) > 0:
                is_safe = response_data["response"][0]["content"] == state.response
            else:
                is_safe = True  # Default to safe if structure is unexpected
            end = time.monotonic()
            
            if is_safe:
                stream_buffer.flush()
            else:
                stream_buffer.discard()

            return {
                "is_safe": is_safe,
                "language": language,
                "safety_timings": {"safety_output_check": end - start},
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to check output safety: {e}")
            # Fail-closed: when the safety service cannot be reached, block
            # responses that match the local danger heuristics and let the
            # rest through with a logged warning. This replaces the previous
            # unconditional fail-open default.
            is_safe = not _matches_local_unsafe_rules(state.response or "")
            if not is_safe:
                logger.warning(
                    "Output safety check unavailable; local rules flagged "
                    "response as unsafe"
                )
            else:
                logger.warning(
                    "Output safety check unavailable (fail-closed mode with "
                    "local rules); response passed local heuristics"
                )
            if is_safe:
                stream_buffer.flush()
            else:
                stream_buffer.discard()
            return {
                "is_safe": is_safe,
                "language": language,
                "safety_timings": {"safety_output_check": time.monotonic() - start},
            }
    
    @staticmethod
    async def check_safety_node(safety: SafetyResult) -> State:
        """Process safety-check results and update state timings."""
        logger.info(f"GraphNodes.check_safety_node() |Safety check result: {safety}")
        return {"timings": safety.safety_timings}

    @staticmethod
    async def unsafe_output(safety: SafetyResult) -> State:
        """Handle unsafe content by returning a safe message."""
        language = safety.language or "en"
        unsafe_messages = getattr(GraphNodes._config, "unsafe_messages", None)
        if isinstance(unsafe_messages, dict):
            candidates = (
                unsafe_messages.get(language),
                unsafe_messages.get("en"),
                next(iter(unsafe_messages.values()), None),
            )
            unsafe_message = next(
                (message for message in candidates if message),
                getattr(GraphNodes._config, "unsafe_message", ""),
            )
        else:
            unsafe_message = getattr(GraphNodes._config, "unsafe_message", "")
        writer = get_stream_writer()
        writer(f"{json.dumps({'type': 'content', 'payload': unsafe_message, 'timestamp': time.time()})}")
        return {"response": unsafe_message}

    @staticmethod
    async def passthrough(state: State) -> State:
        """Preserve state while LangGraph waits for the input safety."""
        return state
