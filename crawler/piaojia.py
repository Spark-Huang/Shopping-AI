"""Parser for Piaojia scenic-ticket pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs
from xml.etree.ElementTree import Element

from crawler.dangdang import parse_html

BASE_URL = "https://piaojia.cn"


@dataclass
class Ticket:
    name: str
    description: str
    url: str
    price: float | None
    online_price: float | None
    suppliers: list[str]
    opening_hours: str
    image: str
    category: str = "travel"
    subcategory: str = "景点门票"
    currency: str | None = "CNY"
    platform: str = "piaojia"

    def metadata(self, crawled_at: str) -> dict[str, object]:
        return {
            "category": self.category,
            "subcategory": self.subcategory,
            "name": f"{self.name}门票",
            "description": self.description,
            "url": self.url,
            "price": self.price,
            "currency": self.currency,
            "image": self.image,
            "platform": self.platform,
            "crawled_at": crawled_at,
        }


def list_url(region: str, keyword: str = "", page: int = 1) -> str:
    return (
        f"{BASE_URL}/jingdian/list.asp?a={region}&q={keyword}"
        "&t=1A&order=1"
        + (f"&page={page}" if page > 1 else "")
    )


def _clean(value: str | None) -> str:
    return " ".join(unescape(value or "").split())


def parse_detail_links(html: str) -> list[str]:
    links = re.findall(r"/jingdian/(detail_\d+\.html)", html)
    return sorted(set(links), key=links.index)


def parse_categories(html: str) -> list[str]:
    categories: list[str] = []
    for href in re.findall(r'href="list\.asp\?[^"]+">', html):
        values = parse_qs(href.removeprefix("list.asp?").removesuffix('">'))
        category = _clean(values.get("k", [""])[0])
        if category and category not in categories:
            categories.append(category)
    return categories


def _text(element: Element | None) -> str:
    return _clean("".join(element.itertext()) if element is not None else "")


def _number(value: str | None) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", value or "")
    return float(match.group()) if match else None


def _image(root: Element) -> str:
    for parent in root.iter():
        classes = parent.get("class", "").split()
        if "slides" not in classes:
            continue
        for image in parent.iter("img"):
            source = (image.get("src") or "").strip()
            if source:
                return source if source.startswith("http") else f"https:{source}"
    return "Piaojia scenic detail page; no photo available"


def _opening_hours(root: Element) -> str:
    for paragraph in root.iter("p"):
        if _text(paragraph).startswith("开放时间："):
            return _text(paragraph).removeprefix("开放时间：")
    return "详见详情页"


def _introduction(root: Element) -> str:
    paragraphs = [
        _text(node)
        for node in root.iter("p")
        if _text(node) and not _text(node).startswith(("开放时间", "门票价格", "景区电话"))
    ]
    return " ".join(paragraphs[:4])[:280] or "详见详情页"


def parse_detail(html: str, path: str) -> Ticket | None:
    root = parse_html(html)
    heading = next((node for node in root.iter("h1") if _text(node)), None)
    name = _text(heading)
    if not name:
        return None

    ticket_price = None
    for paragraph in root.iter("p"):
        text = _text(paragraph)
        if text.startswith("门票价格："):
            ticket_price = _number(_text(next(paragraph.iter("b"), None)) or text)

    online_price = None
    for container in root.iter():
        classes = container.get("class", "").split()
        if "top" in classes:
            text = _text(container)
            match = re.search(r"最低价:.*?[¥￥](\d+(?:\.\d+)?)", text)
            if match:
                online_price = float(match.group(1))

    suppliers = []
    for item in root.iter("li"):
        spans = {
            _clean(" ".join(span.get("class", "").split())): span
            for span in item.iter("span")
        }
        supplier = _text(spans.get("shop"))
        if supplier and supplier not in suppliers and supplier != "供应商":
            suppliers.append(supplier)

    opening_hours = _opening_hours(root)
    introduction = _introduction(root)
    online = f"网上最低报价¥{online_price:g}起" if online_price else "网上最低报价见详情页"
    supplier_text = "、".join(suppliers) if suppliers else "见详情页"
    description = (
        f"门票价格¥{ticket_price:g}；{online}；开放时间{opening_hours}；"
        f"供应商：{supplier_text}；简介：{introduction}"
        if ticket_price
        else f"门票价格见详情页；{online}；开放时间{opening_hours}；"
        f"供应商：{supplier_text}；简介：{introduction}"
    )
    return Ticket(
        name=name,
        description=description,
        url=f"{BASE_URL}/jingdian/{path}",
        price=ticket_price,
        online_price=online_price,
        suppliers=suppliers,
        opening_hours=opening_hours,
        image=_image(root),
    )
