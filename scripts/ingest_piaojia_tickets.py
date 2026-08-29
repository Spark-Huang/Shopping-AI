"""Crawl and ingest Guizhou scenic tickets from Piaojia."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import httpx
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.fetcher import Fetcher
from crawler.piaojia import BASE_URL, parse_categories, parse_detail, parse_detail_links
from crawler.timeutil import utc_now


def _proxy_fetcher() -> Fetcher:
    fetcher = Fetcher(min_interval=0.4, max_interval=0.8)
    proxy = os.environ.get(
        "PIAOJIA_PROXY",
        os.environ.get("HTTPS_PROXY", os.environ.get("https_proxy", "")),
    )
    fetcher.client = httpx.Client(
        timeout=fetcher.timeout,
        follow_redirects=True,
        trust_env=False,
        transport=httpx.HTTPTransport(proxy=proxy or None),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126 Safari/537.36"
            ),
            "Referer": f"{BASE_URL}/jingdian/",
        },
    )
    return fetcher


def crawl(region: str, output: Path, max_pages: int) -> list[dict[str, object]]:
    fetcher = _proxy_fetcher()
    first = fetcher.fetch(
        f"{BASE_URL}/jingdian/list.asp?a={quote(region)}&q=&t=1A&order=1",
        encoding="utf-8",
    )
    categories = parse_categories(first)
    paths: dict[str, None] = {}
    for category in categories:
        for page in range(1, max_pages + 1):
            url = (
                f"{BASE_URL}/jingdian/list.asp?a={quote(region)}&q=&"
                f"k={quote(category)}&t=&page={page}"
            )
            html = fetcher.fetch(url, encoding="utf-8")
            found = parse_detail_links(html)
            if not found:
                break
            paths.update(dict.fromkeys(found))
            if not re.search(rf'page={page + 1}["\']', html):
                break

    crawled_at = utc_now()
    products = []
    for path in paths:
        try:
            detail = parse_detail(
                fetcher.fetch(f"{BASE_URL}/jingdian/{path}", encoding="utf-8"), path
            )
        except Exception as exc:
            print(f"fetch failed: {path}: {exc}", file=sys.stderr)
            continue
        if detail is not None:
            products.append(detail.metadata(crawled_at))
    output.write_text(
        json.dumps({"source": BASE_URL, "count": len(products), "products": products}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return products


def ingest(payload: Path) -> tuple[int, int]:
    from search.app.embeddings.text import RetrieverConfig
    from search.app.engine import Retriever
    from search.app.settings import load_config_with_overrides, search_config_path

    data = load_config_with_overrides(str(ROOT / "platform/configs/search/config.yaml"))
    retriever = Retriever(
        RetrieverConfig(
            text_embed_port=os.environ.get("EMBED_BASE_URL", data["text_embed_port"]),
            image_embed_port=os.environ.get("EMBED_BASE_URL", data["image_embed_port"]),
            text_model_name=os.environ.get("EMBED_NAME", data["text_model_name"]),
            image_model_name=data["image_model_name"],
            db_port=os.environ.get("MILVUS_URI", data["db_port"]),
            db_name=data["db_name"],
            sim_threshold=data["sim_threshold"],
            text_collection=data["text_collection"],
            image_collection=data["image_collection"],
            category_prefilter_k=data.get("category_prefilter_k", 50),
        )
    )
    data = json.loads(payload.read_text(encoding="utf-8"))
    products = data["products"]
    if data.get("embedding_model") != retriever.text_model_name:
        retriever.ingest_products(products)
    return len(products), retriever.text_db.col.num_entities


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="贵州")
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--output", default="/tmp/piaojia-tickets.json")
    parser.add_argument("--ingest", action="store_true")
    args = parser.parse_args()
    payload = Path(args.output)
    if not payload.exists():
        crawl(args.region, payload, args.max_pages)
    products = json.loads(payload.read_text(encoding="utf-8"))["products"]
    inserted = 0
    if args.ingest:
        _, inserted = ingest(payload)
        print(f"payload={len(products)} milvus_entities={inserted}")
    else:
        print(json.dumps({"count": len(products)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
