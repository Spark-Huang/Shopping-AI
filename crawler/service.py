"""Crawler orchestration for live product refresh."""

from __future__ import annotations

from crawler.categories import normalize_keyword
from crawler.dangdang import Product, parse_products, search_url
from crawler.fetcher import Fetcher
from crawler.jd import parse_products as parse_jd
from crawler.jd import search_url as jd_search_url
from crawler.yiwugo import YiwugoFetcher
from crawler.yiwugo import parse_products as parse_yiwugo

SUBCATEGORIES = {
    "茅台": "酱香白酒",
    "习酒": "酱香白酒",
    "珍酒": "酱香白酒",
    "董酒": "酱香白酒",
    "国台": "酱香白酒",
    "青酒": "酱香白酒",
    "蜡染": "蜡染",
    "刺绣": "苗绣",
    "苗银": "苗银",
    "银饰": "苗银",
    "酸汤": "酸汤底料",
    "老干妈": "调味酱",
    "波波糖": "地方小吃",
    "刺梨": "刺梨饮品",
    "都匀毛尖": "都匀毛尖",
}


def _contains_any(keyword: str, names: set[str]) -> bool:
    return any(name in keyword for name in names)


def _category(keyword: str) -> str:
    if _contains_any(keyword, {"茅台", "习酒", "珍酒", "董酒", "国台", "青酒"}):
        return "wine"
    if _contains_any(keyword, {"蜡染", "刺绣", "苗银", "银饰", "披肩"}):
        return "craft"
    return "food"


def _subcategory(keyword: str) -> str:
    for name, subcategory in SUBCATEGORIES.items():
        if name in keyword:
            return subcategory
    return "other"


class CrawlerService:
    def __init__(
        self,
        fetcher: Fetcher | None = None,
        max_pages: int = 1,
        platform: str = "dangdang",
    ):
        self.fetcher = fetcher or Fetcher()
        self.max_pages = max(1, max_pages)
        if platform not in {"dangdang", "jd", "yiwugo"}:
            raise ValueError(f"unknown platform: {platform}")
        self.platform = platform

    def crawl(self, keyword: str, region: str = "贵州") -> list[Product]:
        normalized = normalize_keyword(keyword)
        category = _category(normalized)
        subcategory = _subcategory(normalized)
        if region and self.platform == "dangdang":
            normalized = f"{region} {normalized}"
        products: list[Product] = []
        if self.platform == "jd":
            for page in range(1, self.max_pages + 1):
                products.extend(
                    parse_jd(
                        self.fetcher.fetch(jd_search_url(normalized, page)),
                        category,
                        subcategory,
                    )
                )
        elif self.platform == "yiwugo":
            yiwugo_fetcher = YiwugoFetcher(self.fetcher)
            for page in range(1, self.max_pages + 1):
                products.extend(
                    parse_yiwugo(
                        yiwugo_fetcher.fetch_page(normalized, page),
                        category,
                        subcategory,
                    )
                )
        else:
            for page in range(1, self.max_pages + 1):
                products.extend(
                    parse_products(
                        self.fetcher.fetch(search_url(normalized, page), encoding="gbk"),
                        category,
                        subcategory,
                    )
                )
        return products
