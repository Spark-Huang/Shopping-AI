"""CSV catalog ingestion orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter

if TYPE_CHECKING:
    from search.app.engine import Retriever


def create_text_chunks(
    texts: list[str], verbose: bool = False
) -> tuple[list[str], list[int]]:
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    all_chunks = []
    text_chunk_counts = []
    for text in texts:
        chunks = text_splitter.split_text(text)
        all_chunks.extend(chunks)
        text_chunk_counts.append(len(chunks))
    if verbose:
        print(f"Created {len(all_chunks)} chunks from {len(texts)} texts")
    return all_chunks, text_chunk_counts


def milvus_from_csv(retriever: Retriever, csv_path: str, verbose: bool = False) -> None:
    if retriever.embeddings_exist():
        print("Embeddings already exist; skipping catalog population.")
        return

    dataframe = pd.read_csv(csv_path)
    metadatas = dataframe.to_dict(orient="records")
    for metadata in metadatas:
        metadata.setdefault("source", "guizhou_catalog")
    # Optional cultural-story column: when present, it is appended to the
    # embedded text so vector retrieval matches cultural queries (e.g.
    # "Miao silver intangible heritage") and the story reaches the chatter
    # via the retrieval result text.
    stories = (
        dataframe["story"].fillna("").astype(str).tolist()
        if "story" in dataframe.columns
        else [""] * len(dataframe)
    )
    combined_texts = [
        f"{name} | {description} | {category},{subcategory}"
        + (f" | {story}" if story.strip() else "")
        for name, description, category, subcategory, story in zip(
            dataframe["name"].tolist(),
            dataframe["description"].tolist(),
            dataframe["category"].tolist(),
            dataframe["subcategory"].tolist(),
            stories,
        )
    ]

    text_embeddings = retriever.text_embeddings(
        combined_texts, query_type="passage", verbose=verbose
    )
    successful_texts_data = [
        (text, embedding, metadata)
        for text, embedding, metadata in zip(combined_texts, text_embeddings, metadatas)
        if embedding is not None
    ]
    if successful_texts_data:
        successful_texts, successful_embeddings, successful_metadatas = zip(
            *successful_texts_data
        )
        retriever.text_db.add_embeddings(
            texts=list(successful_texts),
            embeddings=list(successful_embeddings),
            metadatas=list(successful_metadatas),
        )

    image_embeddings = retriever.image_embeddings(
        dataframe["image"].tolist(), verbose=verbose
    )
    successful_images_data = [
        (image, embedding, metadata)
        for image, embedding, metadata in zip(
            dataframe["image"].tolist(), image_embeddings, metadatas
        )
        if embedding is not None
    ]
    if successful_images_data and retriever.image_db is not None:
        successful_images, successful_image_embeddings, successful_image_metadatas = zip(
            *successful_images_data
        )
        retriever.image_db.add_embeddings(
            texts=list(successful_images),
            embeddings=list(successful_image_embeddings),
            metadatas=list(successful_image_metadatas),
        )
