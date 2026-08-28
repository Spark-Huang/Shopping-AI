import pytest
from pytest import MonkeyPatch

from orchestrator.app.agents.cartops.agent import CartAgent


def test_budget_reminder_is_absent_before_trigger() -> None:
    agent = CartAgent.__new__(CartAgent)

    result = agent._maybe_impulse_budget_note(
        "added 1 Silk Dress",
        type(
            "Cart",
            (),
            {"contents": [{"item": "Silk Dress", "amount": 1, "price": 200.0}]},
        )(),
        1,
    )

    assert result is None


def test_triggered_reminder_gently_suggests_budget_when_unset(
    monkeypatch: MonkeyPatch,
) -> None:
    agent = CartAgent.__new__(CartAgent)
    agent.memory_base_url = "http://memory"
    cart = type(
        "Cart",
        (),
        {
            "contents": [
                {"item": "Silk Dress", "amount": 1, "price": 200.0},
                {"item": "Leather Bag", "amount": 1, "price": 180.0},
                {"item": "Cashmere Coat", "amount": 1, "price": 220.0},
            ]
        },
    )()

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"context": ""}

    monkeypatch.setattr(
        "orchestrator.app.agents.cartops.agent.requests.get",
        lambda url, timeout: Response(),
    )

    result = agent._maybe_impulse_budget_note(
        "added 1 Cashmere Coat", cart, 42
    )

    assert result is not None
    assert result.startswith("Gentle note:")
    assert "Me" in result
    assert "Budget alert" not in result
