import re


_BUDGET_PATTERN = re.compile(
    r"(?:monthly\s+budget|月预算|每月预算)\D*?(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def extract_monthly_budget(context: str) -> float | None:
    matches = _BUDGET_PATTERN.findall(context or "")
    if not matches:
        return None
    try:
        budget = float(matches[-1])
    except ValueError:
        return None
    return budget if budget > 0 else None


def format_monthly_budget(budget: float) -> str:
    return f"MONTHLY BUDGET: ${budget:.2f}"
