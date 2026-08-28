from __future__ import annotations

import asyncio

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memory.app import database as memory_database
from memory.app import main as memory_main


class SlowCognee:
    def __init__(self) -> None:
        self.calls = 0
        self.settings = SimpleNamespace(embedding_enabled=True)

    async def extract(self, _: str) -> bool:
        await asyncio.sleep(0.05)
        self.calls += 1
        return True

    async def retrieve(self, _: str) -> list[str]:
        return []


def use_memory_database(monkeypatch) -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(memory_main, "engine", engine)
    monkeypatch.setattr(memory_main, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(memory_database, "_current_engine", engine)
    memory_main.Base.metadata.create_all(bind=engine)
    return engine


async def _disabled_retrieve(_: str) -> list[str]:
    return []


def test_extract_persists_both_messages_without_blocking(
    monkeypatch,
) -> None:
    engine = use_memory_database(monkeypatch)
    client = TestClient(memory_main.app)
    slow_cognee = SlowCognee()
    memory_main.cognee_client = slow_cognee
    try:
        response = client.post(
            "/user/42/messages/extract",
            json={
                "query": "I prefer blue dresses",
                "response": "Noted for future searches",
            },
        )
    finally:
        asyncio.run(asyncio.sleep(0))

    assert response.status_code == 200
    assert response.json()["extraction_scheduled"] is True
    assert slow_cognee.calls == 0
    stored = client.get("/user/42/messages").json()["messages"]
    assert [(row["role"], row["content"]) for row in stored] == [
        ("user", "I prefer blue dresses"),
        ("assistant", "Noted for future searches"),
    ]
    memory_main.Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_disabled_memory_still_persists_and_uses_context(
    monkeypatch,
) -> None:
    engine = use_memory_database(monkeypatch)
    client = TestClient(memory_main.app)
    client.post("/user/7/context/add", json={"new_context": "existing"})
    original_client = memory_main.cognee_client
    memory_main.cognee_client = SimpleNamespace(
        settings=SimpleNamespace(embedding_enabled=False),
        retrieve=_disabled_retrieve,
    )
    try:
        response = client.post(
            "/user/7/messages/extract",
            json={"query": "hi", "response": "hello"},
        )
        semantic = client.get("/user/7/memory", params={"query": "hello"})
    finally:
        memory_main.cognee_client = original_client

    assert response.json()["extraction_scheduled"] is False
    assert semantic.json()["context"] == "existing"
    memory_main.Base.metadata.drop_all(bind=engine)
    engine.dispose()
