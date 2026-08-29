"""
Repository-wide pytest configuration for the offline unit test suite.

Goals
-----
- Make service source packages importable without bringing up Docker or any
  live backend. Each service lives in ``<service>/app/`` and is importable as
  ``<service>.app.<module>`` once the repo root is on ``sys.path``.
- Provide shared fixtures (``base_config``, ``make_openai_chat_response`` etc.)
  that all suites can depend on without knowing service-specific wiring.
- Ensure every service module that reads API keys at import time finds
  harmless placeholder values so tests can import them directly.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterator

import pytest

# Ensure the repo root is importable so tests can `import orchestrator.app...`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# Several service modules read API keys at import time. Set harmless defaults
# before any test imports them so we never trip on KeyError during collection.
for _key in ("LLM_API_KEY", "EMBED_API_KEY", "SAFETY_API_KEY"):
    os.environ.setdefault(_key, f"test-{_key.lower()}")


@pytest.fixture
def base_config() -> SimpleNamespace:
    """Return a valid orchestrator-shaped config object.

    Agent classes accept any object with matching attributes; using
    ``SimpleNamespace`` keeps the fixture decoupled from the concrete
    ``OrchestratorConfig`` pydantic model so we can test agents in isolation.
    """
    return SimpleNamespace(
        llm_port="http://localhost:8000/v1",
        llm_name="test-model",
        retriever_port="http://localhost:8010",
        memory_base_url="http://localhost:8011",
        safety_base_url="http://localhost:8012",
        routing_prompt="You are a routing assistant.",
        chatter_prompt=(
            "You are a helpful Shopping AI assistant.\n"
            "REAL UI CAPABILITIES: view/add/remove cart items, edit quantities, "
            "multi-select and check out selected items (records orders and "
            "clears them from the cart), and visit each item's external "
            "merchant link.\n"
            "BUDGET AWARENESS: if a prior budget appears in RECENT DISCUSSION, "
            "flag over-budget recommendations with `Budget alert:` and offer "
            "in-budget alternatives."
        ),
        categories=[
            "bag",
            "sunglasses",
            "dress",
            "shoes",
            "top blouse sweater",
            "ethnic-wear",
            "craft",
            "food",
            "drink",
        ],
        agent_choices=["cart", "retriever", "chatter"],
        memory_length=16384,
        top_k_retrieve=4,
        multimodal=True,
        chatter_max_tokens=None,
        unsafe_messages={
            "en": "Sorry, I can only help with shopping-related questions.",
            "zh": "抱歉，我只能协助购物相关问题。",
        },
    )


@pytest.fixture
def valid_config_dict() -> Dict[str, Any]:
    """Dict counterpart of :func:`base_config` for testing pydantic validation."""
    return {
        "llm_port": "http://localhost:8000/v1",
        "llm_name": "test-model",
        "retriever_port": "http://localhost:8010",
        "memory_base_url": "http://localhost:8011",
        "safety_base_url": "http://localhost:8012",
        "routing_prompt": "You are a routing assistant.",
        "chatter_prompt": "You are a helpful Shopping AI assistant.",
        "categories": ["bag", "shoes"],
        "agent_choices": ["cart", "retriever", "chatter"],
        "memory_length": 16384,
        "top_k_retrieve": 4,
        "multimodal": True,
        "unsafe_messages": {
            "en": "Sorry, I can only help with shopping-related questions.",
            "zh": "抱歉，我只能协助购物相关问题。",
        },
    }


class FakeResponse:
    """Minimal stand-in for ``requests.Response`` used by service tests.

    Providing a tiny shim here (rather than in each test file) keeps the
    service tests readable and avoids subtle coupling to the ``requests``
    implementation. Supports the subset of the interface exercised by the
    orchestrator agents: ``status_code``, ``text``, ``json``,
    ``raise_for_status``.
    """

    def __init__(
        self,
        json_data: Any = None,
        status_code: int = 200,
        text: str | None = None,
    ) -> None:
        self._json = json_data if json_data is not None else {}
        self.status_code = status_code
        self.text = text if text is not None else __import__("json").dumps(self._json)

    def json(self) -> Any:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise __import__("requests").exceptions.HTTPError(
                f"HTTP {self.status_code}"
            )


@pytest.fixture
def fake_response_cls() -> type:
    """Expose ``FakeResponse`` to tests as a fixture-friendly handle."""
    return FakeResponse


@pytest.fixture
def make_openai_chat_response():
    """Factory for a fake OpenAI chat completion response.

    The OpenAI client used across agents consumes
    ``response.choices[0].message`` (content + optional tool_calls). This
    fixture builds that nested structure from primitive inputs so tests don't
    repeat the ceremony.
    """

    def _build(
        content: str | None = None,
        tool_name: str | None = None,
        tool_arguments: str | None = None,
    ) -> SimpleNamespace:
        tool_calls = None
        if tool_name is not None:
            tool_calls = [
                SimpleNamespace(
                    function=SimpleNamespace(
                        name=tool_name,
                        arguments=tool_arguments or "{}",
                    )
                )
            ]
        message = SimpleNamespace(content=content, tool_calls=tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    return _build


@pytest.fixture
def stream_writer_capture(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Capture LangGraph stream writer payloads emitted by agent ``invoke``.

    Several orchestrator agents call ``get_stream_writer()`` and push events
    through it. For unit tests we intercept the factory and redirect writes
    into a plain list so assertions can inspect what the agent streamed
    without standing up the real LangGraph runtime.
    """
    from orchestrator.app.agents import chatter as chatter_mod
    from orchestrator.app.graph import nodes as nodes_mod

    captured: list[str] = []

    def _fake_writer() -> Any:
        def _write(payload: str) -> None:
            captured.append(payload)

        return _write

    monkeypatch.setattr(chatter_mod, "get_stream_writer", _fake_writer)
    monkeypatch.setattr(nodes_mod, "get_stream_writer", _fake_writer)
    yield captured
