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
        "home storage": "storage box",
    }
    value = aliases.get(normalized, normalized)
    return value if value in CATEGORY_KEYWORDS else "other"
