"""Tests for the search service freshness configuration API."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from search.app import engine as engine_mod
from search.app import settings as settings_mod
from search.app.freshness import DEFAULT_FRESHNESS_HOURS


@pytest.fixture
def api_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setenv("DATA_FRESHNESS_FILE", str(tmp_path / "freshness"))
    monkeypatch.setenv("REGION_FILE", str(tmp_path / "region"))
    monkeypatch.delenv("SHOPPING_REGION", raising=False)
    monkeypatch.delenv("DATA_FRESHNESS_HOURS", raising=False)

    config = {
        "text_embed_port": "http://localhost:9000/v1",
        "image_embed_port": "http://localhost:9001/v1",
        "text_model_name": "text-model",
        "image_model_name": "image-model",
        "db_port": "http://localhost:19530",
        "db_name": "catalog",
        "sim_threshold": 0.1,
        "text_collection": "text_col",
        "image_collection": "image_col",
        "category_prefilter_k": 50,
        "data_path": str(tmp_path / "catalog.csv"),
    }

    class _Freshness:
        ttl_hours = DEFAULT_FRESHNESS_HOURS

    class _Retriever:
        def __init__(self, *_args, **_kwargs) -> None:
            self.freshness = _Freshness()

        def milvus_from_csv(self, _: str) -> None:
            return None

    monkeypatch.setattr(settings_mod, "load_config_with_overrides", lambda _: config)
    monkeypatch.setattr(engine_mod, "Retriever", _Retriever)
    sys.modules.pop("search.app.main", None)
    search_main = importlib.import_module("search.app.main")
    yield TestClient(search_main.app)
    sys.modules.pop("search.app.main", None)


def test_freshness_api_reads_writes_and_rejects_invalid_values(api_client):
    response = api_client.get("/config/freshness")
    assert response.status_code == 200
    assert response.json() == {"data_freshness_hours": 24}

    response = api_client.post(
        "/config/freshness", json={"data_freshness_hours": 36.5}
    )
    assert response.status_code == 200
    assert response.json() == {"data_freshness_hours": 36.5}

    assert api_client.get("/config/freshness").json() == {
        "data_freshness_hours": 36.5
    }
    assert api_client.post(
        "/config/freshness", json={"data_freshness_hours": 0}
    ).status_code == 422
    assert api_client.post(
        "/config/freshness", json={"data_freshness_hours": "invalid"}
    ).status_code == 422


def test_region_api_reads_writes_and_rejects_invalid_values(api_client):
    response = api_client.get("/config/region")
    assert response.status_code == 200
    assert response.json() == {"region": "贵州"}

    response = api_client.post("/config/region", json={"region": "四川"})
    assert response.status_code == 200
    assert response.json() == {"region": "四川"}
    assert api_client.get("/config/region").json() == {"region": "四川"}
    assert api_client.post(
        "/config/region", json={"region": "Invalid region"}
    ).status_code == 422
