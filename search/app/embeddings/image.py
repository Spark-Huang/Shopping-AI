"""Image embedding adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.embeddings import Embeddings

if TYPE_CHECKING:
    from search.app.engine import Retriever


class ImageEmbeddings(Embeddings):
    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def embed_query(self, text: str) -> list[float]:
        embeddings = self.retriever.image_embeddings([text], verbose=True)
        if embeddings and embeddings[0] is not None:
            return embeddings[0]
        raise ValueError("Failed to generate image embedding")

    def embed_documents(self, texts: list[str]) -> list[list[float] | None]:
        return self.retriever.image_embeddings(texts)
