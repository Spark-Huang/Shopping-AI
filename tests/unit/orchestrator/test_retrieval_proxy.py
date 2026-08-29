
"""Unit tests for ``orchestrator.app.retriever``.

Covers
------
- ``_normalize_numeric_filter`` / ``_normalize_filters`` (pure logic).
- ``_sanitize_categories`` (pure logic).
- ``_extract_retrieval_inputs`` with a stubbed OpenAI async client.
- ``invoke`` with both text and image paths, success and HTTP failure.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace
from typing import Any, Dict

import pytest
import requests

from orchestrator.app.agents import retrieval_proxy as retriever_mod
from orchestrator.app.agents.state import State
from orchestrator.app.agents.retrieval_proxy import RetrieverAgent


@pytest.fixture
def retriever_agent(base_config, monkeypatch: pytest.MonkeyPatch) -> RetrieverAgent:
    class _FakeOpenAI:
        def __init__(self, *_, **__) -> None:
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_: None)
            )

    monkeypatch.setattr(retriever_mod, "OpenAI", _FakeOpenAI)
    return RetrieverAgent(config=base_config)


# ---------------------------------------------------------------------------
# Pure helper methods
# ---------------------------------------------------------------------------


class TestNormalizeNumericFilter:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, None),
            (10, 10.0),
            (10.5, 10.5),
            ("25", 25.0),
            ("$25", 25.0),
            ("1,250.50", 1250.5),
            ("  $19.99  ", 19.99),
            ("not a number", None),
            (["list"], None),
        ],
    )
    def test_coercion(self, value: Any, expected: float | None) -> None:
        result = RetrieverAgent._normalize_numeric_filter(value)
        if expected is None:
            assert result is None
        else:
            assert result == pytest.approx(expected)


class TestNormalizeFilters:
    def test_keeps_positive_prices(self, retriever_agent: RetrieverAgent) -> None:
        assert retriever_agent._normalize_filters({"min_price": 20, "max_price": 100}) == {
            "min_price": 20.0,
            "max_price": 100.0,
        }

    def test_drops_non_positive_prices(self, retriever_agent: RetrieverAgent) -> None:
        assert retriever_agent._normalize_filters({"min_price": 0, "max_price": 0}) == {}

    def test_drops_both_when_min_exceeds_max(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        assert retriever_agent._normalize_filters({"min_price": 200, "max_price": 50}) == {}

    def test_ignores_unknown_keys(self, retriever_agent: RetrieverAgent) -> None:
        assert retriever_agent._normalize_filters(
            {"max_price": 100, "color": "red"}
        ) == {"max_price": 100.0}

    def test_empty_dict_returns_empty(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        assert retriever_agent._normalize_filters({}) == {}


class TestSanitizeCategories:
    def test_keeps_allowlisted_in_order_dedupe(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        result = retriever_agent._sanitize_categories(["bag", "dress", "bag", "shoes"])
        assert result == ["bag", "dress", "shoes"]

    def test_drops_unknown_categories(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        assert retriever_agent._sanitize_categories(["apparel", "clothing"]) == []

    def test_skips_non_strings_and_blank_values(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        result = retriever_agent._sanitize_categories(
            ["bag", "", "   ", None, 123, "dress"]  # type: ignore[list-item]
        )
        assert result == ["bag", "dress"]


# ---------------------------------------------------------------------------
# extract_retrieval_inputs
# ---------------------------------------------------------------------------


def _stub_extraction_response(
    retriever_agent: RetrieverAgent, arguments: Dict[str, Any]
) -> None:
    """Replace the retriever's OpenAI client with a tool-call response."""
    tool_calls = [
        SimpleNamespace(
            function=SimpleNamespace(
                name="extract_retrieval_inputs",
                arguments=json.dumps(arguments),
            )
        )
    ]
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=tool_calls))
        ]
    )
    retriever_agent.model = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: response))
    )


