from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from statistics import mean

from paper_pipeline.config import AppConfig
from paper_pipeline.manifest import list_pdfs, read_manifest
from paper_pipeline.metadata import paper_id
from paper_pipeline.utils import ensure_dir, estimate_tokens, read_json, read_jsonl


def generate_quality_report(config: AppConfig) -> Path:
    reports_dir = config.path("reports_dir")
    ensure_dir(reports_dir)
    report_path = reports_dir / "conversion_quality_report.md"
    raw_pdfs = list_pdfs(config.path("raw_pdf_dir"))
    json_dir = config.path("json_dir")
    json_files = sorted(json_dir.glob("*.json")) if json_dir.exists() else []
    expected_ids = {
        paper_id(row)
        for row in read_manifest(config.path("manifest_path"))
        if row.get("filename")
    }
    if expected_ids:
        json_files = [json_file for json_file in json_files if json_file.stem in expected_ids]
    chunks = read_jsonl(config.path("chunks_jsonl"))
    enriched_rows = _read_enriched(config.path("processed_dir") / "manifest_enriched.csv")
    processed_filenames: set[str] = set()
    chunks_by_paper = Counter(str(chunk.get("paper_id", "")) for chunk in chunks)

    successful = len(json_files)
    failed = max(0, len(raw_pdfs) - successful)
    fallback_count = 0
    warnings: list[str] = []
    suspicious: list[str] = []
    paper_summaries: list[str] = []
    grobid_available = "not configured"

    for json_file in json_files:
        paper = read_json(json_file)
        processed_filenames.add(str(paper.get("metadata", {}).get("filename", "")))
        conversion = paper.get("conversion", {})
        if conversion.get("fallback_used"):
            fallback_count += 1
        if conversion.get("grobid_available") is not None:
            grobid_available = str(conversion.get("grobid_available")).lower()
        for warning in conversion.get("warnings", []):
            filename = paper.get("metadata", {}).get("filename", json_file.name)
            warnings.append(f"{filename}: {warning}")
        sections = paper.get("sections", [])
        text_size = sum(len(str(section.get("text", ""))) for section in sections)
        if text_size < config.conversion.suspicious_text_length:
            suspicious.append(paper.get("metadata", {}).get("filename", json_file.name))
        paper_summaries.append(
            _paper_summary(
                paper,
                conversion,
                len(sections),
                chunks_by_paper[str(paper.get("paper_id", ""))],
            )
        )

    chunk_sizes = [estimate_tokens(chunk.get("text", "")) for chunk in chunks]
    tiny_chunks = [
        str(chunk.get("chunk_id", ""))
        for chunk in chunks
        if estimate_tokens(chunk.get("text", "")) < 30
    ]
    missing_metadata = [
        row
        for row in enriched_rows
        if "missing" in row.get("validation_warnings", "").lower()
    ]
    duplicates = [row for row in enriched_rows if row.get("duplicate_sha256") == "true"]
    failed_pdfs = [
        str(path.relative_to(config.path("raw_pdf_dir"))).replace("\\", "/")
        for path in raw_pdfs
        if str(path.relative_to(config.path("raw_pdf_dir"))).replace("\\", "/")
        not in processed_filenames
    ]

    lines = [
        "# Conversion Quality Report",
        "",
        "## Summary",
        "",
        f"- PDFs found: {len(raw_pdfs)}",
        f"- Successful conversions: {successful}",
        f"- Failed conversions: {failed}",
        f"- Fallbacks used: {fallback_count}",
        f"- Chunks generated: {len(chunks)}",
        f"- Average chunk size: {round(mean(chunk_sizes), 1) if chunk_sizes else 0}",
        f"- Tiny chunks (<30 tokens): {len(tiny_chunks)}",
        f"- GROBID availability: {grobid_available}",
        "",
    ]

    if not raw_pdfs:
        lines.extend(
            [
                "## Next Step",
                "",
                "No PDFs found yet. Add examiner publications to `data/raw_pdfs/`, then run:",
                "",
                "```powershell",
                "python -m paper_pipeline.cli scan-pdfs",
                "python -m paper_pipeline.cli validate-manifest",
                "python -m paper_pipeline.cli run-all",
                "```",
                "",
            ]
        )

    lines.extend(_section("Suspiciously Short Extractions", suspicious))
    lines.extend(_section("Failed Conversions", failed_pdfs))
    lines.extend(_section("Per-Paper Conversion", paper_summaries))
    lines.extend(_section("Tiny Chunks", tiny_chunks))
    lines.extend(
        _section("Missing Metadata Rows", [row.get("filename", "") for row in missing_metadata])
    )
    lines.extend(_section("Duplicate PDFs", [row.get("filename", "") for row in duplicates]))
    lines.extend(_section("Conversion Warnings", warnings))

    report_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return report_path


def _read_enriched(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _section(title: str, items: list[str]) -> list[str]:
    lines = [f"## {title}", ""]
    if not items:
        lines.append("- None")
    else:
        lines.extend(f"- {item}" for item in items if item)
    lines.append("")
    return lines


def _paper_summary(
    paper: dict[str, object],
    conversion: dict[str, object],
    section_count: int,
    chunk_count: int,
) -> str:
    metadata = paper.get("metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    filename = metadata.get("filename", paper.get("paper_id", "unknown paper"))
    actual_tool = conversion.get("actual_tool") or conversion.get("primary_tool") or "unknown"
    fallback = "fallback" if conversion.get("fallback_used") else "primary"
    return f"{filename}: {actual_tool} ({fallback}), {section_count} sections, {chunk_count} chunks"
