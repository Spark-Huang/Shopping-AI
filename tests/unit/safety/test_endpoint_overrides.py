
"""Unit tests for ``safety.app.endpoint_overrides``.

The module is a small helper that mutates a configuration-shaped object
with base URL overrides from a YAML file. We test it using lightweight
stand-in objects so no ``nemoguardrails`` installation is required at
import time.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
import yaml

from safety.app.endpoint_overrides import apply_endpoint_overrides


def _make_config(model_entries: List[Dict[str, Any]]) -> SimpleNamespace:
    """Build a configuration-like object with ``models`` attribute.

    Each model exposes ``type`` and a mutable ``parameters`` dict so we can
    observe updates done by ``apply_endpoint_overrides``.
    """
    models = [
        SimpleNamespace(
            type=entry["type"],
            model=entry.get("model", "original-model"),
            parameters=dict(entry.get("parameters", {})),
        )
        for entry in model_entries
    ]
    return SimpleNamespace(models=models)


class TestApplyEndpointOverrides:
    def test_safety_model_name_comes_from_environment(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.delenv("CONFIG_OVERRIDE", raising=False)
        monkeypatch.setenv("SAFETY_NAME", "gpt-5.5")
        config = SimpleNamespace(
            models=[
                SimpleNamespace(
                    type="main",
                    engine="openai",
                    model="legacy-model",
                    parameters={},
                )
            ]
        )

        apply_endpoint_overrides(config, config_dir=str(tmp_path))

        assert config.models[0].model == "gpt-5.5"

    def test_no_override_env_leaves_config_untouched(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.delenv("CONFIG_OVERRIDE", raising=False)
        config = _make_config(
            [{"type": "main", "parameters": {"base_url": "http://default"}}]
        )

        apply_endpoint_overrides(config, config_dir=str(tmp_path))

        assert config.models[0].parameters["base_url"] == "http://default"

    def test_missing_override_file_is_tolerated(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("CONFIG_OVERRIDE", "missing.yaml")
        config = _make_config(
            [{"type": "main", "parameters": {"base_url": "http://default"}}]
        )

        apply_endpoint_overrides(config, config_dir=str(tmp_path))

        # No exception; config untouched.
        assert config.models[0].parameters["base_url"] == "http://default"

    def test_override_updates_matching_model_base_url(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        override_path = tmp_path / "override.yaml"
        override_path.write_text(
            yaml.safe_dump(
                {
                    "models": [
                        {
                            "type": "main",
                            "parameters": {
                                "base_url": "https://gateway.example.com/v1",
                            },
                        }
                    ]
                }
            )
        )
        monkeypatch.setenv("CONFIG_OVERRIDE", "override.yaml")
        config = _make_config(
            [{"type": "main", "parameters": {"base_url": "http://default"}}]
        )

        apply_endpoint_overrides(config, config_dir=str(tmp_path))

        assert (
            config.models[0].parameters["base_url"]
            == "https://gateway.example.com/v1"
        )

    def test_override_of_non_matching_type_is_ignored(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        override_path = tmp_path / "override.yaml"
        override_path.write_text(
            yaml.safe_dump(
                {
                    "models": [
                        {
                            "type": "content-safety",
                            "parameters": {"base_url": "https://safety"},
                        }
                    ]
                }
            )
        )
        monkeypatch.setenv("CONFIG_OVERRIDE", "override.yaml")
        config = _make_config(
            [{"type": "main", "parameters": {"base_url": "http://default"}}]
        )

        apply_endpoint_overrides(config, config_dir=str(tmp_path))

        # No matching type → nothing to update.
        assert config.models[0].parameters["base_url"] == "http://default"

    def test_override_without_base_url_is_skipped(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        override_path = tmp_path / "override.yaml"
        override_path.write_text(
            yaml.safe_dump(
                {
                    "models": [
                        {
                            "type": "main",
                            "parameters": {"other_param": "x"},
                        }
                    ]
                }
            )
        )
        monkeypatch.setenv("CONFIG_OVERRIDE", "override.yaml")
        config = _make_config(
            [{"type": "main", "parameters": {"base_url": "http://default"}}]
        )

        apply_endpoint_overrides(config, config_dir=str(tmp_path))

        assert config.models[0].parameters["base_url"] == "http://default"

    def test_override_without_models_key_is_noop(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        override_path = tmp_path / "override.yaml"
        override_path.write_text(yaml.safe_dump({"other_key": "value"}))
        monkeypatch.setenv("CONFIG_OVERRIDE", "override.yaml")
        config = _make_config(
            [{"type": "main", "parameters": {"base_url": "http://default"}}]
        )

        apply_endpoint_overrides(config, config_dir=str(tmp_path))

        assert config.models[0].parameters["base_url"] == "http://default"

    def test_multiple_models_update_first_match_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        override_path = tmp_path / "override.yaml"
        override_path.write_text(
            yaml.safe_dump(
                {
                    "models": [
                        {
                            "type": "main",
                            "parameters": {"base_url": "https://new"},
                        }
                    ]
                }
            )
        )
        monkeypatch.setenv("CONFIG_OVERRIDE", "override.yaml")
        config = _make_config(
            [
                {"type": "main", "parameters": {"base_url": "http://default1"}},
                {"type": "main", "parameters": {"base_url": "http://default2"}},
            ]
        )

        apply_endpoint_overrides(config, config_dir=str(tmp_path))

        # The function breaks after the first match; the second stays put.
        assert config.models[0].parameters["base_url"] == "https://new"
        assert config.models[1].parameters["base_url"] == "http://default2"


# ---------------------------------------------------------------------------
# safety hooks compatibility smoke test
# ---------------------------------------------------------------------------


class TestSafetyHooksSmoke:
    """Smoke-test the auto-loaded ``platform/configs/safety/safety_hooks.py`` shim.

    The compatibility module is executed by ``LLMRails.__init__`` next to the safety YAML
    configuration; it monkey-patches the safety framework so the local
    OpenAI-compatible gateway accepts the built-in safety-check LLM calls.
    These checks run the *real shim file* (via ``exec`` against a temporary
    module) with stubbed ``nemoguardrails`` packages, mirroring the stub
    approach used throughout this suite -- no real nemoguardrails install or
    network access is required. We assert that importing the shim leaves the
    patch marker on the wrapped ``llm_call``, i.e. the temperature/stream
    compatibility patches were actually installed at import time.
    """

    @staticmethod
    def _install_stub_safety_package(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
        """Install minimal fake ``nemoguardrails.*`` modules in ``sys.modules``.

        Returns a registry dict whose ``"original_llm_call"`` entry holds the
        fake source ``llm_call`` coroutine function the shim should wrap.
        """
        import importlib.util
        import sys
        import types

        async def original_llm_call(*args: Any, **kwargs: Any) -> str:
            return "ok"

        llm_utils = types.ModuleType("nemoguardrails.actions.llm.utils")
        llm_utils.llm_call = original_llm_call  # type: ignore[attr-defined]

        actions_pkg = types.ModuleType("nemoguardrails.actions")
        actions_llm_pkg = types.ModuleType("nemoguardrails.actions.llm")
        cs_actions = types.ModuleType(
            "nemoguardrails.library.content_safety.actions"
        )
        cs_actions.llm_call = original_llm_call  # type: ignore[attr-defined]

        library_pkg = types.ModuleType("nemoguardrails.library")
        content_safety_pkg = types.ModuleType(
            "nemoguardrails.library.content_safety"
        )

        class OpenAICompatibleClient:  # pragma: no cover - attribute holder
            pass

        og_client_module = types.ModuleType(
            "nemoguardrails.llm.clients.openai_compatible"
        )
        setattr(og_client_module, "OpenAICompatibleClient", OpenAICompatibleClient)

        modules = {
            "nemoguardrails": types.ModuleType("nemoguardrails"),
            "nemoguardrails.actions": actions_pkg,
            "nemoguardrails.actions.llm": actions_llm_pkg,
            "nemoguardrails.actions.llm.utils": llm_utils,
            "nemoguardrails.library": library_pkg,
            "nemoguardrails.library.content_safety": content_safety_pkg,
            "nemoguardrails.library.content_safety.actions": cs_actions,
            "nemoguardrails.llm": types.ModuleType("nemoguardrails.llm"),
            "nemoguardrails.llm.clients": types.ModuleType(
                "nemoguardrails.llm.clients"
            ),
            "nemoguardrails.llm.clients.openai_compatible": og_client_module,
        }
        for name, module in modules.items():
            monkeypatch.setitem(sys.modules, name, module)
        return {"original_llm_call": original_llm_call}

    def test_shim_import_applies_patch_markers(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Executing the shim file must wrap ``llm_call`` with the marker."""
        import asyncio
        import importlib.util
        import sys

        registry = self._install_stub_safety_package(monkeypatch)

        # Load the production shim by file path into a throwaway module --
        # this mirrors how the safety framework executes config.py next to the YAML
        # (the configs tree is data, not a package, so there is no importable
        # ``platform.configs.safety`` module).
        shim_path = (
            Path(__file__).resolve().parents[3]
            / "platform" / "configs" / "safety" / "safety_hooks.py"
        )
        assert shim_path.is_file(), f"shim not found: {shim_path}"
        spec = importlib.util.spec_from_file_location(
            "_safety_config_smoke", shim_path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # runs _apply() at import time

        patched = getattr(
            sys.modules["nemoguardrails.actions.llm.utils"], "llm_call"
        )
        assert getattr(patched, "_content_safety_compat_applied", False) is True
        # The wrapper must still delegate to the original implementation.
        assert asyncio.run(patched()) == "ok"
        assert registry["original_llm_call"] is not None


class TestNeutralDefaultBaseURL:
    """Decision 4A: no private gateway hosts hard-coded in tracked files."""

    def test_default_base_url_is_neutral_placeholder(self) -> None:
        from safety.app.endpoint_overrides import DEFAULT_BASE_URL

        assert DEFAULT_BASE_URL == "http://llm-gateway:8000/v1"
        assert "host.docker.internal" not in DEFAULT_BASE_URL
        assert "20128" not in DEFAULT_BASE_URL

    def test_safety_base_url_env_wins_when_model_has_no_explicit_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # _inject_openai_params reads SAFETY_BASE_URL from the environment;
        # unset parameters must receive the env value.
        monkeypatch.delenv("CONFIG_OVERRIDE", raising=False)
        monkeypatch.setenv("SAFETY_BASE_URL", "http://real-safety-gateway.example.com/v1")
        monkeypatch.setenv("SAFETY_API_KEY", "test-key")

        from safety.app.endpoint_overrides import _inject_openai_params

        model = SimpleNamespace(
            type="main", engine="openai", parameters=None
        )
        config = SimpleNamespace(models=[model])

        _inject_openai_params(config)

        assert model.parameters["base_url"] == "http://real-safety-gateway.example.com/v1"
        assert model.parameters["api_key"] == "test-key"


class TestSafetyYamlShape:
    """Guard against using configuration keys ignored by NeMo Guardrails."""

    def test_safety_config_declares_native_rails(self) -> None:
        config_path = (
            Path(__file__).resolve().parents[3]
            / "platform"
            / "configs"
            / "safety"
            / "config.yml"
        )
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

        assert "rails" in config
        assert "safety" not in config
        assert config["rails"]["input"]["flows"]
        assert config["rails"]["output"]["flows"]
