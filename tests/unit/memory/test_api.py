"""Unit tests for ``memory.app.main``.

The service creates a module-level SQLite engine bound to ``./context.db``.
For tests we reconfigure it to an in-memory engine and rebuild the schema
against that engine. Every test gets a fresh database through the
``isolated_memory_db`` fixture so state never leaks between cases.
"""

from __future__ import annotations

import asyncio
from typing import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, Table, create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from memory.app import database as memory_database
from memory.app import models as memory_models
from memory.app import main as memory_main

# The service split main.py into database/models/main; surface the pieces the
# tests address as flat attributes, matching the pre-split module surface.
memory_main.engine = memory_database.engine
memory_main.Base = memory_database.Base
memory_main._ensure_cart_columns = memory_database._ensure_cart_columns
memory_main._ensure_cart_unique_index = memory_database._ensure_cart_unique_index
memory_main.CartItem = memory_models.CartItem
memory_main.User = memory_models.User
memory_main.Order = memory_models.Order


@pytest.fixture
def isolated_memory_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Swap the module-level SQLite engine for a per-test in-memory one.

    We use ``StaticPool`` + the ``:memory:`` URL so all sessions opened
    during a single test share the same connection and therefore see the
    same data. At teardown the module's original globals are restored so
    subsequent tests see fresh tables.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session_local = sessionmaker(bind=test_engine)

    monkeypatch.setattr(memory_main, "engine", test_engine)
    monkeypatch.setattr(memory_main, "SessionLocal", test_session_local)
    monkeypatch.setattr(memory_database, "_current_engine", test_engine)

    memory_main.Base.metadata.create_all(bind=test_engine)

    yield

    memory_main.Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture
def client(isolated_memory_db) -> TestClient:
    return TestClient(memory_main.app)


class TestCartMigration:
    @pytest.mark.parametrize("legacy_column", ["price", "url"])
    def test_cart_columns_migrate_idempotently(
        self,
        isolated_memory_db: None,
        legacy_column: str,
    ) -> None:
        table = memory_main.CartItem.__table__
        memory_main.Base.metadata.drop_all(bind=memory_main.engine, tables=[table])
        legacy_columns = [
            Column(
                column.name,
                column.type,
                primary_key=column.primary_key,
            )
            for column in table.columns
            if column.name != legacy_column
        ]
        legacy_metadata = memory_main.Base.metadata.__class__()
        legacy_table = Table(
            table.name,
            legacy_metadata,
            *legacy_columns,
        )
        table.drop(bind=memory_main.engine, checkfirst=True)
        legacy_table.create(bind=memory_main.engine)

        with memory_main.engine.connect() as conn:
            indexes = {index["name"] for index in inspect(conn).get_indexes(table.name)}
            if "ix_cart_items_user_id" not in indexes:
                conn.execute(text("CREATE INDEX ix_cart_items_user_id ON cart_items (user_id)"))

        engine = memory_main.engine
        with engine.connect() as conn:
            before = {column["name"] for column in inspect(conn).get_columns(table.name)}
            assert legacy_column not in before
        memory_main._ensure_cart_columns()
        memory_main._ensure_cart_columns()
        with engine.connect() as conn:
            after = {column["name"] for column in inspect(conn).get_columns(table.name)}
            assert {"price", "url"} <= after

    def test_cart_duplicates_are_removed_and_unique_index_is_idempotent(
        self, isolated_memory_db: None
    ) -> None:
        with memory_main.SessionLocal() as session, session.begin():
            session.execute(text("DROP INDEX IF EXISTS ux_cart_items_user_item"))
            session.add_all(
                [
                    memory_main.CartItem(
                        id=1, user_id=1, item="Silk Dress", amount=1, price=49.9
                    ),
                    memory_main.CartItem(
                        id=2, user_id=1, item="Silk Dress", amount=2, price=59.9
                    ),
                ]
            )

        memory_main._ensure_cart_unique_index()
        memory_main._ensure_cart_unique_index()

        with memory_main.engine.connect() as conn:
            index_names = {
                index["name"] for index in inspect(conn).get_indexes("cart_items")
            }
            rows = conn.execute(
                text(
                    "SELECT id, amount, price FROM cart_items "
                    "WHERE user_id = 1 AND item = 'Silk Dress'"
                )
            ).all()
            pragma = conn.exec_driver_sql(
                "PRAGMA index_info(ux_cart_items_user_item)"
            ).fetchall()

        assert "ux_cart_items_user_item" in index_names
        assert rows == [(1, 1, 49.9)]
        assert [column[2] for column in pragma] == ["user_id", "item"]

    def test_sqlite_uses_wal_and_five_second_busy_timeout(
        self, isolated_memory_db: None
    ) -> None:
        with memory_main.engine.connect() as conn:
            journal_mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
            busy_timeout = conn.exec_driver_sql("PRAGMA busy_timeout").scalar()

        if not memory_main.engine.url.database.startswith(":memory:"):
            assert str(journal_mode).lower() == "wal"
        assert busy_timeout == 5000


