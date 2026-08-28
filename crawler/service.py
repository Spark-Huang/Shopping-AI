"""Crawler orchestration for live product refresh."""

from __future__ import annotations

from crawler.categories import category_for, normalize_keyword
from crawler.dangdang import Product, parse_products, search_url
from crawler.fetcher import Fetcher


class CrawlerService:
    def __init__(self, fetcher: Fetcher | None = None, max_pages: int = 1):
        self.fetcher = fetcher or Fetcher()
        self.max_pages = max(1, max_pages)

    def crawl(self, keyword: str) -> list[Product]:
        normalized = normalize_keyword(keyword)
        category = category_for(normalized)
        products: list[Product] = []
        for page in range(1, self.max_pages + 1):
            html = self.fetcher.fetch(search_url(normalized, page))
            products.extend(parse_products(html, category))
        return products
