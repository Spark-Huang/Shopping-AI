"""Runtime configuration for the optional cognee memory subsystem."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = True) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _milvus_uri() -> str:
    host = os.getenv("MILVUS_HOST", "127.0.0.1")
    port = os.getenv("MILVUS_PORT", "19530")
    return os.getenv("MILVUS_URI", f"http://{host}:{port}")


@dataclass(frozen=True)
class MemorySettings:
    embedding_enabled: bool
    dataset_name: str
    milvus_uri: str
    llm_provider: str
    llm_endpoint: str
    llm_model: str
    llm_api_key: str
    embedding_provider: str
    embedding_endpoint: str
    embedding_model: str
    embedding_dimensions: int
    embedding_api_key: str
    data_root_directory: str
    system_root_directory: str


def load_memory_settings() -> MemorySettings:
    system_root = os.getenv(
        "MEMORY_COGNEE_SYSTEM_ROOT",
        str(Path(__file__).resolve().parent / ".cognee_system"),
    )
    data_root = os.getenv(
        "MEMORY_COGNEE_DATA_ROOT",
        str(Path(__file__).resolve().parent / ".cognee_data"),
    )
    return MemorySettings(
        embedding_enabled=_env_bool("MEMORY_EMBEDDING_ENABLED", True),
        dataset_name=os.getenv("MEMORY_COGNEE_DATASET", "shopping_ai_memory"),
        milvus_uri=_milvus_uri(),
        llm_provider=os.getenv("COGNEE_LLM_PROVIDER", "openai"),
        llm_endpoint=os.getenv("COGNEE_LLM_ENDPOINT", os.getenv("LLM_BASE_URL", "")),
        llm_model=os.getenv("COGNEE_LLM_MODEL", os.getenv("LLM_NAME", "")),
        llm_api_key=os.getenv("COGNEE_LLM_API_KEY", os.getenv("LLM_API_KEY", "")),
        embedding_provider=os.getenv("COGNEE_EMBEDDING_PROVIDER", "openai"),
        embedding_endpoint=os.getenv(
            "COGNEE_EMBEDDING_ENDPOINT", os.getenv("EMBED_BASE_URL", "")
        ),
        embedding_model=os.getenv(
            "COGNEE_EMBEDDING_MODEL", os.getenv("EMBED_NAME", "")
        ),
        embedding_dimensions=int(os.getenv("COGNEE_EMBEDDING_DIMENSIONS", "3072")),
        embedding_api_key=os.getenv(
            "COGNEE_EMBEDDING_API_KEY", os.getenv("EMBED_API_KEY", "")
        ),
        data_root_directory=data_root,
        system_root_directory=system_root,
    )
