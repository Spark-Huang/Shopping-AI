"""Text embedding model configuration and adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

if TYPE_CHECKING:
    from search.app.engine import Retriever


class RetrieverConfig(BaseModel):
    text_embed_port: str
    image_embed_port: str = ""
    text_model_name: str
    image_model_name: str = ""
    db_port: str
    db_name: str
    sim_threshold: float
    text_collection: str
    image_collection: str
    category_prefilter_k: int = 50


class TextEmbeddings(Embeddings):
    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def embed_query(self, text: str) -> list[float]:
        result = self.retriever.embed_chunk(text)
        return result / np.linalg.norm(result)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        results = self.retriever.text_embeddings(texts)
        return [list(result / np.linalg.norm(result)) for result in results]
