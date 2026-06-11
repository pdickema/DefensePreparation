from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from paper_pipeline.config import AppConfig
from paper_pipeline.defense_prep import METHOD_TERMS, STOPWORDS, THEORY_TERMS
from paper_pipeline.manifest import OperationResult
from paper_pipeline.utils import (
    ensure_dir,
    estimate_tokens,
    read_json,
    read_jsonl,
    slugify,
    write_jsonl,
)


def export_llm_corpus(config: AppConfig) -> OperationResult:
    export_dir = ensure_dir(config.path("llm_export_dir"))
    chunks = _filtered_chunks(read_jsonl(config.path("chunks_jsonl")), config)
    papers = _load_papers(config.path("json_dir"))

    messages = [f"Ensured LLM export directory: {export_dir}"]
    _write_prompt_template(export_dir / "llm_prompt_template.md")
    write_jsonl(export_dir / "chunks_for_rag.jsonl", _rag_rows(chunks, config))

    if not chunks:
        _write_empty_overview(export_dir / "corpus_overview.md")
        messages.append(
            "No chunks found yet. Run process and chunk before using the LLM exports."
        )
        messages.append(f"Wrote LLM prompt template: {export_dir / 'llm_prompt_template.md'}")
        messages.append(f"Wrote empty RAG export: {export_dir / 'chunks_for_rag.jsonl'}")
        return OperationResult(messages=messages)

    _write_corpus_overview(export_dir / "corpus_overview.md", chunks, papers)
    examiner_paths = _write_examiner_packs(export_dir, chunks, papers, config)

    messages.extend(
        [
            f"Wrote LLM corpus overview: {export_dir / 'corpus_overview.md'}",
            f"Wrote RAG JSONL export: {export_dir / 'chunks_for_rag.jsonl'}",
            f"Wrote LLM prompt template: {export_dir / 'llm_prompt_template.md'}",
        ]
    )
    messages.extend(f"Wrote examiner LLM pack: {path}" for path in examiner_paths)
    return OperationResult(messages=messages)


def _filtered_chunks(chunks: list[dict[str, Any]], config: AppConfig) -> list[dict[str, Any]]:
    if config.llm_export.include_references:
        return chunks
    return [chunk for chunk in chunks if not _is_reference_chunk(chunk)]


def _is_reference_chunk(chunk: dict[str, Any]) -> bool:
    section = str(chunk.get("section") or "").strip().lower()
    return section in {"references", "bibliography"} or section.startswith("references")


def _load_papers(json_dir: Path) -> dict[str, dict[str, Any]]:
    if not json_dir.exists():
        return {}
    papers: dict[str, dict[str, Any]] = {}
    for path in sorted(json_dir.glob("*.json")):
        paper = read_json(path)
        papers[str(paper.get("paper_id") or path.stem)] = paper
    return papers


