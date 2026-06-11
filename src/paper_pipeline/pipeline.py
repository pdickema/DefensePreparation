from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from paper_pipeline import chunking
from paper_pipeline.cleaning import clean_markdown
from paper_pipeline.config import AppConfig
from paper_pipeline.converters import (
    docling_converter,
    grobid_converter,
    marker_converter,
    ocr_converter,
)
from paper_pipeline.converters.common import ConversionResult
from paper_pipeline.hashing import sha256_file
from paper_pipeline.manifest import (
    NO_PDFS_MESSAGE,
    OperationResult,
    list_pdfs,
    read_manifest,
    validate_manifest,
)
from paper_pipeline.metadata import build_metadata, paper_id
from paper_pipeline.quality import generate_quality_report
from paper_pipeline.sectioning import parse_markdown_sections
from paper_pipeline.utils import (
    ensure_dir,
    read_json,
    utc_now_iso,
    with_yaml_front_matter,
    write_json,
)

LOGGER = logging.getLogger(__name__)


def process_papers(config: AppConfig) -> OperationResult:
    validation = validate_manifest(config)
    raw_dir = config.path("raw_pdf_dir")
    rows = read_manifest(config.path("manifest_path"))
    pdfs = list_pdfs(raw_dir)
    result = OperationResult(messages=list(validation.messages), warnings=list(validation.warnings))

    if not pdfs:
        if NO_PDFS_MESSAGE not in result.messages:
            result.messages.append(NO_PDFS_MESSAGE)
        return result

    grobid_available = False
    if config.conversion.use_grobid:
        grobid_available = grobid_converter.is_available(config.conversion.grobid_url)
        if not grobid_available:
            warning = "GROBID is enabled but not reachable; continuing without TEI extraction."
            result.warnings.append(warning)
            LOGGER.warning(warning)

    for row in rows:
        filename = row.get("filename", "")
        pdf_path = raw_dir / filename if filename else raw_dir
        if not filename or not pdf_path.exists():
            continue

        warnings: list[str] = []
        sha256 = sha256_file(pdf_path)
        pid = paper_id(row)
        tei_written = False

        if config.conversion.use_grobid and grobid_available:
            tei_path = config.path("tei_dir") / f"{pid}.tei.xml"
            tei_written = grobid_converter.process_fulltext(
                pdf_path, tei_path, config.conversion.grobid_url
            )
            if not tei_written:
                warnings.append("GROBID request failed; TEI not written")

        conversion = _convert_with_fallbacks(config, pdf_path, warnings)
        if conversion is None:
            result.warnings.append(f"{filename}: no converter succeeded")
            continue

        cleaned_markdown = clean_markdown(conversion.markdown)
        if len(cleaned_markdown) < config.conversion.suspicious_text_length:
            warnings.append("suspiciously short extracted text")

        metadata = build_metadata(row, sha256=sha256)
        conversion_date = utc_now_iso()
        front_matter = {
            "examiner": metadata["examiner"],
            "title": metadata["title"],
            "year": metadata["year"],
            "doi": metadata["doi"],
            "source_pdf": metadata["filename"],
            "sha256": sha256,
            "conversion_tool": conversion.tool,
            "conversion_date": conversion_date,
        }
        markdown_out = with_yaml_front_matter(front_matter, cleaned_markdown)
        sections = parse_markdown_sections(markdown_out)
        paper_json = {
            "paper_id": pid,
            "metadata": metadata,
            "conversion": {
                "primary_tool": config.conversion.primary,
                "actual_tool": conversion.tool,
                "fallback_used": conversion.fallback_used,
                "grobid_available": grobid_available,
                "grobid_tei_written": tei_written,
                "warnings": warnings + conversion.warnings,
            },
            "sections": sections,
            "references": [],
            "tables": [],
            "figures": [],
        }

        markdown_path = config.path("markdown_dir") / f"{pid}.md"
        json_path = config.path("json_dir") / f"{pid}.json"
        ensure_dir(markdown_path.parent)
        markdown_path.write_text(markdown_out, encoding="utf-8")
        write_json(json_path, paper_json)
        result.messages.append(f"Processed {filename}")

    return result


def _convert_with_fallbacks(
    config: AppConfig, pdf_path: Path, warnings: list[str]
) -> ConversionResult | None:
    try:
        return docling_converter.convert_pdf(pdf_path)
    except Exception as exc:
        warnings.append(f"Docling failed or unavailable: {exc}")
        LOGGER.warning("Docling failed for %s: %s", pdf_path, exc)

    if config.conversion.fallback_marker:
        try:
            return marker_converter.convert_pdf(pdf_path)
        except Exception as exc:
            warnings.append(f"Marker fallback failed or unavailable: {exc}")

    if config.conversion.fallback_ocr:
        status = ocr_converter.tool_status()
        if not ocr_converter.is_available():
            warnings.append(f"OCR fallback unavailable; tool status: {status}")
        else:
            ocr_pdf = pdf_path.with_suffix(".ocr.pdf")
            if ocr_converter.ocr_pdf(pdf_path, ocr_pdf):
                try:
                    conversion = docling_converter.convert_pdf(ocr_pdf)
                    conversion.fallback_used = True
                    conversion.warnings.append("OCR fallback used before Docling conversion")
                    return conversion
                finally:
                    if ocr_pdf.exists():
                        ocr_pdf.unlink(missing_ok=True)

    return None


def chunk_processed_papers(config: AppConfig) -> OperationResult:
    json_dir = config.path("json_dir")
    json_files = sorted(json_dir.glob("*.json")) if json_dir.exists() else []
    if not json_files:
        return OperationResult(
            messages=[
                "No processed JSON papers found yet. Add PDFs, run process, then run chunk again."
            ]
        )

    chunks: list[dict[str, Any]] = []
    for json_file in json_files:
        paper = read_json(json_file)
        chunks.extend(
            chunking.chunk_paper(
                paper,
                target_tokens=config.chunking.target_tokens,
                overlap_tokens=config.chunking.overlap_tokens,
            )
        )

    count = chunking.write_chunks(config.path("chunks_jsonl"), chunks)
    return OperationResult(messages=[f"Wrote {count} chunks to {config.path('chunks_jsonl')}"])


def run_all(config: AppConfig) -> OperationResult:
    from paper_pipeline.defense_prep import generate_defense_prep
    from paper_pipeline.manifest import initialize_data, scan_pdfs

    result = OperationResult()
    for step in [
        initialize_data(config),
        scan_pdfs(config),
        validate_manifest(config),
        process_papers(config),
        chunk_processed_papers(config),
    ]:
        result.messages.extend(step.messages)
        result.warnings.extend(step.warnings)

    report_path = generate_quality_report(config)
    result.messages.append(f"Wrote quality report: {report_path}")

    defense_paths = generate_defense_prep(config)
    result.messages.extend(f"Wrote defense-prep output: {path}" for path in defense_paths)
    return result
