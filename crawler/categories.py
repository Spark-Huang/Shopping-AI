"""Category vocabulary shared by the crawler and product index."""

from __future__ import annotations

CATEGORY_KEYWORDS: tuple[str, ...] = (
    "thermos cup",
    "headphones",
    "phone case",
    "backpack",
    "storage box",
    "stationery",
    "beauty",
    "dress",
    "skirt",
    "kitchenware",
    "toys",
    "pet supplies",
    "lighting",
)


def normalize_keyword(keyword: str | None) -> str:
    value = " ".join((keyword or "").strip().split())
    return value or "thermos cup"


def category_for(keyword: str) -> str:
    normalized = normalize_keyword(keyword).lower()
    aliases = {
        "cup": "thermos cup",
        "water bottle": "thermos cup",
        "earbuds": "headphones",
        "women clothing": "dress",
        "women's clothing": "dress",
        "skirt": "dress",
        "midi skirt": "skirt",
        "中裙": "skirt",
        "半身裙": "skirt",
        "中长半身裙": "skirt",
        "dress skirt": "dress",
        "半身裙": "dress",
        "中长半身裙": "dress",
        "连衣裙": "dress",
        "home storage": "storage box",
    }
    value = aliases.get(normalized, normalized)
    return value if value in CATEGORY_KEYWORDS else "other"
