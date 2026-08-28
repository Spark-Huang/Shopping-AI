"""Search service configuration loading."""

from __future__ import annotations

import os
from typing import Any

import yaml


def load_config_with_overrides(base_config_path: str) -> dict[str, Any]:
    if not os.path.exists(base_config_path):
        raise FileNotFoundError(f"Base config file not found at {base_config_path}")

    with open(base_config_path, "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    override_file = os.environ.get("CONFIG_OVERRIDE")
    if override_file:
        override_path = os.path.join(
            os.path.dirname(base_config_path), override_file
        )
        if os.path.exists(override_path):
            with open(override_path, "r", encoding="utf-8") as file_handle:
                config.update(yaml.safe_load(file_handle))

    return config


def search_config_path() -> str:
    shared_config_root = os.environ.get("SHARED_CONFIG_ROOT", "/app/platform/configs")
    return os.path.join(shared_config_root, "search", "config.yaml")


def apply_endpoint_overrides(data: dict[str, Any]) -> dict[str, Any]:
    endpoint = os.environ.get("EMBED_BASE_URL") or os.environ.get("LLM_BASE_URL")
    if endpoint:
        for config_key in ("text_embed_port", "image_embed_port"):
            if data.get(config_key):
                data[config_key] = endpoint
    return data
