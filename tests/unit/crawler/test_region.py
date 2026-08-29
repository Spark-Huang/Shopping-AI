from crawler.service import CrawlerService


class _FakeFetcher:
    def __init__(self) -> None:
        self.urls = []

    def fetch(self, url: str) -> str:
        self.urls.append(url)
        return ""


def _service() -> tuple[CrawlerService, _FakeFetcher]:
    fetcher = _FakeFetcher()
    return CrawlerService(fetcher=fetcher), fetcher


def _decoded(url: str) -> str:
    from urllib.parse import unquote_to_bytes

    encoded = url.split("key=", 1)[1].split("&", 1)[0]
    return unquote_to_bytes(encoded).decode("gbk")


def test_crawler_uses_guizhou_by_default():
    service, fetcher = _service()
    service.crawl("特产")
    assert _decoded(fetcher.urls[0]) == "贵州 特产"


def test_crawler_uses_selected_region():
    service, fetcher = _service()
    service.crawl("特产", region="四川")
    assert _decoded(fetcher.urls[0]) == "四川 特产"


def test_crawler_respects_region_in_user_query():
    service, fetcher = _service()
    service.crawl("北京的手机")
    assert _decoded(fetcher.urls[0]) == "贵州 北京的手机"
