"""Yiwugo search API parser and CSRF fetch orchestration."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

from crawler.dangdang import Product

BASE_URL = "https://www.yiwugo.com"
SUCCESS_CODE = "1"


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(match.group()) if match else None


def _int(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def parse_item(raw: dict[str, Any], category: str, subcategory: str) -> Product | None:
    sku = _int(raw.get("id"))
    name = _clean(raw.get("title"))
    if not sku or not name:
        return None
    price_fen = _number(raw.get("sellPrice"))
    price = price_fen / 100 if price_fen is not None else None
    return Product(
        name=name,
        description=_clean(raw.get("shopName")),
        url=f"{BASE_URL}/product/detail/{sku}.html",
        price=price,
        currency="CNY" if price is not None else None,
        image=_clean(raw.get("picture1")),
        category=category,
        subcategory=subcategory,
        platform="yiwugo",
    )


def parse_products(
    payload: str | dict[str, Any], category: str, subcategory: str = "other"
) -> list[Product]:
    try:
        data = payload if isinstance(payload, dict) else json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, dict) or str(data.get("code")) != SUCCESS_CODE:
        return []
    rows = (data.get("content") or {}).get("prslist") or []
    return [
        product
        for row in rows
        if isinstance(row, dict)
        for product in [parse_item(row, category, subcategory)]
        if product is not None
    ]


class YiwugoFetcher:
    def __init__(self, fetcher: Any) -> None:
        self.fetcher = fetcher

    def _token(self, keyword: str) -> str:
        self.fetcher.fetch(f"{BASE_URL}/search?q={quote(keyword)}")
        token = self.fetcher.client.cookies.get("csrfToken")
        if not token:
            raise RuntimeError("csrfToken cookie missing after Yiwugo seed request")
        return token

    def fetch_page(self, keyword: str, page: int = 1) -> dict[str, Any]:
        token = self._token(keyword)
        url = f"{BASE_URL}/api/search/s.htm?q={quote(keyword)}&pageSize=60&page={max(1, page)}"
        headers = {
            "x-csrf-token": token,
            "x-requested-with": "XMLHttpRequest",
            "referer": f"{BASE_URL}/search?q={quote(keyword)}",
            "accept": "application/json, text/plain, */*",
        }
        data = json.loads(self.fetcher.fetch(url, extra_headers=headers))
        if str(data.get("code")) != SUCCESS_CODE:
            headers["x-csrf-token"] = self._token(keyword)
            data = json.loads(self.fetcher.fetch(url, extra_headers=headers))
        if str(data.get("code")) != SUCCESS_CODE:
            raise RuntimeError(f"Yiwugo API business error: {data.get('msg')}")
        return data