class TestExtractRetrievalInputs:
    async def test_empty_query_short_circuits(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        entities, categories, filters = await retriever_agent._extract_retrieval_inputs(
            State(user_id=1, query="")
        )

        # With no query we fall back to [] entities, full category list, and no filters.
        assert entities == []
        assert categories == retriever_agent.categories
        assert filters == {}

    async def test_tool_call_parsing_happy_path(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        _stub_extraction_response(
            retriever_agent,
            {
                "search_entities": ["summer dress"],
                "category_one": "dress",
                "category_two": "dress",
                "category_three": "dress",
                "max_price": 100,
            },
        )

        entities, categories, filters = await retriever_agent._extract_retrieval_inputs(
            State(user_id=1, query="show me a summer dress under $100")
        )

        assert entities == ["summer dress"]
        assert categories == ["dress"]  # dedup + allowlist
        assert filters == {"max_price": 100.0}

    async def test_extractor_prompt_rejects_generic_anything_entities(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        captured: Dict[str, Any] = {}
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                function=SimpleNamespace(
                                    name="extract_retrieval_inputs",
                                    arguments=json.dumps(
                                        {
                                            "search_entities": [],
                                            "category_one": "dress",
                                            "category_two": "bag",
                                            "category_three": "shoes",
                                            "max_price": 100,
                                        }
                                    ),
                                )
                            )
                        ],
                    )
                )
            ]
        )

        def _create(**kwargs: Any) -> Any:
            captured.update(kwargs)
            return response

        retriever_agent.model = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )

        entities, _categories, filters = await retriever_agent._extract_retrieval_inputs(
            State(user_id=1, query="show me anything under $100")
        )

        prompt = captured["messages"][0]["content"]
        assert "Do NOT use generic browse words" in prompt
        assert "show me anything under ¥100" in prompt
        assert entities == []
        assert filters == {"max_price": 100.0}

    async def test_first_query_extraction_prompt_omits_context(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        captured: Dict[str, Any] = {}

        def _create(**kwargs: Any) -> Any:
            captured.update(kwargs)
            response = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=None, tool_calls=None)
                    )
                ]
            )
            return response

        retriever_agent.model = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )

        await retriever_agent._extract_retrieval_inputs(
            State(user_id=1, query="find a bag", context="old discussion")
        )

        user_prompt = captured["messages"][1]["content"]
        assert "old discussion" not in user_prompt
        assert "Current question: find a bag" in user_prompt

    async def test_invalid_categories_fall_back_to_allowlist(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        _stub_extraction_response(
            retriever_agent,
            {
                "search_entities": ["summer top"],
                "category_one": "apparel",
                "category_two": "clothing",
                "category_three": "apparel",
            },
        )

        entities, categories, filters = await retriever_agent._extract_retrieval_inputs(
            State(user_id=1, query="anything summer-y")
        )

        assert entities == ["summer top"]
        # All LLM categories were invented → fall back to agent's full list.
        assert categories == retriever_agent.categories
        assert filters == {}

    async def test_string_entity_list_gets_split(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        _stub_extraction_response(
            retriever_agent,
            {
                "search_entities": "['earrings', 'necklace']",
                "category_one": "earrings",
                "category_two": "necklace",
                "category_three": "necklace",
            },
        )

        entities, _, _ = await retriever_agent._extract_retrieval_inputs(
            State(user_id=1, query="accessories please")
        )

        assert entities == ["earrings", "necklace"]

    async def test_falls_back_to_content_when_no_tool_call(
        self, retriever_agent: RetrieverAgent
    ) -> None:
        # Model emits raw JSON content; the retriever must parse it.
        content = json.dumps(
            {
                "name": "extract_retrieval_inputs",
                "arguments": {
                    "search_entities": ["bag"],
                    "category_one": "bag",
                    "category_two": "bag",
                    "category_three": "bag",
                },
            }
        )
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content, tool_calls=None)
                )
            ]
        )
        retriever_agent.model = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: response))
        )

        entities, categories, _ = await retriever_agent._extract_retrieval_inputs(
            State(user_id=1, query="need a bag")
        )

        assert entities == ["bag"]
        assert categories == ["bag"]


# ---------------------------------------------------------------------------
# invoke()
# ---------------------------------------------------------------------------


