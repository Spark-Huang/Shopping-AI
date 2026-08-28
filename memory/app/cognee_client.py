"""Fault-tolerant cognee adapter for long-term user memory."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .memory_config import MemorySettings, load_memory_settings

logger = logging.getLogger(__name__)


class CogneeApi(Protocol):
    async def add(self, data: list[str], dataset_name: str) -> Any:
        """Add source text to a cognee dataset."""

    async def cognify(self, datasets: list[str]) -> Any:
        """Run cognee's extraction pipeline."""

    async def search(
        self, *, query_type: Any, query_text: str, datasets: Any = None
    ) -> Any:
        """Search extracted knowledge."""


@dataclass
class CogneeClient:
    settings: MemorySettings
    api: CogneeApi | None = None

    @classmethod
    def from_env(cls) -> "CogneeClient":
        return cls(settings=load_memory_settings())

    def configure(self) -> CogneeApi:
        if self.api is not None:
            return self.api

        import cognee

        settings = self.settings
        Path(settings.data_root_directory).mkdir(parents=True, exist_ok=True)
        Path(settings.system_root_directory).mkdir(parents=True, exist_ok=True)
        cognee.config.data_root_directory(settings.data_root_directory)
        cognee.config.system_root_directory(settings.system_root_directory)
        llm_config = cognee.infrastructure.llm.config.get_llm_config()
        llm_config.llm_provider = settings.llm_provider
        llm_config.llm_endpoint = settings.llm_endpoint
        llm_config.llm_model = settings.llm_model
        llm_config.llm_api_key = settings.llm_api_key
        embedding_config = (
            cognee.infrastructure.databases.vector.embeddings.config.get_embedding_config()
        )
        embedding_config.embedding_provider = settings.embedding_provider
        embedding_config.embedding_endpoint = settings.embedding_endpoint
        embedding_config.embedding_model = settings.embedding_model
        embedding_config.embedding_dimensions = settings.embedding_dimensions
        embedding_config.embedding_api_key = settings.embedding_api_key
        cognee.config.set_vector_db_config(
            {
                "vector_db_url": settings.milvus_uri,
                "vector_db_provider": "milvus",
            }
        )
        self.api = cognee
        return self.api

    async def extract(self, text: str) -> bool:
        if not self.settings.embedding_enabled:
            return False
        try:
            api = self.configure()
            await api.add([text], self.settings.dataset_name)
            await api.cognify([self.settings.dataset_name])
            return True
        except Exception as exc:
            logger.warning("memory | cognee extraction degraded to SQLite: %s", exc)
            return False

    async def retrieve(self, query: str) -> list[str]:
        if not self.settings.embedding_enabled:
            return []
        try:
            api = self.configure()
            search_types = getattr(api, "SearchType", None)
            query_type = (
                getattr(search_types, "CHUNKS", "Chunks") if search_types else "Chunks"
            )

            results = await api.search(
                query_type=query_type,
                query_text=query,
                datasets=[self.settings.dataset_name],
            )
            return _result_texts(results)[:8]
        except Exception as exc:
            logger.warning(
                "memory | cognee retrieval degraded to users.context: %s", exc
            )
            return []


def _result_texts(results: Any) -> list[str]:
    if not isinstance(results, list):
        return []
    texts: list[str] = []
    for result in results:
        if isinstance(result, str):
            value = result
        elif isinstance(result, dict):
            value = str(result.get("text") or "")
        else:
            value = str(getattr(result, "text", "") or "")
        if value.strip():
            texts.append(value.strip())
    return texts
