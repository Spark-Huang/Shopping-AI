"""Persisted shopping-region configuration."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_REGION = "贵州"
SUPPORTED_REGIONS = (
    "贵州",
    "云南",
    "四川",
    "重庆",
    "广东",
    "北京",
    "上海",
)


def _region_file() -> Path:
    return Path(os.environ.get("REGION_FILE", "/tmp/shopping-ai-region"))


def load_region() -> str:
    try:
        value = _region_file().read_text(encoding="utf-8").strip()
        if value in SUPPORTED_REGIONS:
            return value
    except OSError:
        pass
    return os.environ.get("SHOPPING_REGION", DEFAULT_REGION)


def save_region(value: str) -> str:
    if value not in SUPPORTED_REGIONS:
        raise ValueError("region is not supported")
    region_file = _region_file()
    region_file.parent.mkdir(parents=True, exist_ok=True)
    region_file.write_text(value, encoding="utf-8")
    return value
