import logging
import re
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter

_PRICE_PATTERN = re.compile(r"PRICE:\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


def _extract_price(catalog_text: Optional[str]) -> Optional[float]:
    if not catalog_text:
        return None
    match = _PRICE_PATTERN.search(catalog_text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


def _normalize_name(name: str) -> str:
    if not name:
        return ""
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _resolve_catalog_match(
    query_name: str,
    catalog_names: list,
    similarities: list,
    min_similarity: float = 0.5,
    min_token_overlap: float = 0.5,
) -> Optional[int]:
    if not catalog_names:
        return None
    q_norm = _normalize_name(query_name)
    if not q_norm:
        if similarities and similarities[0] >= min_similarity:
            return 0
        return None
    q_tokens = set(q_norm.split())
    best_overlap = 0.0
    best_idx: Optional[int] = None
    for idx, candidate in enumerate(catalog_names):
        c_norm = _normalize_name(candidate)
        if not c_norm:
            continue
        if q_norm == c_norm or q_norm in c_norm or c_norm in q_norm:
            return idx
        c_tokens = set(c_norm.split())
        if not c_tokens or not q_tokens:
            continue
        overlap = len(q_tokens & c_tokens) / len(q_tokens | c_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_idx = idx
    if best_idx is not None and best_overlap >= min_token_overlap:
        return best_idx
    if similarities and similarities[0] >= min_similarity:
        return 0
    return None


class CatalogMatchMixin:
    def _lookup_in_catalog(self, item_name: str) -> Optional[Dict[str, Any]]:
        """Look up a product in the catalog by name.

        Returns ``{"name", "text", "similarity", "url"}`` for the best match per
        ``_resolve_catalog_match`` or None. ``k`` is widened so the right
        record is present even when embedding similarity ranks it below
        the top hit.
        """
        adapter = HTTPAdapter(max_retries=self.retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        logging.info(f"CartAgent._lookup_in_catalog() | /query/text -- query: {item_name}")
        ret_response = session.post(
            f"{self.search_url}/query/text",
            json={
                "text": [item_name],
                "categories": self.categories,
                "k": self._CATALOG_LOOKUP_K,
            },
        )
        ret_response.raise_for_status()
        res_json = ret_response.json()
        names = res_json.get("names") or []
        similarities = res_json.get("similarities") or []
        texts = res_json.get("texts") or []
        urls = res_json.get("urls") or []

        match_idx = _resolve_catalog_match(item_name, names, similarities)
        if match_idx is None:
            logging.info(
                f"CartAgent._lookup_in_catalog() | no match for '{item_name}' "
                f"(candidates={names[:self._CATALOG_LOOKUP_K]}, sims={similarities[:self._CATALOG_LOOKUP_K]})"
            )
            return None

        similarity = similarities[match_idx] if match_idx < len(similarities) else 0.0
        text = texts[match_idx] if match_idx < len(texts) else None
        url = urls[match_idx] if match_idx < len(urls) else None
        logging.info(
            f"CartAgent._lookup_in_catalog() | query='{item_name}' -> "
            f"matched='{names[match_idx]}' sim={similarity}"
        )
        return {"name": names[match_idx], "text": text, "similarity": similarity, "url": url}