# --------------------------------------------------------------------------->
# Health
# --------------------------------------------------------------------------->


class TestHealth:
    def test_health_returns_200_with_status(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert "timestamp" in body
        assert body["version"] == "1.0.0"

    def test_concurrent_context_reads_do_not_exhaust_pool(
        self, isolated_memory_db, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        test_engine = create_engine(
            f"sqlite:///{tmp_path / 'context.db'}",
            poolclass=NullPool,
        )
        monkeypatch.setattr(memory_main, "engine", test_engine)
        monkeypatch.setattr(
            memory_main, "SessionLocal", sessionmaker(bind=test_engine)
        )
        memory_main.Base.metadata.create_all(bind=test_engine)

        with ThreadPoolExecutor(max_workers=30) as executor:
            results = list(
                executor.map(
                    lambda _: asyncio.run(memory_main.get_context(1)),
                    range(30),
                )
            )

        assert results == [{"user_id": 1, "context": ""}] * 30

        memory_main.Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


# --------------------------------------------------------------------------->
# Cart endpoints
# --------------------------------------------------------------------------->


class TestCartFlows:
    def test_empty_cart_returns_empty_list(self, client: TestClient) -> None:
        response = client.get("/user/1/cart")
        assert response.status_code == 200
        assert response.json() == {"user_id": 1, "cart": []}

    def test_add_single_item(self, client: TestClient) -> None:
        response = client.post(
            "/user/1/cart/add",
            json={"item": "Silk Dress", "amount": 1, "price": 49.99},
        )
        assert response.status_code == 200
        assert "added 1" in response.json()["message"]

        listed = client.get("/user/1/cart").json()["cart"][0]
        assert {key: value for key, value in listed.items() if key != "url"} == {
            "item": "Silk Dress",
            "amount": 1,
            "price": 49.99,
        }
        assert listed["url"] is None

    @pytest.mark.parametrize(
        "url",
        [
            "javascript:alert(1)",
            "http://example.com/product",
            "https://example.com/" + "a" * 2049,
        ],
    )
    def test_add_rejects_unsafe_or_oversized_url(
        self, client: TestClient, url: str
    ) -> None:
        response = client.post(
            "/user/1/cart/add",
            json={"item": "Silk Dress", "amount": 1, "url": url},
        )

        assert response.status_code == 422
        assert client.get("/user/1/cart").json()["cart"] == []

    def test_repeated_add_increments_existing_amount(self, client: TestClient) -> None:
        client.post(
            "/user/1/cart/add",
            json={"item": "Silk Dress", "amount": 1, "price": 49.99},
        )
        client.post(
            "/user/1/cart/add",
            json={"item": "Silk Dress", "amount": 2, "price": 49.99},
        )

        cart = client.get("/user/1/cart").json()["cart"][0]
        assert cart["item"] == "Silk Dress"
        assert cart["amount"] == 3
        assert cart["price"] == pytest.approx(49.99)

    def test_add_updates_price_when_newer_provided(
        self, client: TestClient
    ) -> None:
        client.post(
            "/user/1/cart/add",
            json={"item": "Silk Dress", "amount": 1, "price": 49.99},
        )
        client.post(
            "/user/1/cart/add",
            json={"item": "Silk Dress", "amount": 1, "price": 69.99},
        )

        cart = client.get("/user/1/cart").json()["cart"]
        assert cart[0]["price"] == pytest.approx(69.99)
        assert cart[0]["amount"] == 2

    def test_empty_url_overwrites_existing_url(self, client: TestClient) -> None:
        client.post(
            "/user/1/cart/add",
            json={
                "item": "Silk Dress",
                "amount": 1,
                "url": "https://example.com/old",
            },
        )
        client.post(
            "/user/1/cart/add",
            json={"item": "Silk Dress", "amount": 1, "url": ""},
        )

        cart = client.get("/user/1/cart").json()["cart"]
        assert cart[0]["url"] is None

    def test_add_without_price_keeps_existing_price(
        self, client: TestClient
    ) -> None:
        client.post(
            "/user/1/cart/add",
            json={"item": "Silk Dress", "amount": 1, "price": 49.99},
        )
        # Second call omits price; existing 49.99 should be preserved.
        client.post(
            "/user/1/cart/add",
            json={"item": "Silk Dress", "amount": 1},
        )

        cart = client.get("/user/1/cart").json()["cart"]
        assert cart[0]["price"] == pytest.approx(49.99)

    def test_remove_reduces_amount(self, client: TestClient) -> None:
        client.post(
            "/user/1/cart/add",
            json={"item": "Silk Dress", "amount": 3, "price": 49.99},
        )
        response = client.post(
            "/user/1/cart/remove",
            json={"item": "Silk Dress", "amount": 1},
        )
        assert response.status_code == 200

        cart = client.get("/user/1/cart").json()["cart"]
        assert cart[0]["amount"] == 2

    def test_remove_deletes_when_amount_exceeded(self, client: TestClient) -> None:
        client.post(
            "/user/1/cart/add",
            json={"item": "Silk Dress", "amount": 2, "price": 49.99},
        )
        client.post(
            "/user/1/cart/remove",
            json={"item": "Silk Dress", "amount": 5},
        )

        cart = client.get("/user/1/cart").json()["cart"]
        assert cart == []

    def test_remove_unknown_item_returns_404(self, client: TestClient) -> None:
        response = client.post(
            "/user/1/cart/remove",
            json={"item": "Ghost", "amount": 1},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Item not in cart"

    def test_clear_cart_removes_all_items(self, client: TestClient) -> None:
        client.post(
            "/user/1/cart/add",
            json={"item": "A", "amount": 1, "price": 10.0},
        )
        client.post(
            "/user/1/cart/add",
            json={"item": "B", "amount": 2, "price": 20.0},
        )

        response = client.post("/user/1/cart/clear")
        assert response.status_code == 200

        cart = client.get("/user/1/cart").json()["cart"]
        assert cart == []

    def test_clear_empty_cart_returns_404(self, client: TestClient) -> None:
        response = client.post("/user/999/cart/clear")
        assert response.status_code == 404

    def test_carts_are_partitioned_per_user(self, client: TestClient) -> None:
        client.post(
            "/user/1/cart/add",
            json={"item": "A", "amount": 1, "price": 10.0},
        )
        client.post(
            "/user/2/cart/add",
            json={"item": "B", "amount": 1, "price": 20.0},
        )

        assert client.get("/user/1/cart").json()["cart"][0]["item"] == "A"
        assert client.get("/user/2/cart").json()["cart"][0]["item"] == "B"

    def test_validation_error_on_missing_required_fields(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/user/1/cart/add",
            json={"amount": 1},
        )
        assert response.status_code == 422


# --------------------------------------------------------------------------->
# Orders
# --------------------------------------------------------------------------->


class TestOrders:
    def test_create_order_creates_user_and_returns_order(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/user/7/orders",
            json={"item": "Silk Dress", "price": 49.99, "purchased_at": "2026-08-01T10:30:00", "note": "manual"},
        )

        assert response.status_code == 200
        order = response.json()["order"]
        assert order["id"] > 0
        assert order["item"] == "Silk Dress"
        assert order["price"] == pytest.approx(49.99)
        assert order["purchased_at"] == "2026-08-01T10:30:00"
        assert order["note"] == "manual"

    def test_list_orders_orders_most_recent_first(self, client: TestClient) -> None:
        client.post("/user/8/orders", json={"item": "Old", "purchased_at": "2026-07-01T00:00:00"})
        client.post("/user/8/orders", json={"item": "New", "purchased_at": "2026-08-01T00:00:00"})

        response = client.get("/user/8/orders")
        assert response.status_code == 200
        assert [order["item"] for order in response.json()["orders"]] == ["New", "Old"]

    def test_orders_are_partitioned_per_user(self, client: TestClient) -> None:
        client.post("/user/1/orders", json={"item": "Mine"})
        client.post("/user/2/orders", json={"item": "Theirs"})

        assert client.get("/user/1/orders").json()["orders"][0]["item"] == "Mine"
        assert client.get("/user/2/orders").json()["orders"][0]["item"] == "Theirs"

    def test_invalid_order_returns_422(self, client: TestClient) -> None:
        response = client.post("/user/1/orders", json={"item": ""})
        assert response.status_code == 422

    def test_zero_price_order_is_accepted(self, client: TestClient) -> None:
        response = client.post("/user/1/orders", json={"item": "Gift", "price": 0})

        assert response.status_code == 200
        assert response.json()["order"]["price"] == 0

    @pytest.mark.parametrize("price", [-1, float("nan"), float("inf")])
    def test_invalid_order_price_returns_422(
        self, client: TestClient, price: float
    ) -> None:
        response = client.post(
            "/user/1/orders",
            content=f'{{"item":"Silk Dress","price":{price}}}'.encode(),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422
        assert client.get("/user/1/orders").json()["orders"] == []


# --------------------------------------------------------------------------->
# Context endpoints
# --------------------------------------------------------------------------->


class TestContextFlows:
    def test_context_empty_for_unknown_user(self, client: TestClient) -> None:
        response = client.get("/user/42/context")
        assert response.status_code == 200
        assert response.json() == {"user_id": 42, "context": ""}

    def test_add_context_creates_user(self, client: TestClient) -> None:
        response = client.post(
            "/user/1/context/add",
            json={"new_context": "hello"},
        )
        assert response.status_code == 200

        assert client.get("/user/1/context").json()["context"] == "hello"

    def test_add_context_appends_to_existing(self, client: TestClient) -> None:
        client.post("/user/1/context/add", json={"new_context": "first"})
        client.post("/user/1/context/add", json={"new_context": "second"})

        stored = client.get("/user/1/context").json()["context"]
        assert stored == "first second"

    def test_replace_context_overwrites_existing(
        self, client: TestClient
    ) -> None:
        client.post("/user/1/context/add", json={"new_context": "old"})
        client.post(
            "/user/1/context/replace",
            json={"new_context": "fresh"},
        )

        assert client.get("/user/1/context").json()["context"] == "fresh"

    def test_replace_context_creates_user_when_absent(
        self, client: TestClient
    ) -> None:
        client.post(
            "/user/99/context/replace",
            json={"new_context": "brand-new"},
        )
        assert (
            client.get("/user/99/context").json()["context"] == "brand-new"
        )

    def test_clear_context_deletes_user(self, client: TestClient) -> None:
        client.post("/user/1/context/add", json={"new_context": "sticky"})
        response = client.post("/user/1/context/clear")
        assert response.status_code == 200

        # After clear the user no longer exists: GET falls back to empty.
        assert client.get("/user/1/context").json() == {
            "user_id": 1,
            "context": "",
        }

    def test_clear_unknown_user_returns_404(self, client: TestClient) -> None:
        response = client.post("/user/404/context/clear")
        assert response.status_code == 404


# --------------------------------------------------------------------------->
# User-level endpoints
# --------------------------------------------------------------------------->


class TestUserEndpoints:
    def test_get_user_404_for_missing_user(self, client: TestClient) -> None:
        response = client.get("/user/7")
        assert response.status_code == 404

    def test_get_user_returns_context(self, client: TestClient) -> None:
        client.post("/user/7/context/add", json={"new_context": "hi"})

        response = client.get("/user/7")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 7
        assert body["context"] == "hi"

    def test_clear_user_removes_record(self, client: TestClient) -> None:
        client.post("/user/1/context/add", json={"new_context": "will be gone"})
        response = client.post("/user/1/clear")
        assert response.status_code == 200

        # After clear the user no longer exists.
        assert client.get("/user/1").status_code == 404

    def test_clear_user_removes_cart_items(self, client: TestClient) -> None:
        client.post("/user/1/context/add", json={"new_context": "cart owner"})
        client.post(
            "/user/1/cart/add",
            json={"item": "Test product", "amount": 1, "price": 19.99},
        )

        response = client.post("/user/1/clear")

        assert response.status_code == 200
        assert client.get("/user/1/cart").json()["cart"] == []
        with memory_main.SessionLocal() as db:
            assert db.query(memory_main.CartItem).filter_by(user_id=1).first() is None

    def test_clear_user_adds_owner_and_removes_orphan_cart_items(
        self, client: TestClient
    ) -> None:
        client.post(
            "/user/404/cart/add",
            json={"item": "Orphan product", "amount": 1, "price": 9.99},
        )

        with memory_main.SessionLocal() as db:
            assert db.query(memory_main.User).filter_by(id=404).first() is not None

        response = client.post("/user/404/clear")

        assert response.status_code == 200
        assert client.get("/user/404/cart").json()["cart"] == []
        with memory_main.SessionLocal() as db:
            assert db.query(memory_main.CartItem).filter_by(user_id=404).first() is None
            assert db.query(memory_main.User).filter_by(id=404).first() is None

    def test_clear_missing_user_is_idempotent(self, client: TestClient) -> None:
        response = client.post("/user/1234/clear")
        assert response.status_code == 200
