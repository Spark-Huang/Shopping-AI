import pytest

from orchestrator.app.agents.budget import extract_monthly_budget


@pytest.mark.parametrize(
    ("context", "expected"),
    [
        ("", None),
        ("No preference stored", None),
        ("MONTHLY BUDGET: $50.00", 50.0),
        ("earlier $25 monthly budget; latest MONTHLY BUDGET: $75.50", 75.5),
        ("monthly budget: $0", None),
        ("每月预算：500", 500.0),
    ],
)
def test_extract_monthly_budget(context: str, expected: float | None) -> None:
    assert extract_monthly_budget(context) == expected
