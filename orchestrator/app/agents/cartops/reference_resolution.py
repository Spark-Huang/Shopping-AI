from typing import Optional

from ..state import State
from .catalog_match import _normalize_name
from .name_heuristics import (
    _BOLD_NAME_RE,
    _CATALOG_ROW_RE,
    _LIST_NUMBER_PREFIX_RE,
    _ORDINAL_POSITIONS,
    _ORDINAL_REFERENCE_RE,
    _PRONOUN_REFERENCE_RE,
    _extract_ordinal_position,
    _strip_list_number_prefix,
    _strip_ordinals,
    NameHeuristicsMixin,
)


class ReferenceResolutionMixin(NameHeuristicsMixin):
    @staticmethod
    def _last_mentioned_product(known: list[str], context: str) -> Optional[str]:
            """Return the product most recently mentioned in ``context``.

            "Most recent" is the rightmost occurrence across all known names;
            used as the deterministic anchor for pronoun-only cart requests.
            """
            if not known or not context:
                return None
            ctx_lower = context.lower()
            best_name: Optional[str] = None
            best_pos = -1
            for name in known:
                needle = name.lower()
                if not needle:
                    continue
                pos = ctx_lower.rfind(needle)
                if pos > best_pos:
                    best_pos = pos
                    best_name = name
            return best_name

    @staticmethod
    def _extract_display_order(context: str) -> list[str]:
            """Extract product names in the order they were shown to the user.

            Scans ``context`` left-to-right and records the first occurrence
            position of every product-name-shaped candidate, using the same
            two harvesters that feed ``_collect_known_products``:

            * catalog rows ``Name | description | category``
            * ``**Name**`` bold spans

            Matches from both patterns are merged by their absolute position
            in the context *before* deduping, so the returned list reflects
            true display order (the order in which products were shown to
            the user) and keeps the casing of whichever form appears first.
            Leading list numbering (``1.``/``2)``) is stripped so numbered
            retrieval rows still resolve as names. Dedup is case-insensitive,
            keeping the first-seen casing. This is what "the first one" /
            "the second one" refer to.
            """
            if not context:
                return []
            candidates: list[tuple[int, str]] = []
            for match in _CATALOG_ROW_RE.finditer(context):
                name = _strip_list_number_prefix(match.group(1).strip())
                if name:
                    candidates.append((match.start(), name))
            for match in _BOLD_NAME_RE.finditer(context):
                name = _strip_list_number_prefix(match.group(1).strip())
                if name:
                    candidates.append((match.start(), name))

            positions: dict[str, tuple[int, str]] = {}
            for position, name in sorted(candidates, key=lambda entry: entry[0]):
                if not NameHeuristicsMixin._looks_like_product_name(name):
                    continue
                key = _normalize_name(name)
                if key and key not in positions:
                    positions[key] = (position, name)
            ordered = sorted(positions.values(), key=lambda entry: entry[0])
            return [name for _, name in ordered]

    def _resolve_ordinal_reference(cls, query: str, context: str) -> Optional[str]:
            """Resolve an ordinal reference ("the first one") via display order.

            Returns the product occupying the requested position in the order
            products were shown in ``context``, or None when there is no
            ordinal token or the position is out of range. "last" resolves to
            the most recently shown product.
            """
            position = _extract_ordinal_position(query)
            if position is None:
                return None
            ordered = cls._extract_display_order(context)
            if not ordered:
                return None
            if position == -1:
                return ordered[-1]
            if 1 <= position <= len(ordered):
                return ordered[position - 1]
            return None

    def _resolve_target_item_with_kind(self, state: State) -> tuple[Optional[str], str]:
            """Resolve the target product together with the strength of its anchor.

            Returns ``(product, kind)`` where ``kind`` is one of:

            * ``"named"``   -- the query explicitly names a known product.
            * ``"ordinal"`` -- the query refers by display position ("the first
              one"); resolved against the order products were shown in context.
            * ``"pronoun"`` -- bare pronoun reference; resolved to the
              last-mentioned product (weakest signal).
            * ``""``        -- no anchored signal at all.

            """
            query = state.query or ""
            known = self._collect_known_products(state)
            if not known:
                return None, ""

            named = self._find_named_product(query, known)
            if named:
                return named, "named"

            if _extract_ordinal_position(query) is not None:
                return self._resolve_ordinal_reference(query, state.context or ""), "ordinal"

            if self._is_pronoun_reference(_strip_ordinals(query)):
                return self._last_mentioned_product(known, state.context or ""), "pronoun"

            return None, ""

    def _resolve_target_item(self, state: State) -> Optional[str]:
            """Deterministically pick the product a cart request is targeting.

            Resolution order:
              1. Named product found in the query -> use it.
              2. Ordinal reference ("the first one", "that 2nd dress", "the
                 last one") -> pick by the order products were displayed in
                 the conversation context. This runs *before* the generic
                 pronoun fallback: the bare "one" inside an ordinal phrase
                 would otherwise be misread as a plain pronoun and silently
                 resolve to the last-mentioned product.
              3. Pronoun-style query (with no ordinal) -> fall back to the
                 last-mentioned product.
              4. Otherwise return None (defer to the LLM's choice).

            The catalog lookup still runs after this, so a bad anchor can
            only shift which real product gets picked, not invent one.
            """
            resolved, _kind = self._resolve_target_item_with_kind(state)
            return resolved
