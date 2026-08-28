"""Search service API routes."""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from search.app.embeddings.text import RetrieverConfig
from search.app.engine import Retriever
from search.app.settings import apply_endpoint_overrides, load_config_with_overrides, search_config_path


class TextQueryRequest(BaseModel):
    text: list[str] = []
    categories: list[str] = []
    filters: dict[str, Any] = Field(default_factory=dict)
    k: int = 4


class ImageQueryRequest(TextQueryRequest):
    image_base64: str = ""


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


@app.post("/query/text")
async def query_text(request: TextQueryRequest):
    texts, ids, similarities, names, images, urls, prices, ratings = await retriever.retrieve(
        query=request.text,
        categories=request.categories,
        filters=request.filters,
        k=request.k,
        image_bool=False,
        verbose=True,
    )
    return {
        "texts": texts,
        "ids": ids,
        "similarities": similarities,
        "names": names,
        "images": images,
        "urls": urls,
        "prices": prices,
        "ratings": ratings,
    }


@app.post("/query/image")
async def query_image(request: ImageQueryRequest):
    texts, ids, similarities, names, images, urls, prices, ratings = await retriever.retrieve(
        query=request.text,
        image=request.image_base64,
        categories=request.categories,
        filters=request.filters,
        k=request.k,
        image_bool=True,
        verbose=True,
    )
    return {
        "texts": texts,
        "ids": ids,
        "similarities": similarities,
        "names": names,
        "images": images,
        "urls": urls,
        "prices": prices,
        "ratings": ratings,
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
    }
