from fastapi import FastAPI
from pydantic import BaseModel
import logging
import time

from .engine import SafetyEngineFactory

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    user_id: int
    query: str


app = FastAPI()

engine = SafetyEngineFactory().create()


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
    }


@app.post("/safety/input", response_model=None)
async def check_input(request: QueryRequest):
    return await engine.call_input_safety(request.query)


@app.post("/safety/input/timing", response_model=None)
async def timing_input(request: QueryRequest):
    start = time.monotonic()
    response = await check_input(request)
    end = time.monotonic()
    logger.info("safety | check_input | time: %s", end - start)
    response["timings"] = [{"safety": end - start}, {"total": end - start}]
    return response


@app.post("/safety/output", response_model=None)
async def check_output(request: QueryRequest):
    return await engine.call_output_safety(request.query)


@app.post("/safety/output/timing", response_model=None)
async def timing_output(request: QueryRequest):
    start = time.monotonic()
    response = await check_output(request)
    end = time.monotonic()
    logger.info("safety | check_output | time: %s", end - start)
    response["timings"] = [{"safety": end - start}, {"total": end - start}]
    return response
