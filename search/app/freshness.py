"""Product freshness policy and live catalog refresh."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from crawler.fetcher import CrawlError
from crawler.service import CrawlerService
from crawler.timeutil import utc_now

DEFAULT_FRESHNESS_HOURS = 24.0


@dataclass(frozen=True)
class FreshnessDecision:
    fresh: bool
    reason: str


def load_freshness_hours() -> float:
    user_setting = Path(
        os.environ.get("DATA_FRESHNESS_FILE", "/tmp/shopping-ai-data-freshness")
    )
    try:
        user_value = float(user_setting.read_text(encoding="utf-8").strip())
        if user_value > 0:
            return user_value
    except (FileNotFoundError, ValueError, OSError):
        pass
    try:
        env_value = float(os.environ["DATA_FRESHNESS_HOURS"])
        if env_value > 0:
            return env_value
    except (KeyError, ValueError):
        pass
    return DEFAULT_FRESHNESS_HOURS


def is_fresh(
    crawled_at: str | None, ttl_hours: float, now: datetime | None = None
) -> FreshnessDecision:
    current = now or datetime.now(UTC)
    if not crawled_at:
        return FreshnessDecision(False, "missing crawled_at")
    try:
        timestamp = datetime.fromisoformat(crawled_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return FreshnessDecision(False, "invalid crawled_at")
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    age_hours = (current - timestamp).total_seconds() / 3600
    if age_hours < 0:
        return FreshnessDecision(False, "crawled_at is in the future")
    return FreshnessDecision(
        age_hours <= ttl_hours,
        "age within TTL" if age_hours <= ttl_hours else "age exceeds TTL",
    )


class FreshnessService:
    def __init__(
        self,
        crawler: CrawlerService | None = None,
        ttl_hours: float | None = None,
    ):
        self.crawler = crawler or CrawlerService()
        self.ttl_hours = (
            ttl_hours if ttl_hours is not None else load_freshness_hours()
        )

    def needs_refresh(
        self, records: list[dict[str, Any]], now: datetime | None = None
    ) -> bool:
        if not records:
            return True
        return any(
            not is_fresh(
                str(record.get("crawled_at") or ""), self.ttl_hours, now
            ).fresh
            for record in records
        )

    def refresh(self, keyword: str) -> tuple[list[dict[str, Any]], bool]:
        try:
            crawled_at = utc_now()
            products = self.crawler.crawl(keyword)
            if not products:
                raise CrawlError("external catalog returned no products")
            return [product.metadata(crawled_at) for product in products], True
        except Exception as exc:
            print(f"Catalog refresh failed; falling back to existing data: {exc}")
            return [], False
