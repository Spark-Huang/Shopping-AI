from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from memory.app.cognee_client import CogneeClient, _result_texts
from memory.app.memory_config import load_memory_settings


class FakeCognee:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.added: list[Any] = []
        self.cognified: list[Any] = []
        self.queries: list[Any] = []
        self.SearchType = SimpleNamespace(CHUNKS="chunks")

    async def add(self, data: list[str], dataset_name: str) -> None:
        self.added.append((data, dataset_name))
        if self.failure:
            raise self.failure

    async def cognify(self, datasets: list[str]) -> None:
        self.cognified.append(datasets)

    async def search(self, **kwargs: Any) -> list[Any]:
        self.queries.append(kwargs)
        if self.failure:
            raise self.failure
        return [SimpleNamespace(text="User prefers blue dresses."), "budget: $75"]


def make_settings(tmp_path: Path, enabled: bool = True):
    settings = load_memory_settings()
    return type(settings)(
        **{
            **settings.__dict__,
            "embedding_enabled": enabled,
            "dataset_name": "shopping_ai_memory",
            "data_root_directory": str(tmp_path / "data"),
            "system_root_directory": str(tmp_path / "system"),
        }
    )


async def test_extract_uses_cognee_dataset(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    client = CogneeClient(settings=settings, api=FakeCognee())

    assert await client.extract("User: hi\nAssistant: hello") is True

    api = client.api
    assert api.added == [(["User: hi\nAssistant: hello"], "shopping_ai_memory")]
    assert api.cognified == [["shopping_ai_memory"]]


async def test_retrieve_normalizes_results(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    api = FakeCognee()
    client = CogneeClient(settings=settings, api=api)

    assert await client.retrieve("dress preferences") == [
        "User prefers blue dresses.",
        "budget: $75",
    ]
    assert api.queries[0]["datasets"] == ["shopping_ai_memory"]


def test_result_texts_accepts_cognee_shapes() -> None:
    assert _result_texts(
        [
            SimpleNamespace(text="namespace text"),
            {"text": "dictionary text"},
            "plain text",
            "",
        ]
    ) == ["namespace text", "dictionary text", "plain text"]


@pytest.mark.parametrize("method", ["extract", "retrieve"])
async def test_cognee_failures_degrade_gracefully(
    tmp_path: Path, method: str
) -> None:
    client = CogneeClient(
        settings=make_settings(tmp_path), api=FakeCognee(RuntimeError("Milvus down"))
    )

    if method == "extract":
        assert await client.extract("conversation") is False
    else:
        assert await client.retrieve("conversation") == []


async def test_memory_switch_disables_cognee(tmp_path: Path) -> None:
    api = FakeCognee()
    client = CogneeClient(settings=make_settings(tmp_path, enabled=False), api=api)

    assert await client.extract("conversation") is False
    assert await client.retrieve("conversation") == []
    assert api.added == []
    assert api.queries == []
