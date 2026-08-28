"""Asynchronous chat-session title generation."""

import logging

import requests

from .state import State


def _fallback_title(state: State) -> str:
    first_user_turn = state.query.strip() or "New conversation"
    return first_user_turn[:60].rstrip() or "New conversation"


def _generate_title_with_llm(agent, state: State) -> str:
    response = agent.model.chat.completions.create(
        model=agent.llm_name,
        messages=[
            {
                "role": "system",
                "content": (
                    "Create a concise shopping conversation title of at most 12 words. "
                    "Reply in the conversation language, without quotes or punctuation."
                ),
            },
            {
                "role": "user",
                "content": f"User: {state.query}\nAssistant: {state.response}",
            },
        ],
        stream=False,
        temperature=0.0,
        max_tokens=32,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    title = (response.choices[0].message.content or "").strip()
    if not title:
        raise ValueError("LLM returned an empty title")
    return title[:200]


def _persist_session_title(agent, state: State, title: str) -> None:
    response = requests.patch(
        f"{agent.memory_base_url}/user/{state.user_id}/sessions/{state.session_id}",
        json={"title": title},
        timeout=3,
    )
    response.raise_for_status()


def maybe_generate_session_title(agent, state: State) -> bool:
    """Persist an LLM title after two conversation turns; never raise to caller."""
    if state.session_id is None:
        return False
    try:
        response = requests.get(
            f"{agent.memory_base_url}/user/{state.user_id}/sessions/{state.session_id}/messages",
            timeout=2,
        )
        response.raise_for_status()
        turn_count = len(response.json().get("messages", []))
        if turn_count < 4:
            return False
        try:
            title = _generate_title_with_llm(agent, state)
        except Exception as exc:
            logging.warning("orchestrator | LLM title generation failed: %s", exc)
            title = _fallback_title(state)
        _persist_session_title(agent, state, title)
        return True
    except Exception as exc:
        logging.warning("orchestrator | session title generation skipped: %s", exc)
        return False
