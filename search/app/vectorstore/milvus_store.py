"""Minimal Milvus adapter used by the search service."""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

import numpy as np
from langchain_core.embeddings import Embeddings
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility


class Milvus:
    TEXT_FIELD = "text"
    VECTOR_FIELD = "vector"
    PK_FIELD = "pk"
    MAX_TEXT_LENGTH = 65535

    def __init__(
        self,
        embedding_function: Embeddings,
        collection_name: str,
        connection_args: dict[str, Any],
        auto_id: bool = True,
        index_params: dict[str, Any] | None = None,
    ) -> None:
        if not auto_id:
            raise ValueError("Search Milvus adapter requires auto_id=True")

        self.embedding_function = embedding_function
        self.collection_name = collection_name
        self.connection_args = connection_args
        self.index_params = index_params or {"metric_type": "COSINE"}
        self.search_params = {
            "metric_type": self.index_params.get("metric_type", "COSINE"),
            "params": self.index_params.get("params", {}),
        }
        self.alias = self._connection_alias(collection_name, connection_args)
        connections.connect(alias=self.alias, **connection_args)
        self.col = self._load_collection_if_exists()

    @staticmethod
    def _connection_alias(collection_name: str, connection_args: dict[str, Any]) -> str:
        uri = str(connection_args.get("uri", "default"))
        raw_alias = f"search_{collection_name}_{uri}"
        return re.sub(r"[^A-Za-z0-9_]", "_", raw_alias)[:255]

    def _load_collection_if_exists(self) -> Collection | None:
        if not utility.has_collection(self.collection_name, using=self.alias):
            return None

        collection = Collection(self.collection_name, using=self.alias)
        try:
            collection.load()
        except Exception as exc:
            print(f"Search collection load skipped: {exc}")
        return collection

    def _ensure_collection(self, dimension: int) -> Collection:
        if self.col is not None:
            return self.col

        schema = CollectionSchema(
            fields=[
                FieldSchema(
                    name=self.PK_FIELD,
                    dtype=DataType.INT64,
                    is_primary=True,
                    auto_id=True,
                ),
                FieldSchema(
                    name=self.TEXT_FIELD,
                    dtype=DataType.VARCHAR,
                    max_length=self.MAX_TEXT_LENGTH,
                ),
                FieldSchema(
                    name=self.VECTOR_FIELD,
                    dtype=DataType.FLOAT_VECTOR,
                    dim=dimension,
                ),
            ],
            description=f"{self.collection_name} collection",
            enable_dynamic_field=True,
        )
        self.col = Collection(self.collection_name, schema=schema, using=self.alias)
        self.col.create_index(
            field_name=self.VECTOR_FIELD,
            index_params={
                "metric_type": self.search_params["metric_type"],
                "index_type": "AUTOINDEX",
                "params": {},
            },
        )
        self.col.load()
        return self.col

    @staticmethod
    def _metadata_value(value: Any) -> Any:
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, float) and np.isnan(value):
            return None
        return value

    @classmethod
    def _vector(cls, embedding: list[float]) -> list[float]:
        return [float(value) for value in embedding]

    def add_embeddings(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        records = []
        for text, embedding, metadata in zip(texts, embeddings, metadatas):
            vector = self._vector(embedding)
            record = {
                self.TEXT_FIELD: text[: self.MAX_TEXT_LENGTH],
                self.VECTOR_FIELD: vector,
            }
            for key, value in metadata.items():
                if key in {self.PK_FIELD, self.TEXT_FIELD, self.VECTOR_FIELD}:
                    continue
                cleaned = self._metadata_value(value)
                if cleaned is not None:
                    record[key] = cleaned
            records.append(record)

        if not records:
            return

        collection = self._ensure_collection(len(records[0][self.VECTOR_FIELD]))
        collection.insert(records)
        collection.flush()

    def similarity_search_with_relevance_scores(
        self,
        query: str,
        k: int = 4,
        expr: str | None = None,
    ) -> list[tuple[SimpleNamespace, float]]:
        if self.col is None:
            return []

        query_vector = self._vector(self.embedding_function.embed_query(query))
        self.col.load()
        search_result = self.col.search(
            data=[query_vector],
            anns_field=self.VECTOR_FIELD,
            param=self.search_params,
            limit=k,
            expr=expr or "",
            output_fields=["*"],
        )

        results = []
        for hit in search_result[0]:
            fields = dict(hit.fields or {})
            page_content = fields.pop(self.TEXT_FIELD, "")
            fields.pop(self.VECTOR_FIELD, None)
            fields[self.PK_FIELD] = hit.id
            document = SimpleNamespace(page_content=page_content, metadata=fields)
            relevance_score = (float(hit.score) + 1.0) / 2.0
            results.append((document, relevance_score))
        return results
