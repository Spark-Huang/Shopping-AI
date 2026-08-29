
"""Unit tests for ``orchestrator.app.main``.

The module does expensive work at import time: it calls ``load_config``,
constructs every agent, and compiles a LangGraph. For unit tests we replace
each of those with lightweight stubs before importing the module.
"""

from __future__ import annotations

import importlib
import json
import sys
from types import SimpleNamespace
from typing import Any, Dict, Iterator, List

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from orchestrator.app import auth as orchestrator_auth
from orchestrator.app.agents.state import Cart, State


def _bearer(user_id: int = 1) -> str:
    """Mint a valid Authorization header for the given user id."""
    token = pyjwt.encode(
        {"sub": str(user_id)}, orchestrator_auth.get_jwt_secret(), algorithm="HS256"
    )
    return f"Bearer {token}"


class _NoopAgent:
    """Constructor-only stub used for every agent class under test."""

    def __init__(self, *_: Any, **__: Any) -> None:
        self.invoked_with: List[Dict[str, Any]] = []

    async def invoke(self, state: State, verbose: bool = False) -> State:
        self.invoked_with.append({"state": state, "verbose": verbose})
        return state

    def decide_function(self, state: State) -> str:
        return "chatter"

    def generate(self, **_: Any) -> List[Dict[str, Any]]:
        return []


class _StubCompiledGraph:
    """Replacement for the compiled LangGraph runnable."""

    def __init__(self, response_text: str = "ok") -> None:
        self.response_text = response_text
        self.astream_calls: List[Any] = []
        self.ainvoke_calls: List[Any] = []

    async def astream(self, state: State, stream_mode: str = "custom"):
        self.astream_calls.append((state, stream_mode))
        for piece in ["hello ", "world"]:
            yield piece

    async def ainvoke(self, state: State) -> Dict[str, Any]:
        self.ainvoke_calls.append(state)
        return {
            "response": self.response_text,
            "timings": {"chatter": 0.1, "memory": 0.01},
        }


@pytest.fixture
def main_module(
    monkeypatch: pytest.MonkeyPatch, base_config
) -> Iterator[Any]:
    """Import ``orchestrator.app.main`` with all heavy deps stubbed."""
    from orchestrator.app.agents.cartops import agent as cart_mod
    from orchestrator.app.agents import chatter as chatter_mod
    from orchestrator.app import settings as config_mod
    from orchestrator.app import graph as graph_mod
    from orchestrator.app.agents import planner as planner_mod
    from orchestrator.app.agents import retrieval_proxy as retriever_mod
    from orchestrator.app.agents import summarizer as summarizer_mod

    # Config loader returns our pre-baked config rather than reading YAML.
    monkeypatch.setattr(config_mod, "load_config", lambda *a, **k: base_config)

    # Every agent class replaced with a noop stub.
    monkeypatch.setattr(cart_mod, "CartAgent", _NoopAgent)
    monkeypatch.setattr(chatter_mod, "ChatterAgent", _NoopAgent)
    monkeypatch.setattr(planner_mod, "PlannerAgent", _NoopAgent)
    monkeypatch.setattr(retriever_mod, "RetrieverAgent", _NoopAgent)
    monkeypatch.setattr(summarizer_mod, "SummaryAgent", _NoopAgent)

    compiled = _StubCompiledGraph()
    monkeypatch.setattr(graph_mod, "create_graph", lambda **_: compiled)

    # Force a fresh import so our stubs are actually used.
    sys.modules.pop("orchestrator.app.main", None)
    main_module = importlib.import_module("orchestrator.app.main")
    main_module._test_compiled = compiled  # type: ignore[attr-defined]

    yield main_module

    sys.modules.pop("orchestrator.app.main", None)


@pytest.fixture
def client(main_module) -> TestClient:
    return TestClient(main_module.app)


# ---------------------------------------------------------------------------
# create_initial_state
# ---------------------------------------------------------------------------


class TestCreateInitialState:
    def test_defaults_fill_empty_strings_and_empty_cart(
        self, main_module
    ) -> None:
        request = main_module.QueryRequest(user_id=1, query="hi")
        state = main_module.create_initial_state(request)

        assert state.user_id == 1
        assert state.query == "hi"
        assert state.context == ""
        assert state.image == ""
        assert isinstance(state.cart, Cart)
        assert state.cart.is_empty()
        assert state.safety_enabled is True

    def test_cart_passthrough(self, main_module) -> None:
        cart = Cart(contents=[{"item": "X", "amount": 2, "price": 9.99}])
        request = main_module.QueryRequest(user_id=1, query="hi", cart=cart)
        state = main_module.create_initial_state(request)

        assert state.cart.contents == cart.contents

    def test_none_context_becomes_empty(self, main_module) -> None:
        request = main_module.QueryRequest(user_id=1, query="hi", context=None)
        state = main_module.create_initial_state(request)
        assert state.context == ""

    def test_dialect_defaults_off_and_passes_through(self, main_module) -> None:
        request = main_module.QueryRequest(user_id=1, query="hi")
        assert main_module.create_initial_state(request).dialect is False

        request = main_module.QueryRequest(user_id=1, query="hi", dialect=True)
        assert main_module.create_initial_state(request).dialect is True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


