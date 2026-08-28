"""Command-line entry point for catalog crawling."""

from __future__ import annotations

import argparse
import json

from crawler.service import CrawlerService
from crawler.timeutil import utc_now


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("keyword")
    parser.add_argument("--max-pages", type=int, default=1)
    args = parser.parse_args()
    try:
        products = CrawlerService(max_pages=args.max_pages).crawl(args.keyword)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    crawled_at = utc_now()
    print(
        json.dumps(
            {
                "status": "ok",
                "count": len(products),
                "products": [product.metadata(crawled_at) for product in products],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
