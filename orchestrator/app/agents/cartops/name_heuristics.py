import ast
import json
import logging
import re
from typing import Any, Optional

from ..state import State
from .catalog_match import _normalize_name

_PRICE_PATTERN = re.compile(r"PRICE:\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)

# Matches **Product Name** spans emitted by the chatter in its user-facing
# responses. We post-filter the captures against
# ``_looks_like_product_name`` to reject bolded price/heading spans like
# "**Price: $69.99**".
_BOLD_NAME_RE = re.compile(r"\*\*([^*\n]+?)\*\*")

# Matches the search service's "NAME | description | category" row format.
# We only need the name (before the first pipe) to harvest candidates.
_CATALOG_ROW_RE = re.compile(r"^([^|\n]+?)\s+\|\s+", re.MULTILINE)

# A product-name-shaped string: at least two tokens, each token made of
# letters, digits, hyphens, or apostrophes. Excludes currency, colons, and
# other punctuation that shows up in incidental bold spans.
_PRODUCT_NAME_SHAPE_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9'\-]*(?:\s+[A-Za-z0-9'\-]+){1,}$"
)

# Generic words that appear in assistant prose headings (e.g.
# "**Manage your cart**") but never in a product name worth anchoring a
# cart action to. A bold span containing one of these is UI copy, not a
# product mention (PM review 2026-08-24, item 13: a chat heading was
# harvested as a product and overrode the LLM's correct pick).
_NON_PRODUCT_TERMS = frozenset(
    {
        "cart",
        "carts",
        "checkout",
        "order",
        "orders",
        "summary",
        "total",
        "subtotal",
        "payment",
        "shipping",
        "delivery",
        "return",
        "returns",
        "exchange",
        "refund",
        "warranty",
        "account",
        "profile",
        "settings",
        "guide",
        "guidelines",
        "faq",
        "policy",
        "policies",
        "privacy",
        "terms",
        "service",
        "services",
        "support",
        "help",
        "assistant",
        "manage",
        "managing",
        "your",
        "please",
        "thanks",
        "welcome",
        "hello",
    }
)

# Leading list numbering on catalog rows ("1. Luminous Satin Dress | ...").
# Retrieval snippets occasionally carry markdown-style enumeration; the
# number is presentation noise, not part of the product name.
_LIST_NUMBER_PREFIX_RE = re.compile(r"^\s*\d{1,3}\s*[.)\]:]\s+")


def _strip_list_number_prefix(candidate: str) -> str:
    """Remove a leading ``1.``/``2)`` style list marker from a name candidate."""
    return _LIST_NUMBER_PREFIX_RE.sub("", candidate or "")

# Words/phrases the user can use to refer to a product without naming it.
# Kept deliberately narrow: adding ambiguous tokens like "the dress" would
# fire the override for legitimate new-product queries.
#
# NOTE: ordinal references ("the first one", "that second one") are handled
# by ``_ORDINAL_REFERENCE_RE`` *before* this pattern is consulted -- see
# ``_strip_ordinals``. Without that stripping, the "one"/"ones" tokens in an
# ordinal phrase would fall into the pronoun branch and be resolved to the
# *last-mentioned* product, silently overriding an explicit "first/second"
# instruction.
_PRONOUN_REFERENCE_RE = re.compile(
    r"\b(it|this|that|one|them|these|those|both)\b",
    re.IGNORECASE,
)

# Ordinal references: word and numeric forms, optionally attached to a
# pronoun-ish noun ("the first one", "that 2nd dress", "grab the last").
_ORDINAL_REFERENCE_RE = re.compile(
    r"\b(?:first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th)\b",
    re.IGNORECASE,
)

# Maps an ordinal token to a 1-based display position; "last" resolves to
# the final entry of whatever was shown to the user.
_ORDINAL_POSITIONS = {
    "first": 1,
    "1st": 1,
    "second": 2,
    "2nd": 2,
    "third": 3,
    "3rd": 3,
    "fourth": 4,
    "4th": 4,
    "fifth": 5,
    "5th": 5,
}


def _strip_ordinals(query: str) -> str:
    """Return ``query`` with ordinal tokens blanked out."""
    return _ORDINAL_REFERENCE_RE.sub(" ", query or "")


def _extract_ordinal_position(query: str) -> Optional[int]:
    """Return the 1-based display position requested by an ordinal phrase."""
    match = _ORDINAL_REFERENCE_RE.search(query or "")
    if not match:
        return None
    token = match.group(0).lower()
    if token == "last":
        return -1
    return _ORDINAL_POSITIONS.get(token)


