"""Parser and URL helpers for JD list pages."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import quote_plus
from xml.etree.ElementTree import Element

from crawler.dangdang import Product


def search_url(keyword: str, page: int = 1) -> str:
    return (
        "https://search.jd.com/Search"
        f"?keyword={quote_plus(keyword)}&page={2 * max(1, page) - 1}"
    )


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def _image_url(tag: Element | None) -> str:
    if tag is None:
        return ""
    for attribute in ("data-lazy-img", "data-source", "src"):
        value = _clean(tag.get(attribute))
        if value and not value.startswith("data:"):
            return f"https:{value}" if value.startswith("//") else value
    return ""


def _price(value: str | None) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", value or "")
    return float(match.group()) if match else None


def parse_products(html: str, category: str, subcategory: str = "other") -> list[Product]:
    products: list[Product] = []
    for card in _ListParser.parse(html).iter("li"):
        sku = _clean(card.get("data-sku"))
        link = next((child for child in card.iter("a") if _clean(child.get("title"))), None)
        if not sku.isdigit() or link is None:
            continue
        name = _clean(link.get("title"))
        if not name:
            continue
        price_tag = next(
            (
                child
                for child in card.iter()
                if child.get("data-price") or child.get("jd-price")
            ),
            None,
        )
        price_value = None
        if price_tag is not None:
            price_value = price_tag.get("data-price") or price_tag.get("jd-price")
        price = _price(price_value)
        products.append(
            Product(
                name=name,
                description="",
                url=f"https://item.jd.com/{sku}.html",
                price=price,
                currency="CNY" if price is not None else None,
                image=_image_url(next(iter(card.iter("img")), None)),
                category=category,
                subcategory=subcategory,
                platform="jd",
            )
        )
    return products


class _ListParser(HTMLParser):
    _SKIP = {"script", "style", "template"}
    _VOID = {"img", "br", "input", "link", "meta", "hr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("root")
        self.stack = [self.root]

    @classmethod
    def parse(cls, html: str) -> Element:
        parser = cls()
        parser.feed(html)
        parser.close()
        return parser.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self._SKIP:
            self.stack.append(Element(tag, {key: value or "" for key, value in attrs}))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self._SKIP:
            element = Element(tag, {key: value or "" for key, value in attrs})
            self.stack[-1].append(element)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP or tag in self._VOID:
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                orphan = self.stack.pop(index)
                self.stack[index - 1].append(orphan)
                del self.stack[index:]
                return

    def close(self) -> None:
        super().close()
        while len(self.stack) > 1:
            self.stack[-2].append(self.stack.pop())
