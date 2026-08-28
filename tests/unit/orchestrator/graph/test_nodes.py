
"""Unit tests for ``orchestrator.app.graph``.

The graph module ships two kinds of artifacts:

* ``GraphNodes`` and ``GraphRouting`` - small async callables that the
  LangGraph runtime invokes for each node/edge. They are pure Python except
  for a few HTTP calls, which we stub.
* ``create_graph`` - wires everything together and compiles a LangGraph. We
  smoke-test it to make sure the factory does not raise and returns a
  compiled runnable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
import requests

from orchestrator.app.graph import nodes as graph_mod
from orchestrator.app.agents.state import Cart, SafetyResult, State, last_non_empty
from orchestrator.app.graph import GraphNodes, GraphRouting, create_graph
from langgraph.graph import END, START, StateGraph


@dataclass
class _HttpRecorder:
    gets: List[Dict[str, Any]] = field(default_factory=list)
    posts: List[Dict[str, Any]] = field(default_factory=list)


class _FakeResponse:
    def __init__(self, payload: Dict[str, Any], status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def json(self) -> Dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture
def install_config(monkeypatch: pytest.MonkeyPatch, base_config) -> SimpleNamespace:
    """Install a known config into the graph module's private global.

    The module stores config as a module-level ``_config`` that is populated
    by ``create_graph``. Unit tests that call ``GraphNodes`` directly must
    set this explicitly.
    """
    GraphNodes.configure(base_config)
    return base_config


@pytest.fixture
def http_recorder(monkeypatch: pytest.MonkeyPatch) -> _HttpRecorder:
    recorder = _HttpRecorder()

    def _fake_get(url: str, timeout: int = 10, **_: Any):
        recorder.gets.append({"url": url, "timeout": timeout})
        if url.endswith("/context"):
            return _FakeResponse({"context": "prior chat"})
        if url.endswith("/memory"):
            return _FakeResponse(
                {
                    "semantic_memory": ["prefers blue dresses"],
                    "context": "prior chat\nLong-term memory: prefers blue dresses",
                }
            )
        if url.endswith("/cart"):
            return _FakeResponse(
                {"cart": [{"item": "Silk Dress", "amount": 1, "price": 49.99}]}
            )
        if url.endswith("/orders"):
            return _FakeResponse(
                {"orders": [{"item": "Silk Dress", "price": 49.99, "purchased_at": "2026-08-01"}]}
            )
        return _FakeResponse({})

    def _fake_post(url: str, json: Dict[str, Any], timeout: int = 10, **_: Any):
        recorder.posts.append({"url": url, "json": json, "timeout": timeout})
        if url.endswith("/safety/input/check"):
            # Echo query back → is_safe True.
            return _FakeResponse(
                {"response": [{"role": "assistant", "content": json["query"]}]}
            )
        if url.endswith("/safety/output/check"):
            return _FakeResponse(
                {"response": [{"role": "assistant", "content": json["query"]}]}
            )
        return _FakeResponse({})

    monkeypatch.setattr(graph_mod.requests, "get", _fake_get)
    monkeypatch.setattr(graph_mod.requests, "post", _fake_post)
    return recorder


# ---------------------------------------------------------------------------
# GraphNodes.get_memory
# ---------------------------------------------------------------------------


class TestGetMemory:
    async def test_populates_context_and_cart_on_success(
        self, install_config, http_recorder: _HttpRecorder
    ) -> None:
        state = State(user_id=42, query="hi")

        result = await GraphNodes.get_memory(state)

        assert result.context == "prior chat\nLong-term memory: prefers blue dresses"
        assert result.cart.contents == [
            {"item": "Silk Dress", "amount": 1, "price": 49.99}
        ]
        assert result.recent_orders.entries[0]["item"] == "Silk Dress"
        assert "memory" in result.timings

        urls = [call["url"] for call in http_recorder.gets]
        assert any(u.endswith("/user/42/context") for u in urls)
        assert any(u.endswith("/user/42/cart") for u in urls)
        assert any(u.endswith("/user/42/orders") for u in urls)

    async def test_spending_recall_sets_monthly_order_summary(
        self, install_config, http_recorder: _HttpRecorder
    ) -> None:
        state = State(user_id=42, query="how much have I spent this month")

        result = await GraphNodes.get_memory(state)

        assert result.next_agent == ""
        assert result.response == "1 orders, total $49.99 this month: Silk Dress"

    async def test_spending_recall_with_no_current_orders_reports_zero(
        self, install_config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fake_get(url: str, timeout: int = 10, **_: Any):
            if url.endswith("/orders"):
                return _FakeResponse(
                    {
                        "orders": [
                            {
                                "item": "Silk Dress",
                                "price": 49.99,
                                "purchased_at": "2000-01-01T00:00:00Z",
                            }
                        ]
                    }
                )
            if url.endswith("/memory"):
                return _FakeResponse({"semantic_memory": [], "context": ""})
            return _FakeResponse({"context": "", "cart": []})

        monkeypatch.setattr(graph_mod.requests, "get", _fake_get)
        state = State(user_id=42, query="这个月花了多少")

        result = await GraphNodes.get_memory(state)

        assert result.response == "0 orders, total $0.00 this month"

    async def test_http_error_leaves_empty_context_and_cart(
        self,
        install_config,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _boom(*_: Any, **__: Any) -> None:
            raise requests.exceptions.ConnectionError("down")

        monkeypatch.setattr(graph_mod.requests, "get", _boom)

        state = State(user_id=7, query="hi")
        result = await GraphNodes.get_memory(state)

        assert result.context == ""
        assert result.cart.contents == []
        assert "memory" in result.timings


# ---------------------------------------------------------------------------
# SafetyResults nodes
# ---------------------------------------------------------------------------


class TestSafetyResultsNodes:
    async def test_input_check_returns_safe_when_content_matches(
        self, install_config, http_recorder: _HttpRecorder
    ) -> None:
        state = State(user_id=1, query="what's for dinner")

        result = await GraphNodes.check_input_safety(state)

        assert result["is_safe"] is True
        assert "safety_input_check" in result["safety_timings"]

    async def test_input_check_flags_mismatched_response_as_unsafe(
        self,
        install_config,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _post_unsafe(url: str, json: Dict[str, Any], timeout: int = 10, **_: Any):
            return _FakeResponse(
                {"response": [{"role": "assistant", "content": "BLOCKED"}]}
            )

        monkeypatch.setattr(graph_mod.requests, "post", _post_unsafe)
        state = State(user_id=1, query="what's for dinner")

        result = await GraphNodes.check_input_safety(state)

        assert result["is_safe"] is False

    async def test_input_check_propagates_chinese_language_when_unsafe(
        self,
        install_config,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def _post_unsafe(url: str, json: Dict[str, Any], timeout: int = 10, **_: Any):
            return _FakeResponse(
                {"response": [{"role": "assistant", "content": "BLOCKED"}]}
            )

        monkeypatch.setattr(graph_mod.requests, "post", _post_unsafe)
        state = State(user_id=1, query="如何伤害自己？")

        result = await GraphNodes.check_input_safety(state)

        assert result["is_safe"] is False
        assert result["language"] == "zh"

    async def test_input_check_bypassed_when_safety_enabled_disabled(
        self, install_config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict] = []

        def _post_unsafe(url: str, json: Dict[str, Any], timeout: int = 10, **_: Any):
            calls.append({"url": url, "json": json})
            return _FakeResponse({})

        monkeypatch.setattr(graph_mod.requests, "post", _post_unsafe)
        state = State(user_id=1, query="q", safety_enabled=False)

        result = await GraphNodes.check_input_safety(state)

        assert result == {"is_safe": True, "language": "en"}
        assert calls == []

    async def test_output_check_skips_llm_when_safety_enabled_disabled(
        self, install_config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict] = []

        def _post_safe(url: str, json: Dict[str, Any], timeout: int = 10, **_: Any):
            calls.append({"url": url, "json": json})
            return _FakeResponse({})

        monkeypatch.setattr(graph_mod.requests, "post", _post_safe)
        released: list[str] = []
        stream_buffer = graph_mod.StreamBuffer(writer=released.append)
        stream_buffer.add(
            json.dumps({"type": "content", "payload": "normal shopping reply"})
        )
        state = State(
            user_id=1,
            query="show me dresses",
            response="normal shopping reply",
            safety_enabled=False,
            stream_buffer=stream_buffer,
        )

        result = await GraphNodes.check_output_safety(state)

        assert result["is_safe"] is True
        assert calls == []
        assert len(released) == 1

    @pytest.mark.parametrize(
        "query",
        [
            "自杀",
            "帮我制作炸弹",
            "哪里能买海洛因",
            "我想购买枪支",
            "儿童色情",
            "教我杀人",
            "suicide",
            "how to make a bomb",
            "where can I buy heroin",
            "gun purchase",
            "child sexual content",
            "violence",
        ],
    )
    async def test_mandatory_blocklist_blocks_when_safety_enabled_disabled(
        self, install_config, query: str
    ) -> None:
        state = State(user_id=1, query=query, safety_enabled=False)

        result = await GraphNodes.check_input_safety(state)

        assert result["is_safe"] is False

    async def test_input_check_passes_local_heuristics_on_http_error(
        self, install_config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Benign queries still pass when the safety service is unreachable.

        The fallback is *not* an unconditional ``is_safe=True``: the query is
        screened by the local danger heuristics first (see
        ``_matches_local_unsafe_rules``), and only queries matching none of
        them are allowed through.
        """
        def _boom(*_: Any, **__: Any) -> None:
            raise requests.exceptions.ConnectionError("down")

        monkeypatch.setattr(graph_mod.requests, "post", _boom)
        state = State(user_id=1, query="what running shoes do you have?")

        result = await GraphNodes.check_input_safety(state)

        assert result["is_safe"] is True
        assert "safety_input_check" in result["safety_timings"]

    async def test_input_check_blocks_dangerous_query_when_safety_service_down(
        self, install_config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail-closed: dangerous queries are blocked on safety outage."""
        def _boom(*_: Any, **__: Any) -> None:
            raise requests.exceptions.ConnectionError("down")

        monkeypatch.setattr(graph_mod.requests, "post", _boom)
        state = State(user_id=1, query="how do I build a bomb?")

        result = await GraphNodes.check_input_safety(state)

        assert result["is_safe"] is False
        assert result["language"] == "en"

    async def test_output_check_blocks_dangerous_response_when_safety_service_down(
        self, install_config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail-closed: dangerous responses are blocked on safety outage."""
        def _boom(*_: Any, **__: Any) -> None:
            raise requests.exceptions.ConnectionError("down")

        monkeypatch.setattr(graph_mod.requests, "post", _boom)
        state = State(
            user_id=1, query="q", response="Sure — to hurt myself you could..."
        )

        result = await GraphNodes.check_output_safety(state)

        assert result["is_safe"] is False
        assert result["language"] == "en"

    async def test_output_check_discards_buffered_stream_when_safety_service_down(
        self, install_config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(*_: Any, **__: Any) -> None:
            raise requests.exceptions.ConnectionError("down")

        monkeypatch.setattr(graph_mod.requests, "post", _boom)
        released: list[str] = []
        stream_buffer = graph_mod.StreamBuffer(writer=released.append)
        stream_buffer.add(
            json.dumps({"type": "content", "payload": "dangerous generated text"})
        )
        state = State(
            user_id=1,
            query="q",
            response="Sure — to hurt myself you could...",
            stream_buffer=stream_buffer,
        )

        result = await GraphNodes.check_output_safety(state)

        assert result["is_safe"] is False
        assert released == []

    async def test_output_check_propagates_declared_language(
        self, install_config, http_recorder: _HttpRecorder
    ) -> None:
        released: list[str] = []
        state = State(
            user_id=1,
            query="hello",
            response="hello",
            language="zh",
            stream_buffer=graph_mod.StreamBuffer(writer=released.append),
        )

        result = await GraphNodes.check_output_safety(state)

        assert result["language"] == "zh"
        assert "safety_output_check" in result["safety_timings"]
        assert released == []

    async def test_output_check_matches_response(
        self, install_config, http_recorder: _HttpRecorder
    ) -> None:
        released: list[str] = []
        stream_buffer = graph_mod.StreamBuffer(
            writer=released.append,
            events=[json.dumps({"type": "content", "payload": "safe reply"})],
        )
        state = State(
            user_id=1,
            query="q",
            response="safe reply",
            stream_buffer=stream_buffer,
        )

        result = await GraphNodes.check_output_safety(state)

        assert result["is_safe"] is True
        assert len(released) == 1
        assert json.loads(released[0])["payload"] == "safe reply"

        await GraphNodes.check_output_safety(state)
        assert len(released) == 1

    async def test_output_check_missing_response_structure_defaults_safe(
        self, install_config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _post(url: str, json: Dict[str, Any], timeout: int = 10, **_: Any):
            return _FakeResponse({})

        monkeypatch.setattr(graph_mod.requests, "post", _post)
        released: list[str] = []
        stream_buffer = graph_mod.StreamBuffer(
            writer=released.append,
            events=[json.dumps({"type": "content", "payload": "anything"})],
        )
        state = State(
            user_id=1,
            query="q",
            response="anything",
            stream_buffer=stream_buffer,
        )

        result = await GraphNodes.check_output_safety(state)

        assert result["is_safe"] is True
        assert len(released) == 1


# ---------------------------------------------------------------------------
# Safety check / unsafe-output nodes
# ---------------------------------------------------------------------------


class TestCheckSafetyResultAndUnsafe:
    async def test_check_safety_node_returns_timings_dict(self) -> None:
        safety_result = SafetyResult(is_safe=False, safety_timings={"safety_input_check": 0.25})

        result = await GraphNodes.check_safety_node(safety_result)

        assert result == {"timings": {"safety_input_check": 0.25}}

    async def test_unsafe_output_streams_safe_message(
        self,
        install_config,
        stream_writer_capture: list,
    ) -> None:
        safety_result = SafetyResult(is_safe=False, language="en")

        result = await GraphNodes.unsafe_output(safety_result)

        assert result["response"] == install_config.unsafe_messages["en"]
        # Exactly one payload frame should have been emitted.
        assert len(stream_writer_capture) == 1
        payload = json.loads(stream_writer_capture[0])
        assert payload["type"] == "content"
        assert payload["payload"] == install_config.unsafe_messages["en"]

    async def test_unsafe_output_uses_chinese_for_chinese_query(
        self,
        install_config,
        stream_writer_capture: list,
    ) -> None:
        safety_result = SafetyResult(is_safe=False, language="zh")

        result = await GraphNodes.unsafe_output(safety_result)

        assert result["response"] == install_config.unsafe_messages["zh"]
        assert len(stream_writer_capture) == 1

    async def test_unsafe_output_falls_back_without_english_message(
        self,
        install_config,
        stream_writer_capture: list,
    ) -> None:
        install_config.unsafe_messages = {"zh": "请勿讨论危险内容。"}

        result = await GraphNodes.unsafe_output(SafetyResult(is_safe=False, language="fr"))

        assert result["response"] == "请勿讨论危险内容。"

    async def test_unsafe_output_falls_back_to_legacy_message_when_dict_empty(
        self,
        install_config,
        stream_writer_capture: list,
    ) -> None:
        install_config.unsafe_messages = {}
        install_config.unsafe_message = "Legacy safe reply"

        result = await GraphNodes.unsafe_output(SafetyResult(is_safe=False))

        assert result["response"] == "Legacy safe reply"


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class TestGraphRouting:
    @pytest.mark.parametrize(
        "is_safe,expected",
        [(True, "chatter_node"), (False, "unsafe_output")],
    )
    def test_decide_if_input_safe(self, is_safe: bool, expected: str) -> None:
        assert GraphRouting.decide_if_input_safe(SafetyResult(is_safe=is_safe)) == expected

    @pytest.mark.parametrize(
        "is_safe,expected",
        [(True, "summarize_node"), (False, "unsafe_output")],
    )
    def test_decide_if_output_safe(self, is_safe: bool, expected: str) -> None:
        assert GraphRouting.decide_if_output_safe(SafetyResult(is_safe=is_safe)) == expected


# ---------------------------------------------------------------------------
# create_graph smoke test
# ---------------------------------------------------------------------------


class TestCreateGraphSmoke:
    def test_create_graph_compiles_without_error(self, base_config) -> None:
        # Any object with ``invoke`` / ``decide_function`` suffices — LangGraph
        # only inspects the callables, not their types.
        class _Noop:
            async def invoke(self, state: State, verbose: bool = False) -> State:
                return state

            def decide_function(self, state: State) -> str:
                return "chatter"

        compiled = create_graph(
            cart_agent=_Noop(),
            retriever_agent=_Noop(),
            planner_agent=_Noop(),
            chatter_agent=_Noop(),
            summary_agent=_Noop(),
            config=base_config,
        )

        # A compiled LangGraph exposes ``invoke``/``astream`` among others; we
        # only need to prove the factory produced a runnable callable.
        assert callable(getattr(compiled, "ainvoke", None)) or callable(
            getattr(compiled, "astream", None)
        )
        assert GraphNodes._config is base_config

    async def test_compiled_stream_is_safe_input_gated(
        self,
        install_config,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def memory(state: State) -> State:
            return state

        async def planner(state: State) -> State:
            state.next_agent = "chatter"
            return state

        def decide(state: State) -> str:
            return state.next_agent

        async def chatter(state: State) -> State:
            from langgraph.config import get_stream_writer

            get_stream_writer()(
                json.dumps({"type": "content", "payload": "CHATTER SHOULDN'T STREAM"})
            )
            return state

        async def summary(state: State) -> State:
            return state

        async def unsafe_input(_state: State) -> dict:
            return {"is_safe": False, "language": "en"}

        async def safe_output(_state: State) -> dict:
            return {"is_safe": True, "language": "en"}

        monkeypatch.setattr(GraphNodes, "get_memory", staticmethod(memory))
        monkeypatch.setattr(
            GraphNodes, "check_input_safety", staticmethod(unsafe_input)
        )
        monkeypatch.setattr(
            GraphNodes, "check_output_safety", staticmethod(safe_output)
        )
        compiled = create_graph(
            cart_agent=SimpleNamespace(invoke=summary),
            retriever_agent=SimpleNamespace(invoke=summary),
            planner_agent=SimpleNamespace(invoke=planner, decide_function=decide),
            chatter_agent=SimpleNamespace(invoke=chatter),
            summary_agent=SimpleNamespace(invoke=summary),
            config=install_config,
        )

        events = [event async for event in compiled.astream(
            State(user_id=1, query="unsafe"), stream_mode="custom"
        )]

        assert len(events) == 1
        assert json.loads(events[0])["payload"] == install_config.unsafe_messages["en"]

    async def test_compiled_stream_waits_for_output_verdict(
        self,
        install_config,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def memory(state: State) -> State:
            return state

        async def planner(state: State) -> State:
            state.next_agent = "chatter"
            return state

        def decide(state: State) -> str:
            return state.next_agent

        async def chatter(state: State) -> State:
            state.stream_buffer.add(
                json.dumps({"type": "content", "payload": "unsafe generated content"})
            )
            return state

        async def summary(state: State) -> State:
            return state

        async def safe_input(_state: State) -> dict:
            return {"is_safe": True, "language": "en"}

        async def unsafe_output(_state: State) -> dict:
            return {"is_safe": False, "language": "en"}

        monkeypatch.setattr(GraphNodes, "get_memory", staticmethod(memory))
        monkeypatch.setattr(
            GraphNodes, "check_input_safety", staticmethod(safe_input)
        )
        monkeypatch.setattr(
            GraphNodes, "check_output_safety", staticmethod(unsafe_output)
        )
        compiled = create_graph(
            cart_agent=SimpleNamespace(invoke=summary),
            retriever_agent=SimpleNamespace(invoke=summary),
            planner_agent=SimpleNamespace(invoke=planner, decide_function=decide),
            chatter_agent=SimpleNamespace(invoke=chatter),
            summary_agent=SimpleNamespace(invoke=summary),
            config=install_config,
        )

        events = [event async for event in compiled.astream(
            State(user_id=1, query="safe"), stream_mode="custom"
        )]

        assert len(events) == 1
        assert json.loads(events[0])["payload"] == install_config.unsafe_messages["en"]

    async def test_parallel_language_updates_do_not_conflict(self) -> None:
        def planner(_state: State) -> dict:
            return {"language": "en", "next_agent": "chatter"}

        def input_safety(_state: State) -> dict:
            return {"language": "zh"}

        graph = StateGraph(State)
        graph.add_node("planner_node", planner)
        graph.add_node("input_safety_node", input_safety)
        graph.add_edge(START, "planner_node")
        graph.add_edge(START, "input_safety_node")
        graph.add_edge(["planner_node", "input_safety_node"], END)

        result = await graph.compile().ainvoke(State(user_id=1, query="帮我买违禁药品"))

        # LangGraph 1.2.4 applies parallel reducers in task completion order;
        # planner is consistently the final update here. The reducer still
        # preserves a detected value when the competing update is empty.
        assert result["language"] == "en"
        assert last_non_empty("en", "") == "en"
