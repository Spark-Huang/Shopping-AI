
"""Unit tests for ``orchestrator.app.chatter``.

Splits into two groups:

1. ``_format_*`` helpers that render the grounded prompt blocks.
2. ``invoke`` with an async-iterator stand-in for the OpenAI streaming
   response, using ``stream_writer_capture`` to observe emitted events.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import AsyncIterator, Iterable, List

import pytest

from orchestrator.app.agents import chatter as chatter_mod
from orchestrator.app.agents.state import Cart, State
from orchestrator.app.agents.chatter import ChatterAgent
from orchestrator.app.agents.state import RecentOrders


@pytest.fixture
def chatter_agent(base_config, monkeypatch: pytest.MonkeyPatch) -> ChatterAgent:
    class _FakeAsyncOpenAI:
        def __init__(self, *_, **__) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=None))

    monkeypatch.setattr(chatter_mod, "AsyncOpenAI", _FakeAsyncOpenAI)
    return ChatterAgent(config=base_config)


# ---------------------------------------------------------------------------
# Pure formatting helpers
# ---------------------------------------------------------------------------


class TestFormatCart:
    def test_empty_cart_returns_placeholder(self) -> None:
        state = State(user_id=1, query="q")
        assert ChatterAgent._format_cart(state) == "(empty)"

    def test_renders_line_per_item_with_price(self) -> None:
        state = State(
            user_id=1,
            query="q",
            cart=Cart(
                contents=[
                    {"item": "Silk Dress", "amount": 2, "price": 49.99},
                    {"item": "Leather Bag", "amount": 1, "price": 199.0},
                ]
            ),
        )

        rendered = ChatterAgent._format_cart(state)

        assert "- 2 x Silk Dress @ ¥49.99" in rendered
        assert "- 1 x Leather Bag @ ¥199.00" in rendered

    def test_renders_line_without_price_when_missing(self) -> None:
        state = State(
            user_id=1,
            query="q",
            cart=Cart(contents=[{"item": "Hat", "amount": 1}]),
        )

        rendered = ChatterAgent._format_cart(state)
        assert rendered == "- 1 x Hat"

    def test_handles_non_numeric_price_gracefully(self) -> None:
        state = State(
            user_id=1,
            query="q",
            cart=Cart(
                contents=[{"item": "Weird Thing", "amount": 1, "price": "NaN$$"}]
            ),
        )

        rendered = ChatterAgent._format_cart(state)
        # Non-coercible price collapses to the no-price branch rather than raising.
        assert rendered == "- 1 x Weird Thing"


class TestFormatRecentOrders:
    def test_empty_orders_returns_placeholder(self) -> None:
        state = State(user_id=1, query="orders")
        assert ChatterAgent._format_recent_orders(state) == "(none)"

    def test_orders_render_details_and_limit_five(self) -> None:
        state = State(
            user_id=1,
            query="orders",
            recent_orders=RecentOrders(entries=[
                {"item": "Newest", "price": 12.5, "purchased_at": "2026-08-26"},
                *[{"item": f"Item {index}", "price": 1, "purchased_at": "2026-08-25"} for index in range(5)],
            ]),
        )

        rendered = ChatterAgent._format_recent_orders(state)

        assert rendered.splitlines()[0] == "- Newest @ ¥12.50 on 2026-08-26"
        assert len(rendered.splitlines()) == 5

    def test_orders_render_gracefully_when_price_is_invalid(self) -> None:
        state = State(
            user_id=1,
            query="orders",
            recent_orders=RecentOrders(
                entries=[
                    {"item": "Weird Price", "price": "NaN$$", "purchased_at": "2026-08-26"}
                ]
            ),
        )

        rendered = ChatterAgent._format_recent_orders(state)

        assert rendered == "- Weird Price (price unavailable) on 2026-08-26"


class TestFormatAvailableCatalog:
    def test_empty_retrieved_returns_placeholder(self) -> None:
        state = State(user_id=1, query="q")
        assert (
            ChatterAgent._format_available_catalog(state)
            == "(no fresh catalog results this turn)"
        )

    def test_lists_names_one_per_line(self) -> None:
        state = State(
            user_id=1,
            query="q",
            retrieved={"Silk Dress": "a.jpg", "Hiking Boot": "b.jpg"},
        )

        out = ChatterAgent._format_available_catalog(state)
        assert "- Silk Dress" in out
        assert "- Hiking Boot" in out

    def test_over_budget_candidates_include_delta(self) -> None:
        state = State(
            user_id=1,
            query="预算100元贵州伴手礼",
            retrieved={
                "贵州特产伴手礼": {
                    "image": "gift.jpg",
                    "price": 138.0,
                    "currency": "CNY",
                    "over_budget": 38.0,
                }
            },
        )

        out = ChatterAgent._format_available_catalog(state)

        assert "- 贵州特产伴手礼: ¥138.00 (CNY), over budget by ¥38.00" in out

    def test_catalog_rule_targets_over_budget_fallback(self) -> None:
        prompt = (
            "If that catalog is marked as an over-budget fallback, say there is no "
            "perfect match within the user's budget, present only those fallback "
            "products with their price and over-budget amount, and never substitute "
            "a different product type."
        )

        assert prompt in ChatterAgent._format_fallback_rule()


class TestDescribePrecedingAgent:
    @pytest.mark.parametrize(
        "next_agent,expected",
        [
            ("cart", "cart"),
            ("CART", "cart"),
            ("retriever", "retriever"),
            ("", "none"),
            ("chatter", "none"),
            ("unknown", "none"),
        ],
    )
    def test_mapping(self, next_agent: str, expected: str) -> None:
        state = State(user_id=1, query="q", next_agent=next_agent)
        assert ChatterAgent._describe_preceding_agent(state) == expected


# ---------------------------------------------------------------------------
# detect_language() (D5: language-aware replies)
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    def test_chinese_text_heuristic_returns_zh(self) -> None:
        assert ChatterAgent.detect_language("帮我找一条丝绸连衣裙") == "zh"

    def test_english_text_heuristic_returns_en(self) -> None:
        # No CJK characters anywhere => English default even with no
        # explicit declaration.
        assert ChatterAgent.detect_language("find me a silk dress") == "en"

    @pytest.mark.parametrize(
        "query",
        [
            # English UI copy with a single CJK brand glyph.
            "I want the 华伦天奴 scarf from your catalog",
            # English query embedding a short CJK product name.
            "show me reviews for 小米 phone cases please",
        ],
    )
    def test_mostly_english_with_stray_cjk_stays_en(self, query: str) -> None:
        # Arch review R16-batch2 P1: presence of a couple of CJK glyphs
        # (brand/product names) must NOT flip an English sentence to zh;
        # the fallback heuristic judges by CJK ratio (>= 0.3), not by
        # mere presence.
        assert ChatterAgent.detect_language(query) == "en"

    def test_mixed_text_at_ratio_boundary(self) -> None:
        # Ratio exactly at the threshold counts as Chinese; just below
        # it stays English.
        at_threshold = "abc" + "你好"          # 2/5 = 0.4 >= 0.3 -> zh
        below_threshold = "abcdef" + "你好"    # 2/8 = 0.25 < 0.3  -> en
        assert ChatterAgent.detect_language(at_threshold) == "zh"
        assert ChatterAgent.detect_language(below_threshold) == "en"

    @pytest.mark.parametrize(
        "declared",
        ["zh", "ZH", " zh ", "en", "EN", " en "],
    )
    def test_declared_language_wins_over_text(self, declared: str) -> None:
        # Explicit UI declaration overrides the text heuristic in both
        # directions (declared zh on English text, declared en on Chinese
        # text), and tolerates case/whitespace from the wire.
        text = "hello" if declared.strip().lower() == "zh" else "你好"
        assert ChatterAgent.detect_language(text, declared) == (
            "zh" if declared.strip().lower() == "zh" else "en"
        )

    def test_unknown_declaration_falls_back_to_text(self) -> None:
        # Legacy/unknown declarations (e.g. "fr") are ignored; the CJK
        # heuristic decides.
        assert ChatterAgent.detect_language("你好世界", "fr") == "zh"
        assert ChatterAgent.detect_language("hello world", "fr") == "en"

    def test_defaults_to_en_when_no_signal(self) -> None:
        # Empty query + no declaration => conservative English default.
        assert ChatterAgent.detect_language("", "") == "en"
        assert ChatterAgent.detect_language("", None) == "en"


class TestLanguageInstruction:
    def test_zh_instruction_pinned_to_chinese(self) -> None:
        instruction = ChatterAgent._language_instruction("zh")
        assert "Chinese" in instruction
        assert "original currency" in instruction

    def test_en_instruction_pinned_to_english(self) -> None:
        instruction = ChatterAgent._language_instruction("en")
        assert "English" in instruction
        assert "original currency" in instruction


class TestChatterGroundingPrompt:
    def test_prompt_contains_real_ui_capabilities(self, chatter_agent: ChatterAgent) -> None:
        prompt = chatter_agent.config.chatter_prompt

        assert "REAL UI CAPABILITIES" in prompt
        assert "external merchant link" in prompt
        assert "check out selected items" in prompt

    def test_prompt_contains_budget_awareness_rule(self, chatter_agent: ChatterAgent) -> None:
        assert "BUDGET AWARENESS" in chatter_agent.config.chatter_prompt
        assert "Budget alert:" in chatter_agent.config.chatter_prompt
        assert "RECENT DISCUSSION" in chatter_agent.config.chatter_prompt
        assert "in-budget alternatives" in chatter_agent.config.chatter_prompt


# ---------------------------------------------------------------------------
# invoke()
# ---------------------------------------------------------------------------


class _FakeStream:
    """Minimal async iterator emitting chat-completion-like delta chunks."""

    def __init__(self, pieces: Iterable[str]) -> None:
        self._pieces: List[str] = list(pieces)

    def __aiter__(self) -> AsyncIterator["_FakeStream"]:
        return self

    async def __anext__(self):
        if not self._pieces:
            raise StopAsyncIteration
        content = self._pieces.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=content))]
        )


def _install_async_stream(
    chatter_agent: ChatterAgent, pieces: Iterable[str]
) -> None:
    async def _create(**_: object) -> _FakeStream:
        return _FakeStream(pieces)

    chatter_agent.model = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )


class TestChatterInvoke:
    async def test_buffer_holds_events_until_safety_verdict(
        self,
        chatter_agent: ChatterAgent,
        stream_writer_capture: list,
    ) -> None:
        _install_async_stream(chatter_agent, ["unsafe ", "content"])
        buffer = chatter_mod.StreamBuffer(
            writer=lambda event: stream_writer_capture.append(event)
        )
        state = State(user_id=1, query="hi", stream_buffer=buffer)
        await chatter_agent.invoke(state, verbose=False)

        assert stream_writer_capture == []
        assert [json.loads(event)["payload"] for event in buffer.events] == [
            {},
            "unsafe ",
            "content",
        ]

    async def test_buffer_flush_preserves_event_order(
        self,
        chatter_agent: ChatterAgent,
        stream_writer_capture: list,
    ) -> None:
        _install_async_stream(chatter_agent, ["Hello ", "world!"])
        buffer = chatter_mod.StreamBuffer(
            writer=lambda event: stream_writer_capture.append(event)
        )
        state = State(user_id=1, query="hi", stream_buffer=buffer)
        await chatter_agent.invoke(state, verbose=False)
        buffer.flush()

        assert [json.loads(event)["type"] for event in stream_writer_capture] == [
            "images",
            "content",
            "content",
        ]
        assert "".join(
            json.loads(event)["payload"]
            for event in stream_writer_capture
            if json.loads(event)["type"] == "content"
        ) == "Hello world!"


async def test_buffer_discard_never_releases_events() -> None:
    released: list[str] = []
    buffer = chatter_mod.StreamBuffer(writer=released.append)
    buffer.add("first")
    buffer.add("second")
    buffer.discard()

    assert released == []
    with pytest.raises(RuntimeError):
        buffer.add("third")


    async def test_invoke_prefers_small_model_for_streaming(
        self,
        chatter_agent: ChatterAgent,
        stream_writer_capture: list,
    ) -> None:
        chatter_agent.small_llm_name = "zai/glm-5"
        captured: dict = {}

        async def _create(**kwargs):
            captured.update(kwargs)
            return _FakeStream(["ok"])

        chatter_agent.model = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )
        await chatter_agent.invoke(State(user_id=1, query="hi"), verbose=False)

        assert captured["model"] == "zai/glm-5"

    async def test_invoke_streams_content_updates_state(
        self,
        chatter_agent: ChatterAgent,
        stream_writer_capture: list,
    ) -> None:
        _install_async_stream(chatter_agent, ["Hello ", "world", "!"])
        state = State(
            user_id=1,
            query="hi there",
            retrieved={"Silk Dress": "a.jpg"},
        )

        out = await chatter_agent.invoke(state, verbose=False)

        assert out.response == "Hello world!"
        assert out.context.endswith("Hello world!")
        assert "chatter" in out.timings
        assert "first_token" in out.timings

        # The first emitted payload is the images frame.
        first_payload = json.loads(stream_writer_capture[0])
        assert first_payload["type"] == "images"
        assert first_payload["payload"] == {"Silk Dress": "a.jpg"}

        # Every subsequent event is a content frame.
        content_frames = [
            json.loads(ev) for ev in stream_writer_capture[1:]
        ]
        assert [frame["type"] for frame in content_frames] == ["content"] * 3
        assert [frame["payload"] for frame in content_frames] == [
            "Hello ",
            "world",
            "!",
        ]

    async def test_invoke_handles_empty_stream_gracefully(
        self,
        chatter_agent: ChatterAgent,
        stream_writer_capture: list,
    ) -> None:
        _install_async_stream(chatter_agent, [])
        state = State(user_id=1, query="hello")

        out = await chatter_agent.invoke(state, verbose=False)

        assert out.response == ""
        # No timings for first_token since nothing streamed.
        assert "first_token" not in out.timings

    async def test_invoke_skips_empty_delta_chunks(
        self,
        chatter_agent: ChatterAgent,
        stream_writer_capture: list,
    ) -> None:
        # ``None`` content chunks arrive when only tool deltas are in flight;
        # the chatter must ignore them without crashing.
        class _NullAwareStream(_FakeStream):
            def __init__(self) -> None:
                super().__init__([None, "Hi", None, "!"])

        async def _create(**_: object) -> _NullAwareStream:
            return _NullAwareStream()

        chatter_agent.model = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )

        state = State(user_id=1, query="hello")
        out = await chatter_agent.invoke(state, verbose=False)

        assert out.response == "Hi!"

    async def test_invoke_injects_image_query_placeholder(
        self,
        chatter_agent: ChatterAgent,
        stream_writer_capture: list,
    ) -> None:
        # When the user submits only an image, the chatter prompt should
        # still contain a coherent USER QUERY block even though state.query
        # is empty. The simplest thing to verify is that the async create
        # receives a messages list with a user message that includes the
        # placeholder text.
        captured: dict = {}

        async def _create(**kwargs):  # noqa: ANN003 - signature mirrors openai
            captured.update(kwargs)
            return _FakeStream(["ok"])

        chatter_agent.model = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )

        state = State(user_id=1, query="")
        out = await chatter_agent.invoke(state, verbose=False)

        assert out.response == "ok"
        user_message = next(
            m for m in captured["messages"] if m["role"] == "user"
        )
        assert "image" in user_message["content"].lower()

    async def test_invoke_max_tokens_falls_back_to_memory_length_when_unset(
        self,
        chatter_agent: ChatterAgent,
        stream_writer_capture: list,
    ) -> None:
        # P2-3: chatter_max_tokens unset (None) => legacy behaviour, the
        # create call uses memory_length as max_tokens.
        assert chatter_agent.config.chatter_max_tokens is None

        captured: dict = {}

        async def _create(**kwargs):  # noqa: ANN003 - signature mirrors openai
            captured.update(kwargs)
            return _FakeStream(["ok"])

        chatter_agent.model = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )

        state = State(user_id=1, query="hello")
        await chatter_agent.invoke(state, verbose=False)

        assert captured["max_tokens"] == chatter_agent.config.memory_length

    async def test_invoke_max_tokens_uses_chatter_max_tokens_when_set(
        self,
        chatter_agent: ChatterAgent,
        stream_writer_capture: list,
    ) -> None:
        # P2-3: when chatter_max_tokens is configured it wins over
        # memory_length (which keeps its meaning as a context-trim
        # threshold for the summarizer).
        chatter_agent.config.chatter_max_tokens = 2048

        captured: dict = {}

        async def _create(**kwargs):  # noqa: ANN003 - signature mirrors openai
            captured.update(kwargs)
            return _FakeStream(["ok"])

        chatter_agent.model = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )

        state = State(user_id=1, query="hello")
        await chatter_agent.invoke(state, verbose=False)

        assert captured["max_tokens"] == 2048
        assert captured["max_tokens"] != chatter_agent.config.memory_length
