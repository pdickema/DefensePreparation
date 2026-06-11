from __future__ import annotations

from pathlib import Path
from typing import Any

from paper_pipeline.metadata import examiner_slug, paper_slug
from paper_pipeline.utils import estimate_tokens, write_jsonl


def _blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    in_table = False

    for line in text.splitlines():
        is_table_line = line.strip().startswith("|") and line.strip().endswith("|")
        if is_table_line:
            in_table = True
            current.append(line)
            continue
        if in_table and current:
            blocks.append("\n".join(current).strip())
            current = []
            in_table = False
        if line.strip():
            current.append(line)
        elif current:
            blocks.append("\n".join(current).strip())
            current = []

    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if block]


def _overlap_text(text: str, overlap_tokens: int) -> str:
    if overlap_tokens <= 0:
        return ""
    words = text.split()
    return " ".join(words[-overlap_tokens:])


def chunk_paper(
    paper: dict[str, Any],
    target_tokens: int = 900,
    overlap_tokens: int = 120,
) -> list[dict[str, Any]]:
    metadata = paper.get("metadata", {})
    sections = paper.get("sections", [])
    base_row = {
        "paper_id": paper.get("paper_id", ""),
        "examiner": metadata.get("examiner", ""),
        "title": metadata.get("title", ""),
        "year": metadata.get("year"),
        "doi": metadata.get("doi", ""),
        "source_pdf": metadata.get("filename", ""),
        "sha256": metadata.get("sha256", ""),
    }
    examiner = examiner_slug(metadata)
    title = paper_slug(metadata)
    chunks: list[dict[str, Any]] = []

    for section in sections:
        pending = ""
        for block in _blocks(str(section.get("text") or "")):
            candidate = f"{pending}\n\n{block}".strip() if pending else block
            if pending and estimate_tokens(candidate) > target_tokens:
                chunks.append(
                    _make_chunk(base_row, section, pending, len(chunks) + 1, examiner, title)
                )
                overlap = _overlap_text(pending, overlap_tokens)
                pending = f"{overlap}\n\n{block}".strip() if overlap else block
            else:
                pending = candidate

        if pending:
            chunks.append(_make_chunk(base_row, section, pending, len(chunks) + 1, examiner, title))

    return chunks


def _make_chunk(
    base_row: dict[str, Any],
    section: dict[str, Any],
    text: str,
    chunk_index: int,
    examiner: str,
    title: str,
) -> dict[str, Any]:
    return {
        "chunk_id": f"{examiner}_{title}_{chunk_index:04d}",
        **base_row,
        "section": section.get("heading", ""),
        "section_level": section.get("level"),
        "page_start": section.get("page_start"),
        "page_end": section.get("page_end"),
        "chunk_index": chunk_index,
        "text": text,
        "token_count_estimate": estimate_tokens(text),
    }


def write_chunks(path: Path, chunks: list[dict[str, Any]]) -> int:
    return write_jsonl(path, chunks)
