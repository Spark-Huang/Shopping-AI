"""Batch text embedding helpers for catalog ingestion and queries."""

from __future__ import annotations

from typing import Any

from numpy import mean


def create_embeddings(
    client: Any,
    inputs: Any,
    model: str,
    query_type: str = "query",
) -> Any:
    try:
        return client.embeddings.create(
            input=inputs,
            model=model,
            encoding_format="float",
            extra_body={"input_type": query_type, "truncate": "NONE"},
        )
    except Exception:
        return client.embeddings.create(
            input=inputs,
            model=model,
            encoding_format="float",
        )


def embed_chunks_in_batches(
    client: Any,
    all_chunks: list[str],
    model: str,
    query_type: str,
    verbose: bool = False,
    batch_size: int = 32,
) -> list[list[float] | None]:
    all_chunk_embeddings = []
    num_batches = (len(all_chunks) + batch_size - 1) // batch_size
    for offset in range(0, len(all_chunks), batch_size):
        batch_chunks = all_chunks[offset : offset + batch_size]
        if verbose:
            print(
                "Embedding text batch "
                f"{offset // batch_size + 1}/{num_batches} ({len(batch_chunks)} chunks)"
            )
        try:
            response = create_embeddings(client, batch_chunks, model, query_type)
            all_chunk_embeddings.extend([item.embedding for item in response.data])
        except Exception:
            all_chunk_embeddings.extend([None for _ in batch_chunks])
    return all_chunk_embeddings


def reconstruct_embeddings(
    texts: list[str],
    all_chunk_embeddings: list[list[float] | None],
    text_chunk_counts: list[int],
) -> list[list[float] | None]:
    final_embeddings = []
    current_chunk_idx = 0
    for index, _text in enumerate(texts):
        num_chunks = text_chunk_counts[index]
        if num_chunks == 0:
            final_embeddings.append(None)
            continue

        chunk_embeddings = all_chunk_embeddings[
            current_chunk_idx : current_chunk_idx + num_chunks
        ]
        current_chunk_idx += num_chunks
        valid_chunk_embeddings = [item for item in chunk_embeddings if item is not None]
        if valid_chunk_embeddings:
            final_embeddings.append(list(mean(valid_chunk_embeddings, axis=0)))
        else:
            final_embeddings.append(None)
    return final_embeddings