class NameHeuristicsMixin:
    @staticmethod
    def _looks_like_product_name(candidate: str) -> bool:
            """Reject non-name bold spans (``**Price: $69.99**``, ``**Tip:**``).

            Product names are at least two tokens of letters/digits, with no
            punctuation beyond hyphens or apostrophes. Additionally, spans
            containing commerce/UI vocabulary ("Manage your cart",
            "Order Summary") are rejected: they are assistant prose, not
            products, and treating them as anchors historically overrode
            correct LLM picks (PM review 2026-08-24, item 13).
            """
            if not _PRODUCT_NAME_SHAPE_RE.match(candidate or ""):
                return False
            tokens = set(_normalize_name(candidate).split())
            return not (tokens & _NON_PRODUCT_TERMS)

    @classmethod
    def _collect_known_products(cls, state: State) -> list[str]:
            """Gather product names the user could plausibly be referring to.

            Sources (deduped case-insensitively, preserving first-seen casing):
              1. Cart contents (trusted; added unconditionally).
              2. Catalog rows ``Name | description | category`` in ``state.context``.
              3. ``**Name**`` spans in ``state.context``.

            Context-derived sources are filtered through
            ``_looks_like_product_name`` because the running context also
            contains prose with stray ``" | "`` and bolded price/heading spans.
            """
            seen: dict[str, str] = {}

            def _add(candidate: str, trusted: bool = False) -> None:
                name = (candidate or "").strip()
                if not name:
                    return
                if not trusted and not cls._looks_like_product_name(name):
                    return
                key = _normalize_name(name)
                if key and key not in seen:
                    seen[key] = name

            if state.cart and state.cart.contents:
                for entry in state.cart.contents:
                    _add(entry.get("item", ""), trusted=True)

            ctx = state.context or ""
            for match in _CATALOG_ROW_RE.findall(ctx):
                _add(match)
            for match in _BOLD_NAME_RE.findall(ctx):
                _add(match)

            return list(seen.values())

    @staticmethod
    def _is_pronoun_reference(query: str) -> bool:
            """True if the query contains a pronoun-style reference.

            A pronoun alone isn't sufficient (a query can both pronoun and
            name a product). Combined with the product-name scan, it's the
            trigger for the focus-item fallback.
            """
            return bool(_PRONOUN_REFERENCE_RE.search(query or ""))

    @staticmethod
    def _find_named_product(query: str, known: list[str]) -> Optional[str]:
            """Return the known product the query most specifically names.

            Users abbreviate catalog names, so strict substring matching is
            not enough. Each candidate is scored with a symmetric token
            overlap::

                score = max(|q ∩ n| / |q|, |q ∩ n| / |n|)

            which keeps long and short queries on equal footing. A candidate
            is chosen only if it (1) scores >= 0.5, (2) beats the runner-up
            by >= 0.2, and (3) shares a signal token with the query.

            Signal tokens are derived from the catalog itself: only tokens
            that appear in at least one ``known`` product name count. Any
            query word outside that vocabulary ("please", "add", "the",
            and their equivalents in any other language) is treated as
            filler. This avoids a curated stopword list and stays correct
            as the catalog (or its language) evolves.

            A single high coverage direction is NOT enough to call a
            candidate "named" by the query: with only ``max(q_cov, n_cov)
            >= 0.5``, a filler-heavy query like "add a silk scarf to my
            cart" could latch onto a context heading that happens to share
            one generic word ("**Manage your cart**"), turning chat prose
            into a "named" anchor that overrode a correct LLM pick (PM
            review 2026-08-24, item 13). Coverage is therefore computed
            over *distinctive* tokens only -- shared generic commerce words
            ("cart", "order", ...) count for nothing -- and both coverage
            directions must clear 0.5, with one exception:
            ``q_cov == 1.0`` with a multi-token distinctive overlap means
            every catalog token in the query belongs to this one candidate
            -- a deliberate (possibly abbreviated) reference, e.g. bulk
            entries like "Honey Skirt" for "Honey Floral Print Midi
            Skirt" -- which stays resolvable even when the candidate's own
            name is longer.
            """
            q_norm = _normalize_name(query)
            if not q_norm:
                return None

            candidates: list[tuple[str, str, set[str]]] = []
            catalog_vocab: set[str] = set()
            for name in known:
                n_norm = _normalize_name(name)
                if not n_norm:
                    continue
                n_tokens = set(n_norm.split())
                if not n_tokens:
                    continue
                candidates.append((name, n_norm, n_tokens))
                catalog_vocab |= n_tokens

            if not candidates:
                return None

            q_tokens = set(q_norm.split()) & catalog_vocab
            if not q_tokens:
                return None

            scored: list[tuple[float, str]] = []
            for name, n_norm, n_tokens in candidates:
                if n_norm in q_norm:
                    return name
                # Generic-word collision guard (see docstring): only
                # distinctive tokens (generic commerce words excluded)
                # count towards coverage.
                shared = (q_tokens & n_tokens) - _NON_PRODUCT_TERMS
                if not shared:
                    continue
                q_cov = len(shared) / len(q_tokens)
                n_cov = len(shared) / len(n_tokens)
                # A one-token overlap only counts when it fully explains the
                # query's catalog vocabulary AND the candidate is a
                # plausible abbreviated target (multi-token name); a bare
                # "cart" hitting "Manage your cart" must not anchor.
                if len(shared) == 1 and len(n_tokens) > 2:
                    continue
                if q_cov < 1.0 and min(q_cov, n_cov) < 0.5:
                    continue
                scored.append((max(q_cov, n_cov), name))

            if not scored:
                return None

            scored.sort(key=lambda entry: entry[0], reverse=True)
            best_score, best_name = scored[0]
            runner_up = scored[1][0] if len(scored) > 1 else 0.0
            if best_score < 0.5:
                return None
            if best_score - runner_up < 0.2:
                return None
            return best_name

    def _override_bulk_item_names(
            self, items: list, state: State
        ) -> list:
            """Apply the deterministic resolver to each entry in a bulk tool call.

            For ``bulk_add_to_cart`` / ``bulk_remove_from_cart`` the LLM provides
            per-item names, so pronoun resolution (which operates over the full
            query) is not useful. Instead we re-anchor each name against the set
            of products actually present in cart + context. This catches the same
            class of mistake the single-item override does (LLM paraphrasing a
            catalog name) without affecting cases where the LLM got it right.

            Mutates and returns ``items`` for convenience.
            """
            if not items:
                return items
            known = self._collect_known_products(state)
            if not known:
                return items

            for entry in items:
                if not isinstance(entry, dict):
                    continue
                llm_pick = entry.get("item_name") or ""
                resolved = self._find_named_product(llm_pick, known)
                if (
                    resolved
                    and _normalize_name(llm_pick) != _normalize_name(resolved)
                ):
                    logging.warning(
                        f"CartAgent.invoke() | overriding bulk item_name "
                        f"llm={llm_pick!r} -> deterministic={resolved!r}"
                    )
                    entry["item_name"] = resolved
            return items

    @staticmethod
    def _coerce_bulk_items(raw: Any) -> list:
            """Accept the ``items`` argument in its various possible shapes.

            The XML fallback path surfaces ``items`` as a string repr that has
            already been parsed to a list by ``_coerce_value`` in almost all
            cases. A defensive re-parse here makes the code tolerant of any
            edge-case model output without special casing its caller.
            """
            if isinstance(raw, list):
                return raw
            if isinstance(raw, str):
                stripped = raw.strip()
                if not stripped:
                    return []
                try:
                    import ast
                    parsed = ast.literal_eval(stripped)
                except (ValueError, SyntaxError):
                    try:
                        parsed = json.loads(stripped)
                    except (ValueError, TypeError):
                        return []
                return parsed if isinstance(parsed, list) else []
            return []

    @staticmethod
    def _extract_recent_discussion(context: str, max_chars: int = 2000) -> str:
            """Return the tail of the conversation context to focus pronoun resolution.

            The running context string grows unboundedly per turn. When resolving
            pronouns like "it" in cart requests, only the most recent exchange is
            relevant; older product mentions and prior cart actions create noise
            that can cause the LLM to misidentify the target item.
            """
            if not context:
                return "(no prior discussion)"
            trimmed = context.strip()
            if len(trimmed) <= max_chars:
                return trimmed
            tail = trimmed[-max_chars:]
            newline_idx = tail.find("\n")
            if 0 < newline_idx < max_chars // 4:
                tail = tail[newline_idx + 1:]
            return "...\n" + tail

    def _update_context(self, user_id: int, context: str) -> None:
            state = getattr(self, "state", None)
            headers = {"Authorization": state.authorization} if state else {}
            response = requests.post(
                f"{self.memory_url}/user/{user_id}/context/add",
                json={"new_context": context},
                headers=headers,
            )
            if response.status_code != 200:
                logging.error(f"Failed to update context: {response.text}")
