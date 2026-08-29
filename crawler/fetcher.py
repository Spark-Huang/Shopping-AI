"""Rate-limited HTTP fetcher for public product pages."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable

import httpx


class CrawlError(RuntimeError):
    """Raised when an external catalog request cannot be completed."""


@dataclass
class Fetcher:
    timeout: float = 15.0
    min_interval: float = 2.0
    max_interval: float = 3.0
    retry_count: int = 2
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        self._last_request_at: float | None = None
        self.client = httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "ShoppingAI-Catalog/1.0"},
            trust_env=False,
        )

    def fetch(
        self,
        url: str,
        *,
        encoding: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> str:
        for attempt in range(self.retry_count + 1):
            self._pace()
            try:
                response = self.client.get(url, headers=extra_headers or {})
                response.raise_for_status()
                response.encoding = encoding or response.charset_encoding or "utf-8"
                return response.text
            except httpx.HTTPError as exc:
                if attempt == self.retry_count:
                    raise CrawlError(f"fetch failed: {url}") from exc
                self.sleeper(2 ** attempt)
        raise CrawlError(f"fetch failed: {url}")

    def _pace(self) -> None:
        now = self.clock()
        if self._last_request_at is not None:
            delay = random.uniform(self.min_interval, self.max_interval)
            remaining = delay - (now - self._last_request_at)
            if remaining > 0:
                self.sleeper(remaining)
        self._last_request_at = self.clock()

    def close(self) -> None:
        self.client.close()
