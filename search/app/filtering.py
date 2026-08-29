"""Catalog result category and structured filters."""

from __future__ import annotations

from typing import Any


USD_TO_CNY = 7.2


def query_currency(filters: dict[str, Any]) -> str:
    currency = filters.get("currency")
    return str(currency).upper() if currency else "CNY"


def extract_product_categories(document: Any) -> list[str]:
    try:
        category_part = document.page_content.split("|")[-1].strip()
        if "PRICE:" in category_part:
            category_part = category_part.split("PRICE:")[0].strip()
        return [
            part.strip().lower()
            for part in category_part.split(",")
            if part.strip() and not part.strip().startswith("/")
        ]
    except Exception:
        return []


def matches_categories(document: Any, categories: list[str]) -> bool:
    product_categories = extract_product_categories(document)
    return any(
        user_category.lower().strip() in product_category
        or product_category in user_category.lower().strip()
        for user_category in categories
        for product_category in product_categories
    )


def milvus_category_expr(categories: list[str]) -> str:
    def quote(category: str) -> str:
        escaped = category.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    values = ", ".join(
        quote(category.strip().lower()) for category in categories if category.strip()
    )
    if not values:
        return ""
    return f"subcategory in [{values}]"


def coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def apply_structured_filters(
    results: list[tuple[Any, float]],
    filters: dict[str, Any] | None,
    verbose: bool = False,
) -> list[tuple[Any, float]]:
    if not filters:
        return results

    min_price = coerce_float(filters.get("min_price"))
    max_price = coerce_float(filters.get("max_price"))
    if min_price is None and max_price is None:
        return results

    currency = query_currency(filters)
    result_currency = next(
        (
            str(result[0].metadata.get("currency", "CNY")).upper()
            for result in results
        ),
        "CNY",
    )
    if currency != result_currency:
        if currency == "USD" and result_currency == "CNY":
            conversion = USD_TO_CNY
            min_price = min_price * conversion if min_price is not None else None
            max_price = max_price * conversion if max_price is not None else None
        elif currency == "CNY" and result_currency == "USD":
            min_price = min_price * USD_TO_CNY if min_price is not None else None
            max_price = max_price * USD_TO_CNY if max_price is not None else None

    filtered_results = []
    for result in results:
        document = result[0]
        price = coerce_float(document.metadata.get("price"))
        if price is None:
            continue
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        filtered_results.append(result)

    if verbose:
        print(
            f"Structured filters: {filters}; kept "
            f"{len(filtered_results)}/{len(results)} results"
        )
    return filtered_results
