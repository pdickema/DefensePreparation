from __future__ import annotations

import os
from typing import Any

from paper_pipeline.config import AppConfig
from paper_pipeline.utils import read_jsonl


def build_index(config: AppConfig) -> list[str]:
    chunks = read_jsonl(config.path("chunks_jsonl"))
    if not chunks:
        return ["No chunks found. Run process and chunk before build-index."]

    if config.index.provider == "openai":
        if not config.index.allow_external_embeddings or not os.getenv("OPENAI_API_KEY"):
            return [
                "OpenAI embeddings are disabled. Set allow_external_embeddings true and "
                "provide OPENAI_API_KEY only if you intentionally want external API calls."
            ]
        return ["OpenAI embeddings hook is reserved for a later explicitly enabled version."]

    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    except Exception as exc:
        return [
            "Local indexing dependencies are not installed. Run: "
            "python -m pip install -e \".[index]\"",
            f"Import error: {exc}",
        ]

    client = chromadb.PersistentClient(path=str(config.path("index_dir")))
    embedding_function = SentenceTransformerEmbeddingFunction(model_name=config.index.model)
    collection = client.get_or_create_collection(
        name="paper_chunks",
        embedding_function=embedding_function,
    )

    ids = [str(chunk["chunk_id"]) for chunk in chunks]
    documents = [str(chunk.get("text", "")) for chunk in chunks]
    metadatas = [_chromadb_metadata(chunk) for chunk in chunks]
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return [f"Indexed {len(chunks)} chunks in {config.path('index_dir')}"]


def query_index(config: AppConfig, query: str, n_results: int = 5) -> list[str]:
    if not config.path("index_dir").exists():
        return ["No index exists yet. Run build-index after processing PDFs."]

    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    except Exception as exc:
        return [
            "Local indexing dependencies are not installed. Run: "
            "python -m pip install -e \".[index]\"",
            f"Import error: {exc}",
        ]

    client = chromadb.PersistentClient(path=str(config.path("index_dir")))
    embedding_function = SentenceTransformerEmbeddingFunction(model_name=config.index.model)
    collection = client.get_or_create_collection(
        name="paper_chunks",
        embedding_function=embedding_function,
    )
    results = collection.query(query_texts=[query], n_results=n_results)
    lines: list[str] = []
    for metadata, document in zip(
        results.get("metadatas", [[]])[0],
        results.get("documents", [[]])[0],
        strict=False,
    ):
        lines.append(
            "\n".join(
                [
                    f"Paper: {metadata.get('title', '')}",
                    f"Examiner: {metadata.get('examiner', '')}",
                    f"Year: {metadata.get('year', '')}",
                    f"Section: {metadata.get('section', '')}",
                    f"Source PDF: {metadata.get('source_pdf', '')}",
                    f"Page range: {metadata.get('page_start', '')}-{metadata.get('page_end', '')}",
                    f"Text: {document[:700]}",
                ]
            )
        )
    return lines or ["No matching chunks found."]


def _chromadb_metadata(chunk: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
    allowed = {}
    for key, value in chunk.items():
        if key == "text":
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            allowed[key] = value
        else:
            allowed[key] = str(value)
    return allowed