class TestHealthAndRoot:
    def test_health_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["version"] == "1.0.0"

    def test_root_describes_endpoints(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

        body = response.json()
        assert body["message"] == "Guikelai API"
        assert body["version"] == "1.0.0"
        assert "query" not in body["endpoints"]
        for key in ["stream", "timing", "cart", "orders", "context", "health", "docs"]:
            assert key in body["endpoints"]


class TestProxyEndpoints:
    def test_session_routes_forward_authorization_to_memory(
        self, main_module, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        token = _bearer()
        requests_seen = []

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):
                return []

        def _request(method: str, url: str, **kwargs):
            requests_seen.append((method, url, kwargs.get("headers")))
            return _Response()

        monkeypatch.setattr(main_module.requests, "get", lambda url, **kwargs: _request("GET", url, **kwargs))
        monkeypatch.setattr(main_module.requests, "post", lambda url, **kwargs: _request("POST", url, **kwargs))

        assert main_module.session_list(1, authorization=token) == []
        assert main_module.session_create(1, {}, authorization=token) == []

        assert len(requests_seen) == 2
        assert all(headers["Authorization"] == token for _, _, headers in requests_seen)

    def test_freshness_routes_forward_authorization_to_search(
        self, main_module, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        token = _bearer()
        requests_seen = []

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"data_freshness_hours": 36.5}

        def _request(method: str, url: str, **kwargs):
            requests_seen.append((method, url, kwargs))
            return _Response()

        monkeypatch.setattr(main_module.requests, "get", lambda url, **kwargs: _request("GET", url, **kwargs))
        monkeypatch.setattr(main_module.requests, "post", lambda url, **kwargs: _request("POST", url, **kwargs))

        assert main_module.freshness_get(authorization=token) == {
            "data_freshness_hours": 36.5
        }
        assert main_module.freshness_set(
            {"data_freshness_hours": 36.5}, authorization=token
        ) == {"data_freshness_hours": 36.5}

        assert len(requests_seen) == 2
        assert all(url.endswith("/config/freshness") for _, url, _ in requests_seen)
        assert all(
            kwargs["headers"]["Authorization"] == token for *_, kwargs in requests_seen
        )

    def test_remove_cart_item_passes_body_to_memory_service(
        self, main_module, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded = {}

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"user_id": 1, "message": "removed"}

        def _post(
            url: str,
            json: Dict[str, Any],
            headers: Dict[str, str],
            timeout: int,
        ):
            recorded.update(
                {"url": url, "json": json, "headers": headers, "timeout": timeout}
            )
            return _Response()

        monkeypatch.setattr(main_module.requests, "post", _post)

        response = main_module.remove_cart_item(
            1, {"item": "Silk Dress", "amount": 1}, authorization=_bearer()
        )

        assert response["message"] == "removed"
        assert recorded["url"].endswith("/user/1/cart/remove")
        assert recorded["json"] == {"item": "Silk Dress", "amount": 1}
        assert recorded["headers"]["Authorization"] == _bearer()

    def test_add_cart_item_passes_image_to_memory_service(
        self, main_module, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded = {}

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"user_id": 1, "message": "added"}

        def _post(
            url: str,
            json: Dict[str, Any],
            headers: Dict[str, str],
            timeout: int,
        ):
            recorded.update({"url": url, "json": json})
            return _Response()

        monkeypatch.setattr(main_module.requests, "post", _post)

        response = main_module.add_cart_item(
            1,
            {
                "item": "Silk Dress",
                "amount": 1,
                "price": 49.9,
                "url": "https://example.com/dress",
                "image": "https://example.com/dress.jpg",
            },
            authorization=_bearer(),
        )

        assert response["message"] == "added"
        assert recorded["url"].endswith("/user/1/cart/add")
        assert recorded["json"]["image"] == "https://example.com/dress.jpg"
        assert recorded["json"]["idempotent"] is True

    def test_checkout_cart_passes_items_to_memory_service(
        self, main_module, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded = {}

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"user_id": 1, "message": "checked out"}

        def _post(url: str, json: Dict[str, Any], timeout: int):
            recorded.update({"url": url, "json": json, "timeout": timeout})
            return _Response()

        monkeypatch.setattr(main_module.requests, "post", _post)

        body = {"items": [{"item": "Silk Dress", "price": 49.99}]}
        response = main_module.checkout_cart(1, body, authorization=_bearer())

        assert response["message"] == "checked out"
        assert recorded["url"].endswith("/user/1/checkout")
        assert recorded["json"] == body

    def test_products_serves_csv_filtered_by_category(
        self, main_module, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        csv_path = tmp_path / "products.csv"
        csv_path.write_text(
            "\n".join(
                [
                    '"category","subcategory","name","description","url","price","image","story"',
                    '"guizhou","ethnic-wear","苗绣披肩","手工苗绣披肩","https://example.com/s1","158","/images/products/guizhou/miao-embroidered-shawl.png","苗绣故事"',
                    '"guizhou","food","老干妈油辣椒","贵州风味辣酱","https://example.com/s2","9","/images/products/guizhou/chili.jpg","辣椒故事"',
                    '"other","misc","外部商品","不在贵州目录","https://example.com/s3","10","",""',
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(main_module, "PRODUCTS_CSV", csv_path)

        response = main_module.list_products(category="guizhou")
        products = response["products"]

        assert len(products) == 2
        assert all(p["category"] == "guizhou" for p in products)
        by_name = {p["name"]: p for p in products}
        assert by_name["老干妈油辣椒"]["price"] == 9
        assert by_name["老干妈油辣椒"]["subcategory"] == "food"
        assert by_name["苗绣披肩"]["subcategory"] == "ethnic-wear"
        assert by_name["苗绣披肩"]["image"] == (
            "/images/products/guizhou/miao-embroidered-shawl.png"
        )
        # Cultural stories ride along for the showcase page and agent.
        assert "苗绣" in by_name["苗绣披肩"]["story"]

    def test_products_without_category_returns_whole_catalog(
        self, main_module, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        csv_path = tmp_path / "products.csv"
        csv_path.write_text(
            "\n".join(
                [
                    '"category","subcategory","name","description","url","price","image","story"',
                    '"guizhou","ethnic-wear","苗绣披肩","手工苗绣披肩","https://example.com/s1","158","/images/products/guizhou/miao-embroidered-shawl.png","苗绣故事"',
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(main_module, "PRODUCTS_CSV", csv_path)

        response = main_module.list_products(category=None)
        products = response["products"]

        assert len(products) == 1
        categories = {p["category"] for p in products}
        assert categories == {"guizhou"}
        assert all(product["sourceUrl"] for product in products)
        assert all(product["verifiedAt"] for product in products)

    def test_products_returns_empty_list_when_catalog_csv_missing(
        self, main_module, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """Until crawler data lands, a missing CSV degrades to an empty catalog."""
        monkeypatch.setattr(main_module, "PRODUCTS_CSV", tmp_path / "absent.csv")

        response = main_module.list_products(category="guizhou")

        assert response == {"products": []}

    def test_add_context_passes_stripped_fact_to_memory_service(
        self, main_module, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded = {}

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"user_id": 1, "message": "updated"}

        def _post(
            url: str,
            json: Dict[str, Any],
            headers: Dict[str, str],
            timeout: int,
        ):
            recorded.update(
                {"url": url, "json": json, "headers": headers, "timeout": timeout}
            )
            return _Response()

        monkeypatch.setattr(main_module.requests, "post", _post)

        response = main_module.add_context(
            1,
            {"new_context": "  MONTHLY BUDGET: $50.00  "},
            authorization=_bearer(),
        )

        assert response["message"] == "updated"
        assert recorded["url"].endswith("/user/1/context/add")
        assert recorded["json"] == {"new_context": "MONTHLY BUDGET: $50.00"}
        assert recorded["headers"]["Authorization"] == _bearer()


class TestAuthEnforcement:
    def test_stream_without_token_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/query/stream",
            json={"user_id": 1, "query": "hi"},
        )
        assert response.status_code == 401

    def test_stream_with_token_for_other_user_returns_403(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/query/stream",
            json={"user_id": 2, "query": "hi"},
            headers={"Authorization": _bearer(user_id=1)},
        )
        assert response.status_code == 403

    def test_stream_with_garbage_token_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/query/stream",
            json={"user_id": 1, "query": "hi"},
            headers={"Authorization": "Bearer not-a-jwt"},
        )
        assert response.status_code == 401

    def test_cart_without_token_returns_401(self, client: TestClient) -> None:
        response = client.get("/cart/1")
        assert response.status_code == 401


class TestAuthProxies:
    def test_register_proxies_to_memory_service(
        self, main_module, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded = {}

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"token": "t", "user": {"id": 1, "username": "alice"}}

        def _post(url: str, json: Dict[str, Any], headers: Dict[str, str], timeout: int):
            recorded.update({"url": url, "json": json, "headers": headers})
            return _Response()

        monkeypatch.setattr(main_module.requests, "post", _post)

        response = main_module.auth_register({"username": "alice", "password": "secret123"})

        assert response["user"]["username"] == "alice"
        assert recorded["url"].endswith("/auth/register")
        assert recorded["json"] == {"username": "alice", "password": "secret123"}

    def test_login_forwards_401_from_memory_service(
        self, main_module, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi import HTTPException

        class _Response:
            status_code = 401

            def json(self):
                return {"detail": "Invalid username or password"}

        def _post(url: str, json: Dict[str, Any], headers: Dict[str, str], timeout: int):
            return _Response()

        monkeypatch.setattr(main_module.requests, "post", _post)

        with pytest.raises(HTTPException) as excinfo:
            main_module.auth_login({"username": "alice", "password": "wrong"})
        assert excinfo.value.status_code == 401
        assert excinfo.value.detail == "Invalid username or password"

    def test_register_forwards_409_from_memory_service(
        self, main_module, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi import HTTPException

        class _Response:
            status_code = 409

            def json(self):
                return {"detail": "Username already taken"}

        def _post(url: str, json: Dict[str, Any], headers: Dict[str, str], timeout: int):
            return _Response()

        monkeypatch.setattr(main_module.requests, "post", _post)

        with pytest.raises(HTTPException) as excinfo:
            main_module.auth_register({"username": "alice", "password": "secret123"})
        assert excinfo.value.status_code == 409
        assert excinfo.value.detail == "Username already taken"

    def test_me_forwards_authorization_header(
        self, main_module, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded = {}

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"id": 1, "username": "alice"}

        def _get(url: str, headers: Dict[str, str], timeout: int):
            recorded.update({"url": url, "headers": headers})
            return _Response()

        monkeypatch.setattr(main_module.requests, "get", _get)

        response = main_module.auth_me(authorization=_bearer())

        assert response["username"] == "alice"
        assert recorded["url"].endswith("/auth/me")
        assert recorded["headers"]["Authorization"].startswith("Bearer ")


class TestTimingEndpoint:
    def test_returns_response_and_persists_ms_timings(
        self, main_module, client: TestClient, tmp_path
    ) -> None:
        timing_path = tmp_path / "timings.jsonl"
        main_module.TIMING_LOG = timing_path
        response = client.post(
            "/query/timing",
            json={"user_id": 1, "query": "hello"},
            headers={"Authorization": _bearer()},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["response"] == main_module._test_compiled.response_text
        assert "total" in body["timings"]
        assert body["timings"]["total"] > 0
        assert body["timings_ms"]["total"] > 0
        assert body["timings_ms"]["chatter"] == 100.0
        persisted = json.loads(timing_path.read_text())
        assert persisted["query"] == "hello"
        assert persisted["timings_ms"] == body["timings_ms"]


class TestStreamEndpoint:
    def test_stream_returns_sse_body_with_done_marker(
        self, main_module, client: TestClient
    ) -> None:
        with client.stream(
            "POST",
            "/query/stream",
            json={"user_id": 1, "query": "hi"},
            headers={"Authorization": _bearer()},
        ) as stream_response:
            assert stream_response.status_code == 200
            chunks: List[str] = []
            for line in stream_response.iter_lines():
                if line:
                    chunks.append(line)

        joined = "\n".join(chunks)
        assert "data: hello " in joined
        assert "data: world" in joined
        assert "[DONE]" in joined

    def test_image_only_query_populates_placeholder(
        self, main_module, client: TestClient
    ) -> None:
        # Image-only requests should get a placeholder query injected so that
        # the graph has something to work with.
        compiled = main_module._test_compiled
        compiled.astream_calls.clear()

        with client.stream(
            "POST",
            "/query/stream",
            json={"user_id": 1, "query": "", "image": "data:image/jpeg;base64,AAA"},
            headers={"Authorization": _bearer()},
        ) as stream_response:
            # Drain the stream so the generator actually runs.
            for _ in stream_response.iter_lines():
                pass

        assert compiled.astream_calls
        state_arg, _ = compiled.astream_calls[-1]
        assert state_arg.image.startswith("data:image/jpeg")
        assert "image" in state_arg.query.lower()


class TestValidation:
    def test_missing_user_id_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/query/timing",
            json={"query": "hi"},
        )
        assert response.status_code == 422

    def test_bad_payload_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/query/timing",
            json={"user_id": "not-an-int", "query": "hi"},
        )
        assert response.status_code == 422
