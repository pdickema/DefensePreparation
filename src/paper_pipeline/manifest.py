from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from paper_pipeline.config import AppConfig
from paper_pipeline.hashing import sha256_file
from paper_pipeline.utils import ensure_dir, relative_posix

MANIFEST_COLUMNS = ["filename", "examiner", "title", "year", "doi", "source", "notes"]
ENRICHED_COLUMNS = MANIFEST_COLUMNS + [
    "exists",
    "sha256",
    "duplicate_sha256",
    "validation_warnings",
]
NO_PDFS_MESSAGE = (
    "No PDFs found yet. Add your examiner publications to data/raw_pdfs/ "
    "and run scan-pdfs again."
)

EXAMPLE_ROWS = [
    {
        "filename": "example_wouters_2015.pdf",
        "examiner": "Marc Wouters",
        "title": "Example Paper Title",
        "year": "2015",
        "doi": "10.xxxx/example",
        "source": "Manual download",
        "notes": "Replace this row later",
    },
    {
        "filename": "example_fichtner_2020.pdf",
        "examiner": "Wolf Fichtner",
        "title": "Another Example Paper",
        "year": "2020",
        "doi": "",
        "source": "Manual download",
        "notes": "DOI missing",
    },
]


@dataclass
class OperationResult:
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.warnings


def data_directories(config: AppConfig) -> list[Path]:
    return [
        config.path("data_dir"),
        config.path("raw_pdf_dir"),
        config.path("processed_dir"),
        config.path("markdown_dir"),
        config.path("json_dir"),
        config.path("tei_dir"),
        config.path("chunks_dir"),
        config.path("index_dir"),
        config.path("reports_dir"),
    ]


def initialize_data(config: AppConfig, force_manifest: bool = False) -> OperationResult:
    result = OperationResult()
    for directory in data_directories(config):
        ensure_dir(directory)
        result.messages.append(f"Ensured {directory}")

    manifest_path = config.path("manifest_path")
    if manifest_path.exists() and not force_manifest:
        result.messages.append(f"Kept existing manifest: {manifest_path}")
    else:
        write_manifest(manifest_path, EXAMPLE_ROWS)
        result.messages.append(f"Wrote example manifest: {manifest_path}")

    result.messages.append(f"Add PDFs later to: {config.path('raw_pdf_dir')}")
    return result


def read_manifest(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({column: str(row.get(column) or "").strip() for column in MANIFEST_COLUMNS})
    return rows


def write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in MANIFEST_COLUMNS})


def list_pdfs(raw_pdf_dir: Path) -> list[Path]:
    if not raw_pdf_dir.exists():
        return []
    return sorted(path for path in raw_pdf_dir.rglob("*.pdf") if path.is_file())


def scan_pdfs(config: AppConfig) -> OperationResult:
    initialize_data(config, force_manifest=False)
    raw_dir = config.path("raw_pdf_dir")
    manifest_path = config.path("manifest_path")
    pdfs = list_pdfs(raw_dir)
    rows = read_manifest(manifest_path)
    existing = {row["filename"]: row for row in rows if row.get("filename")}
    messages: list[str] = []
    warnings: list[str] = []

    if not pdfs:
        messages.append(NO_PDFS_MESSAGE)
        return OperationResult(messages=messages, warnings=warnings, rows=rows)

    discovered_names = {relative_posix(path, raw_dir): path for path in pdfs}
    for filename in sorted(discovered_names):
        if filename not in existing:
            rows.append(
                {
                    "filename": filename,
                    "examiner": "",
                    "title": Path(filename).stem.replace("_", " ").replace("-", " "),
                    "year": "",
                    "doi": "",
                    "source": "",
                    "notes": "Draft row from scan-pdfs",
                }
            )
            messages.append(f"Added draft manifest row for {filename}")

    for row in rows:
        filename = row.get("filename", "")
        if filename and filename not in discovered_names:
            warnings.append(f"Manifest PDF not found in raw folder: {filename}")

    write_manifest(manifest_path, rows)
    messages.append(f"Manifest updated: {manifest_path}")
    return OperationResult(messages=messages, warnings=warnings, rows=rows)


def validate_manifest(config: AppConfig) -> OperationResult:
    initialize_data(config, force_manifest=False)
    raw_dir = config.path("raw_pdf_dir")
    rows = read_manifest(config.path("manifest_path"))
    pdfs = list_pdfs(raw_dir)
    messages: list[str] = []
    warnings: list[str] = []

    if not pdfs:
        messages.append(NO_PDFS_MESSAGE)
        enriched_path = config.path("processed_dir") / "manifest_enriched.csv"
        ensure_dir(enriched_path.parent)
        with enriched_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ENRICHED_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        **row,
                        "exists": "false",
                        "sha256": "",
                        "duplicate_sha256": "false",
                        "validation_warnings": "raw_pdf_dir empty; add PDFs before validation",
                    }
                )
        messages.append(f"Saved enriched manifest: {enriched_path}")
        return OperationResult(messages=messages, warnings=warnings, rows=rows)

    sha_counts: dict[str, int] = {}
    enriched: list[dict[str, Any]] = []
    for row in rows:
        row_warnings: list[str] = []
        filename = row.get("filename", "")
        pdf_path = raw_dir / filename if filename else raw_dir
        exists = bool(filename and pdf_path.exists())
        sha256 = ""

        if not filename:
            row_warnings.append("filename missing")
        if not exists:
            row_warnings.append("PDF file missing")
        else:
            sha256 = sha256_file(pdf_path)
            sha_counts[sha256] = sha_counts.get(sha256, 0) + 1

        for field_name in ["examiner", "title", "year", "source"]:
            if not str(row.get(field_name) or "").strip():
                row_warnings.append(f"{field_name} missing")
        if not str(row.get("doi") or "").strip():
            row_warnings.append("doi missing")

        enriched.append(
            {
                **row,
                "exists": str(exists).lower(),
                "sha256": sha256,
                "duplicate_sha256": "false",
                "validation_warnings": "; ".join(row_warnings),
            }
        )
        warnings.extend(f"{filename or '<blank>'}: {warning}" for warning in row_warnings)

    for row in enriched:
        sha256 = row.get("sha256", "")
        if sha256 and sha_counts.get(sha256, 0) > 1:
            row["duplicate_sha256"] = "true"
            warning = f"{row.get('filename')}: duplicate PDF hash"
            row["validation_warnings"] = "; ".join(
                item for item in [row.get("validation_warnings", ""), "duplicate PDF hash"] if item
            )
            warnings.append(warning)

    enriched_path = config.path("processed_dir") / "manifest_enriched.csv"
    ensure_dir(enriched_path.parent)
    with enriched_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ENRICHED_COLUMNS)
        writer.writeheader()
        writer.writerows(enriched)

    messages.append(f"Saved enriched manifest: {enriched_path}")
    return OperationResult(messages=messages, warnings=warnings, rows=enriched)
