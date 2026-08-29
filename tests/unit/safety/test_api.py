
"""Unit tests for ``safety.app.main``.

``main.py`` imports ``engine`` at module load time, which in turn instantiates
``ContentSafety``. To keep this hermetic we inject a fake ``nemoguardrails`` into
``sys.modules`` *before* importing ``main``. Tests then drive the FastAPI app
through ``TestClient`` as if it were running behind uvicorn.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Iterator, List

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[3]
SAFETY_APP = str(REPO_ROOT / "safety" / "app")


def _install_stub_safety_package(recorded: Dict[str, Any]) -> None:
    class _RailsConfig:
        def __init__(self, path: str) -> None:
            self.config_path = path
            self.models = []

        @classmethod
        def from_path(cls, path: str) -> "_RailsConfig":
            return cls(path)

    class _LLMRails:
        def __init__(self, config: Any) -> None:
            self._config = config

        async def generate_async(
            self, messages: List[Dict[str, Any]], options: Dict[str, Any]
        ) -> Dict[str, Any]:
            recorded.setdefault("calls", []).append(
                {"messages": messages, "options": options}
            )
            # Default behaviour: echo the last message as assistant content
            # (i.e. treat input/output as safe).
            last = messages[-1]
            return {
                "response": [
                    {"role": "assistant", "content": last["content"]}
                ]
            }

    fake = ModuleType("nemoguardrails")
    fake.RailsConfig = _RailsConfig
    fake.LLMRails = _LLMRails
    sys.modules["nemoguardrails"] = fake


@pytest.fixture
def safety_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    recorded: Dict[str, Any] = {}
    _install_stub_safety_package(recorded)

    if SAFETY_APP not in sys.path:
        sys.path.insert(0, SAFETY_APP)

    for name in ("safety.app.main", "safety.app.engine"):
        sys.modules.pop(name, None)

    main_module = importlib.import_module("safety.app.main")
    main_module._test_recorded = recorded  # type: ignore[attr-defined]
    yield main_module

    for name in ("safety.app.main", "safety.app.engine"):
        sys.modules.pop(name, None)


@pytest.fixture
def client(safety_app) -> TestClient:
    return TestClient(safety_app.app)


class TestSafetyEndpoints:
    def test_health_returns_200_with_status(self, client: TestClient) -> None:
        response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["version"] == "1.0.0"
        assert "timestamp" in body

    def test_input_check_echoes_safe_query(
        self, safety_app, client: TestClient
    ) -> None:
        response = client.post(
            "/safety/input",
            json={"user_id": 1, "query": "safe query"},
        )
        assert response.status_code == 200

        body = response.json()
        assert body["response"][0]["content"] == "safe query"

        calls = safety_app._test_recorded["calls"]
        assert calls[-1]["options"] == {"rails": ["input"]}

    def test_output_check_uses_output_safety(
        self, safety_app, client: TestClient
    ) -> None:
        response = client.post(
            "/safety/output",
            json={"user_id": 1, "query": "bot reply"},
        )
        assert response.status_code == 200

        calls = safety_app._test_recorded["calls"]
        assert calls[-1]["options"] == {"rails": ["output"]}

    def test_input_timing_includes_timings_field(
        self, safety_app, client: TestClient
    ) -> None:
        response = client.post(
            "/safety/input/timing",
            json={"user_id": 1, "query": "hello"},
        )
        assert response.status_code == 200

        body = response.json()
        # Timings is appended by the endpoint; structure is a list of single-key
        # dicts (["safety", "total"]).
        assert "timings" in body
        keys = [list(entry.keys())[0] for entry in body["timings"]]
        assert keys == ["safety", "total"]

    def test_output_timing_includes_timings_field(
        self, safety_app, client: TestClient
    ) -> None:
        response = client.post(
            "/safety/output/timing",
            json={"user_id": 1, "query": "hello"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "timings" in body
        assert isinstance(body["timings"], list)

    def test_missing_fields_returns_422(
        self, safety_app, client: TestClient
    ) -> None:
        response = client.post(
            "/safety/input",
            json={"user_id": 1},  # query missing
        )
        assert response.status_code == 422