class _FakeCatalogResponse:
    def __init__(self, payload: Dict[str, Any], status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def json(self) -> Dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


def _install_session_post(
    monkeypatch: pytest.MonkeyPatch,
    retriever_agent: RetrieverAgent,
    payload: Dict[str, Any] | None = None,
    *,
    raise_exc: Exception | None = None,
):
    """Stub ``requests.Session.post`` used inside RetrieverAgent.invoke."""
    captured: Dict[str, Any] = {}

    class _FakeSession:
        def mount(self, *_args, **_kwargs) -> None:
            return None

        def post(self, url: str, json: Dict[str, Any]):
            captured["url"] = url
            captured["json"] = json
            if raise_exc is not None:
                raise raise_exc
            return _FakeCatalogResponse(payload or {})

    monkeypatch.setattr(retriever_agent, "http_session", _FakeSession())
    return captured


class TestRetrieverInvoke:
    async def test_gift_set_query_spans_guizhou_catalog_categories(
        self,
        retriever_agent: RetrieverAgent,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_extraction_response(
            retriever_agent,
            {
                "search_entities": ["伴手礼"],
                "category_one": "food",
                "category_two": "food",
                "category_three": "food",
                "max_price": 100,
            },
        )
        captured = _install_session_post(
            monkeypatch,
            retriever_agent,
            payload={"texts": [], "names": [], "images": []},
        )

        await retriever_agent.invoke(
            State(user_id=1, query="预算100元推荐三样贵州伴手礼"),
            verbose=False,
        )

        assert captured["json"]["text"] == [
            "贵州茶",
            "贵州不辣食品饮品",
            "贵州非遗手作伴手礼",
        ]
        assert captured["json"]["categories"] == [
            "ethnic-wear",
            "craft",
            "food",
            "drink",
        ]
        assert captured["json"]["filters"] == {"max_price": 100.0}
        assert captured["json"]["k"] == 6

    @pytest.mark.parametrize(
        ("query", "arguments", "expected"),
        [
            (
                "推荐笔记本电脑",
                {"search_entities": ["笔记本电脑"], "category_one": "", "category_two": "", "category_three": ""},
                True,
            ),
            (
                "recommend a laptop",
                {"search_entities": ["laptop"], "category_one": "", "category_two": "", "category_three": ""},
                True,
            ),
            (
                "夏天穿什么",
                {"search_entities": ["夏天穿搭"], "category_one": "", "category_two": "", "category_three": ""},
                False,
            ),
            (
                "show me summer dresses",
                {"search_entities": ["summer dress"], "category_one": "dress", "category_two": "dress", "category_three": "dress"},
                False,
            ),
        ],
    )
    async def test_out_of_catalog_detection(
        self,
        retriever_agent: RetrieverAgent,
        query: str,
        arguments: dict,
        expected: bool,
    ) -> None:
        _stub_extraction_response(retriever_agent, arguments)
        entities, categories, _ = await retriever_agent._extract_retrieval_inputs(
            State(user_id=1, query=query)
        )
        assert retriever_agent._is_out_of_catalog(entities, categories) is expected

    async def test_out_of_catalog_skips_retrieval(
        self,
        retriever_agent: RetrieverAgent,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_extraction_response(
            retriever_agent,
            {"search_entities": ["laptop"], "category_one": "", "category_two": "", "category_three": ""},
        )
        captured = _install_session_post(monkeypatch, retriever_agent)

        state = State(user_id=1, query="recommend a laptop")
        out = await retriever_agent.invoke(state, verbose=False)

        assert "Guizhou specialties only" in out.response
        assert "captured" not in locals() or captured == {}

    async def test_text_query_populates_state_with_results(
        self,
        retriever_agent: RetrieverAgent,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_extraction_response(
            retriever_agent,
            {
                "search_entities": ["summer dress"],
                "category_one": "dress",
                "category_two": "dress",
                "category_three": "dress",
            },
        )
        captured = _install_session_post(
            monkeypatch,
            retriever_agent,
            payload={
                "texts": ["Summer Dress | breezy | dress"],
                "names": ["Summer Dress"],
                "images": ["img1.jpg"],
                "similarities": [0.9],
            },
        )

        state = State(user_id=1, query="show me a summer dress")
        out = await retriever_agent.invoke(state, verbose=False)

        assert captured["url"].endswith("/query/text")
        # Filters omitted when none are requested.
        assert captured["json"]["text"] == ["summer dress"]
        assert captured["json"]["k"] == retriever_agent.k_value
        assert "Summer Dress" in out.response
        assert "Summer Dress" in out.retrieved
        # Legacy catalog payloads (no urls/prices/ratings) still yield a
        # commercial-shaped entry with only the image key.
        assert out.retrieved["Summer Dress"] == {"image": "img1.jpg"}
        assert "retriever_retrieval" in out.timings
        assert "retriever_categories" in out.timings

    async def test_repeated_candidate_pool_reuses_60s_cache(
        self,
        retriever_agent: RetrieverAgent,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_extraction_response(
            retriever_agent,
            {
                "search_entities": ["summer dress"],
                "category_one": "dress",
                "category_two": "dress",
                "category_three": "dress",
            },
        )
        calls = []

        def _post(url: str, **_kwargs):
            calls.append(url)
            raise AssertionError("cache test should not call the service")

        monkeypatch.setattr(retriever_agent.http_session, "post", _post)
        payload = {
            "texts": ["Summer Dress"],
            "names": ["Summer Dress"],
            "images": ["img1.jpg"],
            "similarities": [0.9],
        }
        retriever_agent._store_results(
            retriever_agent._cache_key(
                ["summer dress"], ["dress"], {}, "", retriever_agent.k_value
            ),
            time.monotonic(),
            payload,
        )

        state = State(user_id=1, query="show me a summer dress")
        out = await retriever_agent.invoke(state, verbose=False)

        assert calls == []
        assert out.timings["retriever_cache_hit"] == 0.0
        assert out.timings["retriever_retrieval"] < 0.1
        assert out.retrieved["Summer Dress"] == {"image": "img1.jpg"}

    async def test_commercial_fields_flow_into_retrieved_state(
        self,
        retriever_agent: RetrieverAgent,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # D4: urls/prices/ratings returned by the search service land in
        # state.retrieved so the SSE images blob carries them to the UI.
        _stub_extraction_response(
            retriever_agent,
            {
                "search_entities": ["summer dress"],
                "category_one": "dress",
                "category_two": "dress",
                "category_three": "dress",
            },
        )
        _install_session_post(
            monkeypatch,
            retriever_agent,
            payload={
                "texts": ["Summer Dress | breezy | dress"],
                "names": ["Summer Dress"],
                "images": ["img1.jpg"],
                "similarities": [0.9],
                "urls": ["/images/Summer_Dress.jpg"],
                "prices": [49.99],
                "ratings": [4.6],
            },
        )

        state = State(user_id=1, query="show me a summer dress")
        out = await retriever_agent.invoke(state, verbose=False)

        assert out.retrieved["Summer Dress"] == {
            "image": "img1.jpg",
            "url": "/images/Summer_Dress.jpg",
            "price": 49.99,
            "rating": 4.6,
        }
        # The chatter-facing text list is unaffected by the extra fields.
        assert "PRICE" not in out.response or "Summer Dress" in out.response

    async def test_partial_commercial_lists_do_not_truncate_rows(
        self,
        retriever_agent: RetrieverAgent,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Regression: a flat zip() over missing commercial lists silently
        # produced an empty response/retrieved; index-based lookup must keep
        # every row even when only some fields are present.
        _stub_extraction_response(
            retriever_agent,
            {
                "search_entities": ["bag"],
                "category_one": "bag",
                "category_two": "bag",
                "category_three": "bag",
            },
        )
        _install_session_post(
            monkeypatch,
            retriever_agent,
            payload={
                "texts": [
                    "Leather Bag | elegant | bag",
                    "Canvas Tote | casual | bag",
                ],
                "names": ["Leather Bag", "Canvas Tote"],
                "images": ["bag.jpg", "tote.jpg"],
                "similarities": [0.7, 0.65],
                "prices": [199.0],
            },
        )

        state = State(
            user_id=1,
            query="find a similar bag",
            image="data:image/jpeg;base64,AAAA",
        )
        out = await retriever_agent.invoke(state, verbose=False)

        assert "Leather Bag" in out.response
        assert "Canvas Tote" in out.response
        assert out.retrieved["Leather Bag"]["price"] == 199.0
        assert "price" not in out.retrieved["Canvas Tote"]

    async def test_image_query_uses_image_endpoint(
        self,
        retriever_agent: RetrieverAgent,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_extraction_response(
            retriever_agent,
            {
                "search_entities": ["bag"],
                "category_one": "bag",
                "category_two": "bag",
                "category_three": "bag",
            },
        )
        captured = _install_session_post(
            monkeypatch,
            retriever_agent,
            payload={
                "texts": ["Leather Bag | elegant | bag"],
                "names": ["Leather Bag"],
                "images": ["bag.jpg"],
                "similarities": [0.7],
            },
        )

        state = State(
            user_id=1,
            query="find a similar bag",
            image="data:image/jpeg;base64,AAAA",
        )
        out = await retriever_agent.invoke(state, verbose=False)

        assert captured["url"].endswith("/query/image")
        assert captured["json"]["image_base64"] == "data:image/jpeg;base64,AAAA"
        assert "Leather Bag" in out.response

    async def test_no_results_produces_polite_message(
        self,
        retriever_agent: RetrieverAgent,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_extraction_response(
            retriever_agent,
            {
                "search_entities": ["unusual product"],
                "category_one": "bag",
                "category_two": "bag",
                "category_three": "bag",
            },
        )
        _install_session_post(
            monkeypatch,
            retriever_agent,
            payload={
                "texts": [],
                "names": [],
                "images": [],
                "similarities": [],
            },
        )

        state = State(user_id=1, query="looking for a watch")
        out = await retriever_agent.invoke(state, verbose=False)

        assert "no products closely matching" in out.response.lower()

    async def test_http_error_sets_error_response(
        self,
        retriever_agent: RetrieverAgent,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _stub_extraction_response(
            retriever_agent,
            {
                "search_entities": ["bag"],
                "category_one": "bag",
                "category_two": "bag",
                "category_three": "bag",
            },
        )
        _install_session_post(
            monkeypatch,
            retriever_agent,
            raise_exc=requests.exceptions.ConnectionError("boom"),
        )

        state = State(user_id=1, query="any bag")
        out = await retriever_agent.invoke(state, verbose=False)

        assert "encountered an error" in out.response.lower()
