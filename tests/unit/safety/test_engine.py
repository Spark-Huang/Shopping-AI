
"""Unit tests for ``safety.app.engine``.

The module is organised for an in-container layout (``/app/src`` on
``PYTHONPATH``) so its imports are flat (``from .endpoint_overrides import ...``)
and it instantiates the safety engine at module load time. To make it
testable as a library we:

* Add ``safety/app/`` to ``sys.path`` so the flat import resolves.
* Register a dummy ``nemoguardrails`` module in ``sys.modules`` *before*
  importing the safety engine so the real package is never required.
* Let the module run its import-time safety engine construction against
  the stubbed classes.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List

import pytest


# ---------------------------------------------------------------------------
# Module loading helper with full dependency isolation
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parents[3]
SAFETY_APP = str(REPO_ROOT / "safety" / "app")


def _install_stub_safety_package(
    created: Dict[str, Any],
) -> ModuleType:
    """Create a stub ``nemoguardrails`` package and register it in sys.modules.

    ``from_path`` just records the path and returns a config-like
    object. ``LLMRails.generate_async`` is a coroutine that echoes the user
    input, which the real package does when inputs are considered safe.
    """

    class _RailsConfig:
        def __init__(self, config_path: str) -> None:
            self.config_path = config_path
            # Mirror the real type's ``.models`` structure so
            # ``apply_endpoint_overrides`` could operate on it if invoked.
            self.models = []

        @classmethod
        def from_path(cls, path: str) -> "_RailsConfig":
            created["from_path_arg"] = path
            return cls(path)

    class _LLMRails:
        def __init__(self, config: Any) -> None:
            created.setdefault("safety_engine_instances", []).append(config)
            self._generate_result: Dict[str, Any] | None = None

        def configure_result(self, result: Dict[str, Any]) -> None:
            self._generate_result = result

        async def generate_async(
            self, messages: List[Dict[str, Any]], options: Dict[str, Any]
        ) -> Dict[str, Any]:
            created.setdefault("calls", []).append(
                {"messages": messages, "options": options}
            )
            if self._generate_result is not None:
                return self._generate_result
            # Default: echo the last user message as assistant content.
            last = messages[-1]
            return {
                "response": [
                    {"role": "assistant", "content": last["content"]}
                ]
            }

    fake_module = ModuleType("nemoguardrails")
    fake_module.RailsConfig = _RailsConfig
    fake_module.LLMRails = _LLMRails

    sys.modules["nemoguardrails"] = fake_module
    return fake_module


@pytest.fixture
def engine_module(monkeypatch: pytest.MonkeyPatch):
    """Import ``safety.app.engine`` with all external deps stubbed out.

    The fixture rebuilds a fresh module per test so state from one case
    never leaks into another.
    """
    created: Dict[str, Any] = {}
    _install_stub_safety_package(created)


    # Force a fresh import of both names to pick up our injected stubs.
    for name in ("safety.app.engine", "safety.app.endpoint_overrides"):
        sys.modules.pop(name, None)

    import importlib

    engine_module = importlib.import_module("safety.app.engine")
    # Attach the recorder to the module for per-test access.
    engine_module._test_created = created  # type: ignore[attr-defined]

    yield engine_module

    # Clean up import cache so other test files get a pristine module.
    for name in ("safety.app.engine", "safety.app.endpoint_overrides"):
        sys.modules.pop(name, None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestModuleImportWiring:
    def test_module_exposes_engine_singleton(
        self, engine_module
    ) -> None:
        assert hasattr(engine_module, "_content_safety")
        assert isinstance(engine_module._content_safety, engine_module.ContentSafety)

    def test_factory_returns_singleton(
        self, engine_module
    ) -> None:
        engine = engine_module.SafetyEngineFactory().create()
        assert engine is engine_module._content_safety

    def test_config_from_path_called_with_container_path(
        self, engine_module
    ) -> None:
        created = engine_module._test_created
        # Singleton is built in the module body with this hardcoded path.
        assert created["from_path_arg"] == "/app/platform/configs/safety"


class TestContentSafetyBase:
    async def test_base_methods_are_noops(self, engine_module) -> None:
        base = engine_module.ContentSafetyBase()
        assert await base.call_input_safety("hi") is None
        assert await base.call_output_safety("hi") is None


class TestContentSafety:
    async def test_input_check_generates_with_input_safety_option(
        self, engine_module
    ) -> None:
        safety_engine = engine_module._content_safety
        result = await safety_engine.call_input_safety("hello")

        # Default stub echoes the input back as the assistant message.
        assert result["response"][0]["content"] == "hello"

        calls = engine_module._test_created["calls"]
        assert calls[-1]["options"] == {"rails": ["input"]}
        assert calls[-1]["messages"] == [
            {"role": "user", "content": "hello"}
        ]

    async def test_output_check_builds_expected_messages_shape(
        self, engine_module
    ) -> None:
        safety_engine = engine_module._content_safety
        await safety_engine.call_output_safety("safe bot response")

        calls = engine_module._test_created["calls"]
        assert calls[-1]["options"] == {"rails": ["output"]}
        assert calls[-1]["messages"] == [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "safe bot response"},
        ]

    async def test_unsafe_input_rewrites_response(
        self, engine_module
    ) -> None:
        # Configure the stub LLMRails to simulate an unsafe classification.
        safety_engine = engine_module._content_safety
        safety_engine.app.configure_result(
            {
                "response": [
                    {"role": "assistant", "content": "I can't help with that."}
                ]
            }
        )

        result = await safety_engine.call_input_safety("prompt injection attempt")
        assert result["response"][0]["content"] == "I can't help with that."
