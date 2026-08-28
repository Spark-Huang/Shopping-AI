from datetime import UTC, datetime, timedelta

from crawler.fetcher import CrawlError
from search.app.freshness import (
    DEFAULT_FRESHNESS_HOURS,
    FreshnessService,
    is_fresh,
    load_freshness_hours,
)


class _FailingCrawler:
    def crawl(self, keyword):
        raise CrawlError("network unavailable")


class _SuccessfulCrawler:
    def crawl(self, keyword):
        raise AssertionError("crawl should not run")


def test_ttl_boundary_is_inclusive_and_expired_is_stale():
    now = datetime(2026, 1, 2, tzinfo=UTC)
    assert is_fresh("2026-01-01T00:00:00Z", 24, now).fresh
    assert not is_fresh("2025-12-31T23:59:59Z", 24, now).fresh
    assert not is_fresh(None, 24, now).fresh


def test_ttl_miss_triggers_refresh_branch_and_failure_degrades_stale():
    old = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    service = FreshnessService(crawler=_FailingCrawler(), ttl_hours=24)
    assert service.needs_refresh([{"crawled_at": old}])
    products, refreshed = service.refresh("thermos cup")
    assert products == []
    assert refreshed is False


def test_ttl_hit_skips_refresh_branch():
    fresh = datetime.now(UTC).isoformat()
    service = FreshnessService(crawler=_SuccessfulCrawler(), ttl_hours=24)
    assert not service.needs_refresh([{"crawled_at": fresh}])


def test_freshness_configuration_uses_setting_env_and_default(tmp_path, monkeypatch):
    setting = tmp_path / "freshness"
    monkeypatch.setenv("DATA_FRESHNESS_FILE", str(setting))
    assert load_freshness_hours() == DEFAULT_FRESHNESS_HOURS
    monkeypatch.setenv("DATA_FRESHNESS_HOURS", "12")
    assert load_freshness_hours() == 12
    setting.write_text("6", encoding="utf-8")
    assert load_freshness_hours() == 6
