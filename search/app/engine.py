"""Search engine facade for text and image catalog retrieval."""

from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from typing import Any

from openai import OpenAI

from search.app.embeddings.image import ImageEmbeddings
from search.app.embeddings.text import RetrieverConfig, TextEmbeddings
from search.app.filtering import (
    apply_structured_filters,
    coerce_float,
    matches_categories,
    milvus_category_expr,
)
from search.app.freshness import FreshnessService
from search.app.images import (
    image_path_to_base64,
    image_url_to_base64,
    is_path,
    is_url,
    resize_base64_image,
)
from search.app.ingestion.batch_embed import (
    create_embeddings,
    embed_chunks_in_batches,
    reconstruct_embeddings,
)
from search.app.ingestion.csv_loader import create_text_chunks, milvus_from_csv
from search.app.vectorstore.milvus_store import Milvus

_CATEGORY_FALLBACK_LIMIT = 2
_MAX_VARCHAR_LENGTH = 65535


class Retriever:
    _coerce_float = staticmethod(coerce_float)
    _milvus_category_expr = staticmethod(milvus_category_expr)

    def _image_conversion(self, name: str):
        conversions = {
            "image_url_to_base64": image_url_to_base64,
            "image_path_to_base64": image_path_to_base64,
            "resize_base64_image": resize_base64_image,
        }
        return conversions[name]

    def _image_conversion(self, name: str):
        conversions = {
            "image_url_to_base64": image_url_to_base64,
            "image_path_to_base64": image_path_to_base64,
            "resize_base64_image": resize_base64_image,
        }
        return conversions[name]

    def __init__(self, config: RetrieverConfig):
        self.text_embed_port = config.text_embed_port
        self.image_embed_port = config.image_embed_port or config.text_embed_port
        self.text_model_name = config.text_model_name
        self.image_model_name = (config.image_model_name or "").strip()
        self.image_enabled = bool(self.image_model_name)
        self.db_port = config.db_port
        self.db_name = config.db_name
        self.sim_threshold = config.sim_threshold
        self.text_collection = config.text_collection
        self.image_collection = config.image_collection
        self.category_prefilter_k = max(config.category_prefilter_k, 1)
        self.freshness = FreshnessService()

        embed_key = os.environ["EMBED_API_KEY"]
        self.text_client = OpenAI(
            api_key=embed_key,
            base_url=self.text_embed_port,
        )
        self.image_client = (
            OpenAI(
                api_key=embed_key,
                base_url=self.image_embed_port,
            )
            if self.image_enabled
            else None
        )

        self.text_embeddings_obj = TextEmbeddings(self)
        self.image_embeddings_obj = (
            ImageEmbeddings(self) if self.image_enabled else None
        )
        self.text_db = Milvus(
            embedding_function=self.text_embeddings_obj,
            collection_name=self.text_collection,
            connection_args={"uri": self.db_port},
            auto_id=True,
            index_params={"metric_type": "COSINE"},
        )
        self.image_db = (
            Milvus(
                embedding_function=self.image_embeddings_obj,
                collection_name=self.image_collection,
                connection_args={"uri": self.db_port},
                auto_id=True,
                index_params={"metric_type": "COSINE"},
            )
            if self.image_enabled
            else None
        )

    def embeddings_exist(self) -> bool:
        try:
            text_count = 0
            if self.text_db.col:
                self.text_db.col.flush()
                text_count = self.text_db.col.num_entities

            image_count = 0
            if self.image_db is not None and self.image_db.col:
                self.image_db.col.flush()
                image_count = self.image_db.col.num_entities

            if self.image_enabled:
                return text_count > 0 and image_count > 0
            return text_count > 0
        except Exception:
            return False

    def ingest_products(self, products: list[dict[str, Any]]) -> None:
        if not products:
            return
        texts = [
            f"{product['name']} | {product['description']} | {product['category']},{product['subcategory']}"
            for product in products
        ]
        embeddings = self.text_embeddings(texts, query_type="passage", verbose=False)
        successful = [
            (text, embedding, product)
            for text, embedding, product in zip(texts, embeddings, products)
            if embedding is not None
        ]
        if successful:
            chunks, vectors, metadata = zip(*successful)
            self.text_db.add_embeddings(
                texts=list(chunks), embeddings=list(vectors), metadatas=list(metadata)
            )

    def catalog_records(self, keyword: str, limit: int = 4) -> list[dict[str, Any]]:
        results = self.text_db.similarity_search_with_relevance_scores(
            keyword, k=max(1, limit)
        )
        return [dict(result[0].metadata) for result in results]

    def _create_embeddings(
        self,
        client: Any,
        inputs: Any,
        model: str,
        query_type: str = "query",
    ) -> Any:
        return create_embeddings(client, inputs, model, query_type)

    def _create_text_chunks(
        self, texts: list[str], verbose: bool = False
    ) -> tuple[list[str], list[int]]:
        return create_text_chunks(texts, verbose)

    def _embed_chunks_in_batches(
        self,
        all_chunks: list[str],
        query_type: str,
        verbose: bool = False,
        batch_size: int = 32,
    ) -> list[list[float] | None]:
        return embed_chunks_in_batches(
            self.text_client,
            all_chunks,
            self.text_model_name,
            query_type,
            verbose,
            batch_size,
        )

    def _reconstruct_embeddings(
        self,
        texts: list[str],
        all_chunk_embeddings: list[list[float] | None],
        text_chunk_counts: list[int],
    ) -> list[list[float] | None]:
        return reconstruct_embeddings(
            texts, all_chunk_embeddings, text_chunk_counts
        )

    def _apply_structured_filters(
        self,
        results: list[tuple[Any, float]],
        filters: dict[str, Any] | None,
        verbose: bool = False,
    ) -> list[tuple[Any, float]]:
        return apply_structured_filters(results, filters, verbose)

    def embed_chunk(
        self, chunk: str, query_type: str = "query"
    ) -> list[float]:
        response = self._create_embeddings(
            client=self.text_client,
            inputs=chunk,
            model=self.text_model_name,
            query_type=query_type,
        )
        return response.data[0].embedding

    def text_embeddings(
        self,
        texts: list[str],
        query_type: str = "query",
        verbose: bool = False,
    ) -> list[list[float] | None]:
        if not texts:
            return []

        all_chunks, text_chunk_counts = create_text_chunks(texts, verbose)
        if not all_chunks:
            return [None] * len(texts)

        all_chunk_embeddings = embed_chunks_in_batches(
            self.text_client,
            all_chunks,
            self.text_model_name,
            query_type,
            verbose,
        )
        return reconstruct_embeddings(texts, all_chunk_embeddings, text_chunk_counts)

    def image_embeddings(
        self, texts: list[str], verbose: bool = False
    ) -> list[list[float] | None]:
        if not self.image_enabled:
            return [None for _ in texts]

        all_embeddings = []
        batch_size = 32
        for offset in range(0, len(texts), batch_size):
            batch_texts = texts[offset : offset + batch_size]
            input_data_list = []
            for text in batch_texts:
                try:
                    input_data = text
                    if is_url(text):
                        input_data = self._image_conversion("image_url_to_base64")(text)
                    elif is_path(text):
                        input_data = self._image_conversion("image_path_to_base64")(text)

                    if input_data and len(input_data) > _MAX_VARCHAR_LENGTH:
                        resized = self._image_conversion("resize_base64_image")(input_data)
                        if resized and len(resized) <= _MAX_VARCHAR_LENGTH:
                            input_data = resized
                        else:
                            input_data = None
                except Exception:
                    input_data = None
                input_data_list.append(input_data)

            valid_inputs = [data for data in input_data_list if data is not None]
            try:
                if valid_inputs:
                    response = self.image_client.embeddings.create(
                        input=valid_inputs,
                        model=self.image_model_name,
                        encoding_format="float",
                    )
                    batch_embeddings = iter(
                        [item.embedding for item in response.data]
                    )
                else:
                    batch_embeddings = iter([])
            except Exception:
                batch_embeddings = iter([])

            reconstructed_batch = []
            for data in input_data_list:
                if data is None:
                    reconstructed_batch.append(None)
                    continue
                try:
                    reconstructed_batch.append(next(batch_embeddings))
                except StopIteration:
                    reconstructed_batch.append(None)
            all_embeddings.extend(reconstructed_batch)

        return all_embeddings

    def milvus_from_csv(self, csv_path: str, verbose: bool = False) -> None:
        milvus_from_csv(self, csv_path, verbose)

    def _expanded_search_k(
        self, k: int, query_count: int, categories: list[str]
    ) -> int:
        expanded = max(
            k * query_count,
            self.category_prefilter_k if categories else 0,
        )
        return min(expanded, 100)

    def _rank_and_filter(
        self,
        results: list[tuple[Any, float]],
        filters: dict[str, Any] | None,
        limit: int | None = None,
        verbose: bool = False,
    ) -> list[tuple[Any, float]]:
        ranked = [result for result in results if result[1] > self.sim_threshold]
        ranked = sorted(ranked, key=lambda item: item[1], reverse=True)
        ranked = apply_structured_filters(ranked, filters=filters, verbose=verbose)
        return ranked[:limit] if limit is not None else ranked

    async def retrieve(
        self,
        query: list[str],
        categories: list[str],
        filters: dict[str, Any] | None = None,
        image: str = "",
        k: int = 4,
        image_bool: bool = False,
        verbose: bool = True,
    ) -> tuple[
        list[str],
        list[str],
        list[float],
        list[str],
        list[str],
        list[str],
        list[float | None],
        list[float | None],
    ]:
        local_queries = query or ["Can you find me something like this image?"]
        categories = [
            category.strip().lower() for category in categories if category.strip()
        ]

        if image_bool and not self.image_enabled:
            image_bool = False

        if image_bool:
            tasks = [
                asyncio.to_thread(
                    self.text_db.similarity_search_with_relevance_scores,
                    local_query,
                    k=self._expanded_search_k(k, len(local_queries), categories),
                    expr=milvus_category_expr(categories) or None,
                )
                for local_query in local_queries
            ]
            base64_string = image.replace(
                "data:application/octet-stream", "data:image/jpeg"
            )
            tasks.append(
                asyncio.to_thread(
                    self.image_db.similarity_search_with_relevance_scores,
                    base64_string,
                    k=self._expanded_search_k(k, len(local_queries), categories),
                    expr=milvus_category_expr(categories) or None,
                )
            )
            unformatted_results = await asyncio.gather(*tasks)
        else:
            tasks = [
                asyncio.to_thread(
                    self.text_db.similarity_search_with_relevance_scores,
                    local_query,
                    k=self._expanded_search_k(k, len(local_queries), categories),
                    expr=milvus_category_expr(categories) or None,
                )
                for local_query in local_queries
            ]
            unformatted_results = await asyncio.gather(*tasks)

        sorted_unformatted_results = [
            sorted(results, key=lambda item: item[1], reverse=True)
            for results in unformatted_results
        ]

        if image_bool:
            interleaved_results = sorted(
                [
                    result
                    for results in sorted_unformatted_results
                    for result in results
                ],
                key=lambda item: item[1],
                reverse=True,
            )
        else:
            interleaved_results = []
            active_iterators = [iter(results) for results in sorted_unformatted_results]
            while active_iterators:
                current_iterator = active_iterators.pop(0)
                try:
                    interleaved_results.append(next(current_iterator))
                    active_iterators.append(current_iterator)
                except StopIteration:
                    pass

        seen_ids = set()
        all_results = []
        for result in interleaved_results:
            pk_value = result[0].metadata.get("pk")
            identifier = str(pk_value) if pk_value is not None else None
            if identifier is not None and identifier not in seen_ids:
                seen_ids.add(identifier)
                all_results.append(result)

        if image_bool or not categories:
            ranked_results = self._rank_and_filter(
                all_results[:k], filters, verbose=verbose
            )
            category_mismatch = False
        else:
            prefiltered = [
                result
                for result in all_results
                if matches_categories(result[0], categories)
            ]
            if prefiltered:
                ranked_results = self._rank_and_filter(
                    prefiltered, filters, limit=k, verbose=verbose
                )
                category_mismatch = False
            else:
                ranked_results = self._rank_and_filter(
                    all_results[: self.category_prefilter_k],
                    filters,
                    limit=min(k, _CATEGORY_FALLBACK_LIMIT),
                    verbose=verbose,
                )
                category_mismatch = bool(ranked_results)

        final_texts = []
        for result in ranked_results:
            text = f"{result[0].page_content}\nPRICE: {result[0].metadata['price']}"
            if category_mismatch:
                text += "\nCATEGORY_MISMATCH: true"
            final_texts.append(text)

        return (
            final_texts,
            [str(result[0].metadata["pk"]) for result in ranked_results],
            [result[1] for result in ranked_results],
            [result[0].metadata["name"] for result in ranked_results],
            [result[0].metadata["image"] for result in ranked_results],
            [
                result[0].metadata.get("url") or "" for result in ranked_results
            ],
            [
                coerce_float(result[0].metadata.get("price"))
                for result in ranked_results
            ],
            [
                coerce_float(result[0].metadata.get("rating"))
                for result in ranked_results
            ],
        )
