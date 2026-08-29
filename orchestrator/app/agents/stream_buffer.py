import re
from dataclasses import dataclass, field
from typing import Callable, List

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_CJK_RATIO_THRESHOLD = 0.3


@dataclass
class StreamBuffer:
    """Hold stream events until every safety verdict is final."""

    writer: Callable[[str], None]
    events: List[str] = field(default_factory=list)
    closed: bool = False

    def add(self, event: str) -> None:
        if self.closed:
            raise RuntimeError("Cannot add events to a closed stream buffer")
        self.events.append(event)

    def flush(self) -> None:
        if self.closed:
            return
        for event in self.events:
            self.writer(event)
        self.closed = True

    def discard(self) -> None:
        self.events.clear()
        self.closed = True


def detect_language(query: str, declared: str | None = None) -> str:
    normalized = (declared or "").strip().lower()
    if normalized in ("zh", "en"):
        return "zh" if normalized == "zh" else "en"
    if not query:
        return "en"
    cjk_count = sum(len(match.group()) for match in _CJK_RE.finditer(query))
    return "zh" if cjk_count / len(query) >= _CJK_RATIO_THRESHOLD else "en"


def language_instruction(language: str) -> str:
    if language == "zh":
        return (
            "\n\nLANGUAGE: Always reply in Chinese (Simplified). "
            "Product names from the catalog stay in their original language, "
            "but every sentence you write must be in Chinese. Render each "
            "catalog price in its original currency, as provided with the "
            "product; never invent, replace, or silently convert a currency."
        )
    return (
        "\n\nLANGUAGE: Always reply in English. Render each catalog price in "
        "its original currency, as provided with the product; never invent, "
        "replace, or silently convert a currency."
    )
