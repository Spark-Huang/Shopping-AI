
"""Unit tests for ``orchestrator.app.config``.

The config module drives every downstream agent's construction. These tests
exercise both the on-disk YAML override flow and the pydantic validation
contract directly, without touching the real container layout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml
from pydantic import ValidationError

from orchestrator.app.settings import (
    OrchestratorConfig,
    load_config,
    load_config_with_override,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def write_yaml(tmp_path: Path):
    """Helper to drop a YAML config into a temporary directory."""

    def _write(name: str, data: Dict[str, Any]) -> Path:
        path = tmp_path / name
        path.write_text(yaml.safe_dump(data))
        return path

    return _write


class TestLoadConfigWithOverride:
    def test_returns_base_config_when_no_override_set(
        self, monkeypatch: pytest.MonkeyPatch, write_yaml, valid_config_dict: dict
    ) -> None:
        monkeypatch.delenv("CONFIG_OVERRIDE", raising=False)
        base_path = write_yaml("config.yaml", valid_config_dict)

        result = load_config_with_override(str(base_path))

        assert result == valid_config_dict

    def test_raises_file_not_found_for_missing_base_config(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.yaml"
        with pytest.raises(FileNotFoundError):
            load_config_with_override(str(missing))

    def test_applies_top_level_override(
        self, monkeypatch: pytest.MonkeyPatch, write_yaml, valid_config_dict: dict
    ) -> None:
        base_path = write_yaml("config.yaml", valid_config_dict)
        write_yaml(
            "config-build.yaml",
            {
                "llm_port": "https://gateway.example.com/v1",
                "llm_name": "overridden-model",
            },
        )
        monkeypatch.setenv("CONFIG_OVERRIDE", "config-build.yaml")

        merged = load_config_with_override(str(base_path))

        assert merged["llm_port"] == "https://gateway.example.com/v1"
        assert merged["llm_name"] == "overridden-model"
        # Base-only fields survive the shallow merge.
        assert merged["memory_base_url"] == valid_config_dict["memory_base_url"]
        assert merged["categories"] == valid_config_dict["categories"]

    def test_override_is_shallow_not_deep_merge(
        self, monkeypatch: pytest.MonkeyPatch, write_yaml, valid_config_dict: dict
    ) -> None:
        # Document that nested keys under a shared top-level key are replaced
        # wholesale (not merged). A regression to deep-merge would change
        # deployment behaviour and should surface in CI.
        base = {**valid_config_dict, "categories": ["bag", "shoes", "dress"]}
        base_path = write_yaml("config.yaml", base)
        write_yaml(
            "config-build.yaml",
            {"categories": ["sunglasses"]},
        )
        monkeypatch.setenv("CONFIG_OVERRIDE", "config-build.yaml")

        merged = load_config_with_override(str(base_path))

        assert merged["categories"] == ["sunglasses"]

    def test_missing_override_file_is_tolerated(
        self, monkeypatch: pytest.MonkeyPatch, write_yaml, valid_config_dict: dict
    ) -> None:
        base_path = write_yaml("config.yaml", valid_config_dict)
        monkeypatch.setenv("CONFIG_OVERRIDE", "missing-override.yaml")

        merged = load_config_with_override(str(base_path))

        assert merged == valid_config_dict


class TestOrchestratorConfigValidation:
    def test_valid_dict_constructs_successfully(self, valid_config_dict: dict) -> None:
        config = OrchestratorConfig(**valid_config_dict)

        assert config.llm_port == valid_config_dict["llm_port"]
        assert config.categories == valid_config_dict["categories"]
        assert config.multimodal is True

    @pytest.mark.parametrize(
        "missing_field",
        [
            "llm_port",
            "llm_name",
            "retriever_port",
            "memory_base_url",
            "safety_base_url",
            "routing_prompt",
            "chatter_prompt",
            "categories",
            "agent_choices",
            "memory_length",
            "top_k_retrieve",
            "multimodal",
            "unsafe_messages",
        ],
    )
    def test_missing_required_field_fails(
        self, valid_config_dict: dict, missing_field: str
    ) -> None:
        bad = dict(valid_config_dict)
        del bad[missing_field]
        with pytest.raises(ValidationError):
            OrchestratorConfig(**bad)

    @pytest.mark.parametrize(
        "url_field",
        ["llm_port", "retriever_port", "memory_base_url", "safety_base_url"],
    )
    def test_url_validator_rejects_non_http_schemes(
        self, valid_config_dict: dict, url_field: str
    ) -> None:
        bad = {**valid_config_dict, url_field: "not-a-url"}
        with pytest.raises(ValidationError):
            OrchestratorConfig(**bad)

    @pytest.mark.parametrize(
        "url_field,value",
        [
            ("llm_port", "http://localhost:8000"),
            ("retriever_port", "https://example.com"),
        ],
    )
    def test_url_validator_accepts_http_and_https(
        self, valid_config_dict: dict, url_field: str, value: str
    ) -> None:
        cfg = OrchestratorConfig(**{**valid_config_dict, url_field: value})
        assert getattr(cfg, url_field) == value

    @pytest.mark.parametrize("value", [0, -1, -100])
    def test_memory_length_must_be_positive(
        self, valid_config_dict: dict, value: int
    ) -> None:
        with pytest.raises(ValidationError):
            OrchestratorConfig(**{**valid_config_dict, "memory_length": value})

    @pytest.mark.parametrize("value", [0, -4])
    def test_top_k_retrieve_must_be_positive(
        self, valid_config_dict: dict, value: int
    ) -> None:
        with pytest.raises(ValidationError):
            OrchestratorConfig(**{**valid_config_dict, "top_k_retrieve": value})

    @pytest.mark.parametrize("field", ["categories", "agent_choices"])
    def test_empty_list_fields_are_rejected(
        self, valid_config_dict: dict, field: str
    ) -> None:
        with pytest.raises(ValidationError):
            OrchestratorConfig(**{**valid_config_dict, field: []})

    def test_extra_fields_are_forbidden(self, valid_config_dict: dict) -> None:
        with pytest.raises(ValidationError):
            OrchestratorConfig(**valid_config_dict, unexpected_field="oops")


class TestLoadConfig:
    # Hermetic: LLM_BASE_URL (loaded from .env by the test runner) would
    # otherwise override llm_port via the decision-4A env injection path.
    @pytest.fixture(autouse=True)
    def _isolate_gateway_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLM_BASE_URL", raising=False)

    def test_returns_typed_orchestrator_config(
        self, write_yaml, valid_config_dict: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CONFIG_OVERRIDE", raising=False)
        path = write_yaml("config.yaml", valid_config_dict)

        config = load_config(str(path))

        assert isinstance(config, OrchestratorConfig)
        assert config.memory_length == valid_config_dict["memory_length"]

    def test_invalid_yaml_surface_as_value_error(
        self, write_yaml, valid_config_dict: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CONFIG_OVERRIDE", raising=False)
        bad = dict(valid_config_dict)
        bad["llm_port"] = "not-a-url"
        path = write_yaml("config.yaml", bad)

        with pytest.raises(ValueError):
            load_config(str(path))


class TestRepoPromptContracts:
    def test_budget_only_browse_routes_to_chatter_for_clarification(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CONFIG_OVERRIDE", raising=False)
        config = load_config_with_override(
            str(REPO_ROOT / "platform/configs/orchestrator/config.yaml")
        )

        routing_prompt = config["routing_prompt"]

        assert "UNDERSPECIFIED SHOPPING CONSTRAINTS -> chatter" in routing_prompt
        assert "show me anything under ¥100" in routing_prompt
        assert "show me Guizhou tea under ¥100" in routing_prompt
        assert "IMAGE ATTACHED is yes" in routing_prompt

    def test_chatter_asks_clarification_before_no_results(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CONFIG_OVERRIDE", raising=False)
        config = load_config_with_override(
            str(REPO_ROOT / "platform/configs/orchestrator/config.yaml")
        )

        chatter_prompt = config["chatter_prompt"]

        assert "AMBIGUITY BEFORE RESULTS" in chatter_prompt
        assert "NO RESULTS AFTER RETRIEVAL" in chatter_prompt
        assert "ask one concise clarifying question" in chatter_prompt


class TestEnvEndpointInjection:
    """Decision 4A: LLM_BASE_URL overrides the tracked YAML placeholder."""

    @pytest.fixture(autouse=True)
    def _isolate_gateway_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LLM_BASE_URL", raising=False)

    def test_llm_base_url_env_overrides_yaml_llm_port(
        self, write_yaml, valid_config_dict: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CONFIG_OVERRIDE", raising=False)
        path = write_yaml("config.yaml", {**valid_config_dict, "llm_port": "http://llm-gateway:8000/v1"})

        config = load_config(str(path))

        # Without the env var the neutral placeholder passes through.
        assert config.llm_port == "http://llm-gateway:8000/v1"

        monkeypatch.setenv("LLM_BASE_URL", "http://real-gateway.example.com:1234/v1")
        config = load_config(str(path))
        assert config.llm_port == "http://real-gateway.example.com:1234/v1"

    def test_llm_base_url_env_beats_config_override_file(
        self, write_yaml, valid_config_dict: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Env injection must have the final word over CONFIG_OVERRIDE too,
        # since compose passes .env values via environment.
        monkeypatch.setenv("CONFIG_OVERRIDE", "config-build.yaml")
        monkeypatch.setenv("LLM_BASE_URL", "http://env-wins.example.com/v1")
        write_yaml("config.yaml", valid_config_dict)
        write_yaml("config-build.yaml", {"llm_port": "http://override-file.example.com/v1"})
        path = write_yaml(
            "config.yaml",
            {**valid_config_dict, "llm_port": "http://llm-gateway:8000/v1"},
        )

        config = load_config(str(path))

        assert config.llm_port == "http://env-wins.example.com/v1"

    def test_repo_config_carries_no_private_gateway_hosts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regression guard for decision 4A: the tracked config must only
        # contain the neutral placeholder, never a private host/port.
        monkeypatch.delenv("CONFIG_OVERRIDE", raising=False)
        config = load_config_with_override(
            str(REPO_ROOT / "platform/configs/orchestrator/config.yaml")
        )

        assert config["llm_port"] == "http://llm-gateway:8000/v1"


class TestChatterMaxTokensSplit:
    """Decision 5 / P2-3: memory_length vs chatter_max_tokens semantics."""

    def test_chatter_max_tokens_defaults_to_none(
        self, valid_config_dict: dict
    ) -> None:
        config = OrchestratorConfig(**valid_config_dict)
        assert config.chatter_max_tokens is None

    def test_chatter_max_tokens_can_be_set_independently(
        self, valid_config_dict: dict
    ) -> None:
        config = OrchestratorConfig(
            **{**valid_config_dict, "memory_length": 4096, "chatter_max_tokens": 2048}
        )
        assert config.memory_length == 4096
        assert config.chatter_max_tokens == 2048

    @pytest.mark.parametrize("value", [0, -1])
    def test_chatter_max_tokens_must_be_positive_when_set(
        self, valid_config_dict: dict, value: int
    ) -> None:
        with pytest.raises(ValidationError):
            OrchestratorConfig(**{**valid_config_dict, "chatter_max_tokens": value})


class TestSmallLlmNameRouting:
    """Decision 3A (Round 6): optional small/fast model for front-of-pipeline tasks."""

    def test_small_llm_name_defaults_to_none(self, valid_config_dict: dict) -> None:
        config = OrchestratorConfig(**valid_config_dict)
        assert config.small_llm_name is None

    def test_small_llm_name_can_be_set(self, valid_config_dict: dict) -> None:
        config = OrchestratorConfig(**{**valid_config_dict, "small_llm_name": "zai/glm-5"})
        assert config.small_llm_name == "zai/glm-5"
        assert config.llm_name == valid_config_dict["llm_name"]

    def test_extra_fields_still_forbidden(self, valid_config_dict: dict) -> None:
        with pytest.raises(ValidationError):
            OrchestratorConfig(**{**valid_config_dict, "not_a_real_field": "x"})

    def test_load_config_env_override_injects_small_llm_name(
        self, monkeypatch: pytest.MonkeyPatch, valid_config_dict: dict, write_yaml
    ) -> None:
        base_path = write_yaml("config.yaml", valid_config_dict)
        monkeypatch.delenv("CONFIG_OVERRIDE", raising=False)
        monkeypatch.setenv("SMALL_LLM_NAME", "zai/glm-5")
        monkeypatch.setenv("LLM_NAME", "env-model")
        monkeypatch.setenv("LLM_BASE_URL", "http://env-gateway:9000/v1")

        config = load_config(str(base_path))

        assert config.small_llm_name == "zai/glm-5"
        assert config.llm_name == "env-model"
        assert config.llm_port == "http://env-gateway:9000/v1"
