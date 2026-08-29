import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from typing import Any, Dict, List, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from openai import OpenAI

from .state import State
from .query_filters import QueryFilterMixin

logger = logging.getLogger(__name__)


class RetrieverAgent(QueryFilterMixin):
    _GUIZHOU_GIFT_CATEGORIES = ("ethnic-wear", "craft", "food", "drink")

    def __init__(
        self,
        config,
    ) -> None:
        logging.info(f"RetrieverAgent.__init__() | Initializing with llm_name={config.llm_name}, llm_port={config.llm_port}")
        # Extraction is a front-of-pipeline latency-sensitive call; prefer the
        # configured small/fast model when available.
        self.llm_name = getattr(config, "small_llm_name", None) or config.llm_name
        self.llm_port = config.llm_port
        
        # Store configuration
        self.search_url = config.retriever_port
        self.k_value = config.top_k_retrieve
        self.categories = config.categories

        retry_strategy = Retry(
            total=3,
            status_forcelist=[422, 429, 500, 502, 503, 504],
            allowed_methods=["POST"],
            backoff_factor=1,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=4, pool_maxsize=4)
        self.http_session = requests.Session()
        self.http_session.mount("https://", adapter)
        self.http_session.mount("http://", adapter)
        
        self.model = OpenAI(
            base_url=config.llm_port,
            api_key=os.environ["LLM_API_KEY"],
            timeout=getattr(config, "llm_timeout_seconds", 60.0),
            max_retries=1,
        )
        self.cache_ttl = 60.0
        self.cache: OrderedDict[str, tuple[float, Dict[str, Any]]] = OrderedDict()
        self.cache_limit = 64
        logging.info(f"RetrieverAgent.__init__() | Initialization complete")

    def _cache_key(
        self,
        entities: List[str],
        categories: List[str],
        filters: Dict[str, float],
        image: str,
        k: int,
    ) -> str:
        normalized_entities = sorted(str(entity).casefold() for entity in entities)
        normalized_categories = sorted(str(category).casefold() for category in categories)
        normalized_filters = sorted(
            (str(name).casefold(), value if isinstance(value, str) else float(value))
            for name, value in filters.items()
        )
        payload = json.dumps(
            [normalized_entities, normalized_categories, normalized_filters, bool(image), k],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        image_digest = hashlib.sha256(image.encode("utf-8")).hexdigest() if image else ""
        return f"{payload}:{image_digest}"

    def _cached_results(self, key: str, now: float) -> Dict[str, Any] | None:
        cached = self.cache.get(key)
        if cached is None:
            return None
        created_at, results = cached
        if now - created_at > self.cache_ttl:
            del self.cache[key]
            return None
        self.cache.move_to_end(key)
        return results

    def _store_results(self, key: str, now: float, results: Dict[str, Any]) -> None:
        self.cache[key] = (now, results)
        self.cache.move_to_end(key)
        while len(self.cache) > self.cache_limit:
            self.cache.popitem(last=False)

    def _broaden_gift_set_search(
        self, query: str, entities: List[str], categories: List[str], k: int
    ) -> tuple[List[str], List[str], int]:
        """Make broad gift-set requests reliably span several Guizhou categories."""
        normalized = (query or "").casefold()
        gift_set_intent = any(
            marker in normalized
            for marker in ("伴手礼", "礼盒", "gift set", "souvenir set")
        )
        if not gift_set_intent:
            return entities, categories, k

        available_categories = [
            category
            for category in self._GUIZHOU_GIFT_CATEGORIES
            if category in self.categories
        ]
        if not available_categories:
            return entities, categories, k

        if any("\u4e00" <= character <= "\u9fff" for character in query):
            broadened_entities = [
                "贵州茶",
                "贵州不辣食品饮品",
                "贵州非遗手作伴手礼",
            ]
        else:
            broadened_entities = [
                "Guizhou tea",
                "mild Guizhou food or drink",
                "Guizhou heritage craft gift",
            ]
        return broadened_entities, available_categories, max(k, 6)

    async def invoke(
        self,
        state: State,
        verbose: bool = True
    ) -> State:
        """
        Process the user query to determine categories and retrieve relevant products.
        """
        logging.info(f"RetrieverAgent.invoke() | Starting with query: {state.query}")

        # Set our k value for retrieval.
        k = self.k_value

        # Get the user query and image from the state
        image = state.image

        # Use the LLM to determine entities/categories/filters for retrieval
        start = time.monotonic()
        entities, categories, filters = await self._extract_retrieval_inputs(state)
        end = time.monotonic()
        state.timings["retriever_categories"] = end - start

        entities, categories, k = self._broaden_gift_set_search(
            state.query, entities, categories, k
        )

        if self._is_out_of_catalog(entities, categories):
            logging.info(
                "RetrieverAgent.invoke() | Specific catalog category absent; "
                "skipping vector retrieval."
            )
            state.response = self._out_of_catalog_message(state)
            state.context = f"{state.context}\n{state.response}"
            return state
        
        cache_key = self._cache_key(entities, categories, filters, image, k)
        cached_results = self._cached_results(cache_key, time.monotonic())
        state.timings["retriever_cache_hit"] = 0.0 if cached_results else 1.0
        if cached_results:
            results = cached_results
        else:
            # Query the search service.
            start = time.monotonic()
            try:
                if image:
                    logging.info(
                        "RetrieverAgent.invoke() | /query/image -- getting response.\n"
                        f"\t| entities: {entities}\n"
                        f"\t| categories: {categories}\n"
                        f"\t| filters: {filters}"
                    )
                    response = self.http_session.post(
                        f"{self.search_url}/query/image",
                        json={
                            "text": entities,
                            "image_base64": image,
                            "categories": categories,
                            "filters": filters,
                            "k": k
                        }
                    )
                else:
                    logging.info(
                        "RetrieverAgent.invoke() | /query/text -- getting response\n"
                        f"\t| query: {entities}\n"
                        f"\t| categories: {categories}\n"
                        f"\t| filters: {filters}"
                    )
                    response = self.http_session.post(
                        f"{self.search_url}/query/text",
                        json={
                            "text": entities,
                            "categories": categories,
                            "filters": filters,
                            "k": k
                        }
                    )

                response.raise_for_status()
                results = response.json()
                self._store_results(cache_key, time.monotonic(), results)

            except requests.exceptions.RequestException as e:
                if verbose:
                    logging.error(f"RetrieverAgent.invoke() | Error querying search service: {str(e)}")
                state.response = "I encountered an error while searching for products. Please try again."
                state.timings["retriever_retrieval"] = time.monotonic() - start
                return state

        start = time.monotonic()
        try:
            if results["texts"]:
                products = []
                retrieved_dict = {}
                urls = results.get("urls") or []
                prices = results.get("prices") or []
                ratings = results.get("ratings") or []
                currencies = results.get("currencies") or []
                for idx, (text, name, img) in enumerate(
                    zip(results["texts"], results["names"], results["images"])
                ):
                    products.append(text)
                    entry: Dict[str, Any] = {"image": img}
                    url = urls[idx] if idx < len(urls) else None
                    price = prices[idx] if idx < len(prices) else None
                    rating = ratings[idx] if idx < len(ratings) else None
                    currency = currencies[idx] if idx < len(currencies) else None
                    if url:
                        entry["url"] = url
                    if price is not None:
                        entry["price"] = price
                    if currency:
                        entry["currency"] = currency
                    if rating is not None:
                        entry["rating"] = rating
                    retrieved_dict[name] = entry
                state.response = "These products are available in the catalog:\n" + "\n".join(products)
                state.retrieved = retrieved_dict
            else:
                state.response = "Unfortunately there are no products closely matching the user's query."

            logging.info(
                "RetrieverAgent.invoke() | Retriever returned context "
                f"({'cache' if cached_results else 'service'})."
            )
            state.context = f"{state.context}\n{state.response}"
        finally:
            state.timings["retriever_retrieval"] = time.monotonic() - start

        logging.info(f"RetrieverAgent.invoke() | Returning final state with response.")

        return state

# Generic name for new callers.
SearchProxyAgent = RetrieverAgent