def _rag_rows(chunks: list[dict[str, Any]], config: AppConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in chunks:
        row = dict(chunk)
        text = str(row.get("text") or "")
        if not config.llm_export.include_full_chunk_text:
            row.pop("text", None)
            row["text_excerpt"] = _excerpt(text, config.llm_export.max_chars_per_chunk)
        rows.append(row)
    return rows


def _write_empty_overview(path: Path) -> None:
    lines = [
        "# LLM Corpus Overview",
        "",
        "No chunks were found yet.",
        "",
        "Next steps:",
        "",
        "```powershell",
        "python -m paper_pipeline.cli process",
        "python -m paper_pipeline.cli chunk",
        "python -m paper_pipeline.cli export-llm",
        "```",
        "",
        "No external API calls are made by this export command.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_corpus_overview(
    path: Path,
    chunks: list[dict[str, Any]],
    papers: dict[str, dict[str, Any]],
) -> None:
    examiners = sorted({str(chunk.get("examiner") or "Unknown examiner") for chunk in chunks})
    paper_keys = {
        (
            str(chunk.get("paper_id") or ""),
            str(chunk.get("examiner") or "Unknown examiner"),
            str(chunk.get("title") or "Untitled"),
            str(chunk.get("year") or ""),
            str(chunk.get("doi") or ""),
        )
        for chunk in chunks
    }
    exported_tokens = sum(estimate_tokens(chunk.get("text", "")) for chunk in chunks)
    lines = [
        "# LLM Corpus Overview",
        "",
        "This export is generated locally from processed PDFs. No external API calls are made.",
        "",
        "## Corpus Size",
        "",
        f"- Examiners: {len(examiners)}",
        f"- Papers: {len(paper_keys)}",
        f"- Chunks: {len(chunks)}",
        f"- Estimated tokens in exported chunks: {exported_tokens}",
        "",
        "## Examiners And Papers",
        "",
    ]

    by_examiner: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for _, examiner, title, year, doi in paper_keys:
        by_examiner[examiner].append((year, title, doi))
    for examiner in examiners:
        lines.extend([f"### {examiner}", ""])
        for year, title, doi in sorted(by_examiner[examiner]):
            doi_text = f", DOI: {doi}" if doi else ""
            lines.append(f"- {year}: {title}{doi_text}")
        lines.append("")

    quality_lines = _quality_lines(papers)
    lines.extend(["## Quality Notes", ""])
    lines.extend(quality_lines or ["- No processed paper quality notes found."])
    lines.append("")
    lines.extend(
        [
            "## Recommended Use",
            "",
            "- Use `examiner_pack_*.md` for copy/paste into an LLM chat.",
            "- Use `chunks_for_rag.jsonl` for local or external RAG tooling.",
            "- Ask the LLM to cite `chunk_id`, paper title, section, and source PDF.",
        ]
    )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _write_examiner_packs(
    export_dir: Path,
    chunks: list[dict[str, Any]],
    papers: dict[str, dict[str, Any]],
    config: AppConfig,
) -> list[Path]:
    paths: list[Path] = []
    by_examiner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        by_examiner[str(chunk.get("examiner") or "Unknown examiner")].append(chunk)

    for examiner in sorted(by_examiner):
        examiner_chunks = sorted(
            by_examiner[examiner],
            key=lambda chunk: (
                str(chunk.get("title") or ""),
                int(chunk.get("chunk_index") or 0),
            ),
        )
        path = export_dir / f"examiner_pack_{slugify(examiner)}.md"
        lines = _examiner_pack_lines(examiner, examiner_chunks, papers, config)
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def _examiner_pack_lines(
    examiner: str,
    chunks: list[dict[str, Any]],
    papers: dict[str, dict[str, Any]],
    config: AppConfig,
) -> list[str]:
    paper_ids = sorted({str(chunk.get("paper_id") or "") for chunk in chunks})
    relevant_papers = {pid: papers[pid] for pid in paper_ids if pid in papers}
    selected = chunks[: config.llm_export.max_chunks_per_examiner]
    lines = [
        f"# LLM Examiner Pack: {examiner}",
        "",
        "Use this pack as local, private context for doctoral-defense preparation.",
        "Ask the LLM to cite chunk IDs and source PDFs when making claims.",
        "",
        "## Quality Note",
        "",
    ]
    lines.extend(_quality_lines(relevant_papers) or ["- No processed paper quality notes found."])
    lines.extend(["", "## Papers", ""])
    lines.extend(_paper_lines(chunks))
    lines.extend(["", "## Theme Signals", ""])
    lines.extend(_counter_lines(_frequent_terms(chunks), empty="- No recurring terms found."))
    lines.extend(["", "## Method Signals", ""])
    lines.extend(_counter_lines(_configured_term_counts(chunks, METHOD_TERMS)))
    lines.extend(["", "## Theory Signals", ""])
    lines.extend(_counter_lines(_configured_term_counts(chunks, THEORY_TERMS)))
    lines.extend(["", "## Section Signals", ""])
    section_counts = Counter(str(chunk.get("section") or "Unknown") for chunk in chunks)
    lines.extend(_counter_lines(section_counts))
    lines.extend(["", "## Selected Chunk Excerpts", ""])
    lines.append(
        f"Showing {len(selected)} of {len(chunks)} chunks. "
        "Use `chunks_for_rag.jsonl` for the complete machine-readable export."
    )
    lines.append("")

    for chunk in selected:
        lines.extend(_chunk_excerpt_lines(chunk, config.llm_export.max_chars_per_chunk))
    return lines


def _paper_lines(chunks: list[dict[str, Any]]) -> list[str]:
    paper_counts: Counter[tuple[str, str, str, str, str]] = Counter()
    for chunk in chunks:
        key = (
            str(chunk.get("paper_id") or ""),
            str(chunk.get("title") or "Untitled"),
            str(chunk.get("year") or ""),
            str(chunk.get("doi") or ""),
            str(chunk.get("source_pdf") or ""),
        )
        paper_counts[key] += 1

    lines: list[str] = []
    for (_, title, year, doi, source_pdf), count in sorted(paper_counts.items()):
        doi_text = f", DOI: {doi}" if doi else ""
        lines.append(f"- {year}: {title}{doi_text} ({count} chunks, source: `{source_pdf}`)")
    return lines or ["- No papers found."]


def _quality_lines(papers: dict[str, dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for paper in sorted(
        papers.values(),
        key=lambda item: str(item.get("metadata", {}).get("title", "")),
    ):
        metadata = paper.get("metadata", {})
        conversion = paper.get("conversion", {})
        if not isinstance(metadata, dict) or not isinstance(conversion, dict):
            continue
        filename = metadata.get("filename") or paper.get("paper_id") or "unknown paper"
        tool = conversion.get("actual_tool") or conversion.get("primary_tool") or "unknown"
        fallback = "fallback used" if conversion.get("fallback_used") else "primary conversion"
        warnings = [str(warning) for warning in conversion.get("warnings", [])]
        warning_text = f" Warnings: {'; '.join(warnings)}" if warnings else ""
        lines.append(f"- {filename}: {tool}, {fallback}.{warning_text}")
    return lines


def _frequent_terms(chunks: list[dict[str, Any]], limit: int = 20) -> Counter[str]:
    text = "\n".join(str(chunk.get("text") or "").lower() for chunk in chunks)
    words = [
        word
        for word in re.findall(r"[a-z][a-z\-]{3,}", text)
        if word not in STOPWORDS and not word.startswith("http")
    ]
    return Counter(words).most_common(limit)


def _configured_term_counts(chunks: list[dict[str, Any]], terms: list[str]) -> Counter[str]:
    text = "\n".join(str(chunk.get("text") or "").lower() for chunk in chunks)
    return Counter({term: text.count(term.lower()) for term in terms if text.count(term.lower())})


def _counter_lines(
    counter: Counter[str] | list[tuple[str, int]],
    empty: str = "- None found.",
) -> list[str]:
    items = counter.most_common(20) if isinstance(counter, Counter) else counter
    if not items:
        return [empty]
    return [f"- {term}: {count}" for term, count in items]


def _chunk_excerpt_lines(chunk: dict[str, Any], max_chars: int) -> list[str]:
    text = _excerpt(str(chunk.get("text") or ""), max_chars)
    return [
        f"### {chunk.get('chunk_id', 'unknown chunk')}",
        "",
        f"- Paper: {chunk.get('title', '')}",
        f"- Year: {chunk.get('year', '')}",
        f"- DOI: {chunk.get('doi', '')}",
        f"- Section: {chunk.get('section', '')}",
        f"- Source PDF: `{chunk.get('source_pdf', '')}`",
        "",
        "```text",
        text,
        "```",
        "",
    ]


def _excerpt(text: str, max_chars: int) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 15].rstrip() + " [truncated]"


def _write_prompt_template(path: Path) -> None:
    lines = [
        "# LLM Prompt Template",
        "",
        "You are helping me prepare for a doctoral dissertation defense.",
        "Use only the provided local corpus excerpts as evidence.",
        "",
        "## Instructions",
        "",
        "- Identify likely examiner interests, questions, and critical angles.",
        "- Cite `chunk_id`, paper title, section, and source PDF for every concrete claim.",
        "- Separate evidence from interpretation.",
        "- Do not invent paper details that are not in the supplied corpus.",
        "- If evidence is thin, say what is missing.",
        "",
        "## Suggested Question",
        "",
        "Based on this examiner pack, what are the most likely defense questions "
        "this examiner could ask, and which corpus chunks support each question?",
        "",
        "## Paste Corpus Context Below",
        "",
        "```text",
        "<paste one `examiner_pack_*.md` file or selected chunks here>",
        "```",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
