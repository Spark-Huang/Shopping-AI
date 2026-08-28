from types import SimpleNamespace

from orchestrator.app.agents.session_titles import maybe_generate_session_title
from orchestrator.app.agents.state import State


class Agent:
    llm_name = "test-model"
    memory_base_url = "http://memory"


class Response:
    def __init__(self, body):
        self.status_code = 200
        self._body = body

    def json(self):
        return self._body

    def raise_for_status(self):
        return None


def _state():
    return State(user_id=1, session_id=5, query="买化妆台和衣服", response="found")


def test_llm_title_generated_after_two_turns(monkeypatch):
    calls = {}

    def get(url, timeout):
        calls["get"] = url
        return Response({"messages": [{}] * 4})

    def create(**kwargs):
        calls["messages"] = kwargs["messages"]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="  买化妆台和衣服  ")
                )
            ]
        )

    def patch(url, json, timeout):
        calls["patch"] = (url, json)
        return Response({})

    monkeypatch.setattr("orchestrator.app.agents.session_titles.requests.get", get)
    monkeypatch.setattr("orchestrator.app.agents.session_titles.requests.patch", patch)
    agent = Agent()
    agent.model = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    assert maybe_generate_session_title(agent, _state()) is True
    assert calls["patch"] == ("http://memory/user/1/sessions/5", {"title": "买化妆台和衣服"})


def test_llm_failure_falls_back_to_truncated_first_message(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.app.agents.session_titles.requests.get",
        lambda url, timeout: Response({"messages": [{}] * 4}),
    )

    def patch(url, json, timeout):
        assert json == {"title": "买化妆台和衣服"}
        return Response({})

    monkeypatch.setattr(
        "orchestrator.app.agents.session_titles.requests.patch", patch
    )
    agent = Agent()
    agent.model = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: 1 / 0))
    )

    assert maybe_generate_session_title(agent, _state()) is True


def test_failure_is_contained(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.app.agents.session_titles.requests.get",
        lambda url, timeout: (_ for _ in ()).throw(RuntimeError("down")),
    )
    assert maybe_generate_session_title(Agent(), _state()) is False
