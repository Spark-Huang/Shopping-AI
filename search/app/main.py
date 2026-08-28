"""Search service API routes."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from search.app.embeddings.text import RetrieverConfig
from search.app.engine import Retriever
from search.app.freshness import load_freshness_hours
from search.app.settings import apply_endpoint_overrides, load_config_with_overrides, search_config_path


class TextQueryRequest(BaseModel):
    text: list[str] = []
    categories: list[str] = []
    filters: dict[str, Any] = Field(default_factory=dict)
    k: int = 4


class ImageQueryRequest(TextQueryRequest):
    image_base64: str = ""


class FreshnessSettingRequest(BaseModel):
    data_freshness_hours: float = Field(gt=0)


async def retrieve_with_freshness(request: TextQueryRequest, image_bool: bool):
    keyword = next(
        (item for item in request.text if item.strip()),
        request.categories[0] if request.categories else "thermos cup",
    )
    records = retriever.catalog_records(keyword, request.k)
    should_refresh = retriever.freshness.needs_refresh(records)
    refreshed = False
    if should_refresh:
        products, refreshed = retriever.freshness.refresh(keyword)
        if refreshed:
            retriever.ingest_products(products)

    result = await retriever.retrieve(
        query=request.text,
        categories=request.categories,
        filters=request.filters,
        k=request.k,
        image_bool=image_bool,
        verbose=True,
    )
    response = dict(
        zip(
            (
                "texts",
                "ids",
                "similarities",
                "names",
                "images",
                "urls",
                "prices",
                "ratings",
            ),
            result,
        )
    )
    response["stale"] = should_refresh and not refreshed
    response["crawled_at"] = [record.get("crawled_at") for record in records]
    return response


app = FastAPI()

_data = apply_endpoint_overrides(load_config_with_overrides(search_config_path()))
_config = RetrieverConfig(
    text_embed_port=_data["text_embed_port"],
    image_embed_port=_data["image_embed_port"],
    text_model_name=_data["text_model_name"],
    image_model_name=_data["image_model_name"],
    db_port=_data["db_port"],
    db_name=_data["db_name"],
    sim_threshold=_data["sim_threshold"],
    text_collection=_data["text_collection"],
    image_collection=_data["image_collection"],
    category_prefilter_k=_data.get("category_prefilter_k", 50),
)
os.environ.setdefault("EMBED_API_KEY", "EMPTY")
retriever = Retriever(_config)
retriever.milvus_from_csv(_data["data_path"])

_freshness_file = Path(
    os.environ.get("DATA_FRESHNESS_FILE", "/tmp/shopping-ai-data-freshness")
)


@app.get("/config/freshness")
async def get_freshness():
    return {"data_freshness_hours": load_freshness_hours()}


@app.post("/config/freshness")
async def set_freshness(request: FreshnessSettingRequest):
    if request.data_freshness_hours <= 0:
        raise HTTPException(status_code=422, detail="data_freshness_hours must be positive")
    _freshness_file.parent.mkdir(parents=True, exist_ok=True)
    _freshness_file.write_text(str(request.data_freshness_hours), encoding="utf-8")
    retriever.freshness.ttl_hours = request.data_freshness_hours
    return {"data_freshness_hours": request.data_freshness_hours}


@app.post("/query/text")
async def query_text(request: TextQueryRequest):
    return await retrieve_with_freshness(request, False)


@app.post("/query/image")
async def query_image(request: ImageQueryRequest):
    return await retrieve_with_freshness(request, True)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
    }
