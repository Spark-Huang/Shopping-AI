import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from memory.app import database
from memory.app.auth import create_token
from memory.app import models
from memory.app import main as memory_main
from memory.app.main import app


@pytest.fixture()
def memory_client(tmp_path, monkeypatch):
    engine = database.create_engine(
        f"sqlite:///{tmp_path / 'memory.db'}",
        connect_args={"check_same_thread": False},
        poolclass=database.NullPool,
    )
    database._current_engine = engine
    models.Base.metadata.drop_all(bind=database._current_engine)
    models.Base.metadata.create_all(bind=engine)
    memory_session_local = sessionmaker(bind=engine)
    monkeypatch.setattr(memory_main, "SessionLocal", memory_session_local)
    monkeypatch.setattr(database, "SessionLocal", memory_session_local)
    client = TestClient(app)
    token = create_token(7, "alice")
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


def test_session_crud_and_scoping(memory_client):
    client, headers = memory_client
    created = client.post(
        "/user/7/sessions", json={"title": ""}, headers=headers
    )
    assert created.status_code == 200
    session = created.json()
    session_id = session["id"]

    listed = client.get("/user/7/sessions", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["sessions"]] == [session_id]

    updated = client.patch(
        f"/user/7/sessions/{session_id}", json={"title": "买化妆台和衣服"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "买化妆台和衣服"

    assert client.get(f"/user/8/sessions/{session_id}", headers=headers).status_code == 404
    deleted = client.delete(f"/user/7/sessions/{session_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/user/7/sessions", headers=headers).json()["sessions"] == []


def test_session_messages_and_legacy_null_writes(memory_client, monkeypatch):
    client, headers = memory_client
    session = client.post("/user/7/sessions", json={"title": ""}, headers=headers).json()

    class _NeverExtract:
        settings = type("Settings", (), {"embedding_enabled": False})()

    monkeypatch.setattr(memory_main, "cognee_client", _NeverExtract())
    persisted = client.post(
        "/user/7/messages/extract",
        json={"query": "买玩具", "response": "ok", "session_id": session["id"]},
        headers=headers,
    )
    assert persisted.status_code == 200

    with memory_main.SessionLocal() as db:
        rows = db.execute(
            database.text("SELECT session_id FROM messages ORDER BY id")
        ).fetchall()
    assert rows == [(session["id"],), (session["id"],)]

    messages = client.get(
        f"/user/7/sessions/{session['id']}/messages", headers=headers
    )
    assert messages.status_code == 200
    assert len(messages.json()["messages"]) == 2


def test_existing_messages_table_gets_nullable_session_id(tmp_path):
    engine = database.create_engine(
        f"sqlite:///{tmp_path / 'legacy.db'}",
        connect_args={"check_same_thread": False},
        poolclass=database.NullPool,
    )
    with engine.begin() as conn:
        conn.execute(
            database.text(
                "CREATE TABLE messages (id INTEGER PRIMARY KEY, user_id INTEGER, "
                "role VARCHAR(16), content TEXT, created_at DATETIME)"
            )
        )
    database._current_engine = engine
    database.Base.metadata.create_all(bind=engine, tables=[database.Base.metadata.tables["sessions"]])
    database._ensure_session_columns()
    with engine.connect() as conn:
        columns = conn.execute(database.text("PRAGMA table_info(messages)")).fetchall()
        session_column = next(column for column in columns if column[1] == "session_id")
    assert session_column[2] == "INTEGER"
    assert session_column[3] == 0
