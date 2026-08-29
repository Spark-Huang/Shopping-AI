"""Parser for Dangdang server-rendered product search pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from xml.etree.ElementTree import Element
from urllib.parse import quote_from_bytes



@dataclass
class Product:
    name: str
    description: str
    url: str
    price: float | None
    image: str
    category: str
    subcategory: str
    platform: str = "dangdang"

    def metadata(self, crawled_at: str) -> dict[str, Any]:
        return {
            "category": self.category,
            "subcategory": self.subcategory,
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "price": self.price,
            "image": self.image,
            "platform": self.platform,
            "crawled_at": crawled_at,
        }


def search_url(keyword: str, page: int = 1) -> str:
    encoded = quote_from_bytes(keyword.encode("gbk"))
    return (
        "http://search.dangdang.com/"
        f"?key={encoded}&act=input&page_index={max(1, page)}"
    )


def _clean(value: str | None) -> str | None:
    return " ".join((value or "").split()) or None


def _absolute_url(value: str | None) -> str:
    url = (value or "").strip()
    return f"https:{url}" if url.startswith("//") else url


def _price(value: str | None) -> float | None:
    match = re.search(r"\d+(?:[.,]\d+)?", value or "")
    return float(match.group().replace(",", "")) if match else None


def parse_products(html: str, category: str) -> list[Product]:
    document = parse_html(html)
    products: list[Product] = []
    for card in document.iter("li"):
        sku = card.attrib.get("id", "")
        link = next(
            (child for child in card.iter("a") if child.get("title")),
            None,
        )
        if not sku.isdigit() or link is None:
            continue
        name = _clean(link.get("title"))
        if not name:
            continue
        price_tag = None
        for child in card.iter("span"):
            if "price_n" in child.get("class", []):
                price_tag = child
                break
        image_tag = next((child for child in card.iter("img")), None)
        image_source = (
            image_tag.get("data-original") or image_tag.get("src") or ""
            if image_tag is not None
            else ""
        )
        if "url_none" in image_source:
            image_source = ""
        products.append(
            Product(
                name=name,
                description=name,
                url=f"https://product.dangdang.com/{sku}.html",
                price=_price(price_tag.text if price_tag is not None else None),
                image=_absolute_url(image_source),
                category=category,
                subcategory=category,
            )
        )
    return products


class _CatalogHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("root")
        self.stack = [self.root]
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        element = Element(tag, dict(attrs))
        self.stack[-1].append(element)
        self.stack.append(element)
        self.current = element
        if tag in {"br", "img", "input", "link", "meta"}:
            self.stack.pop()
            self.current = self.stack[-1]

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].append(Element(tag, dict(attrs)))

    def handle_data(self, data):
        if self.current.text is None:
            self.current.text = ""
        self.current.text += data

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                self.current = self.stack[-1]
                break


def parse_html(html: str) -> Element:
    parser = _CatalogHtmlParser()
    parser.feed(html)
    parser.close()
    return parser.root
