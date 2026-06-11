from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from paper_pipeline.config import AppConfig
from paper_pipeline.manifest import (
    NO_PDFS_MESSAGE,
    OperationResult,
    is_suspicious_source,
    list_pdfs,
    year_from_filename,
)
from paper_pipeline.pdf_metadata import ExtractedPdfMetadata, extract_pdf_metadata
from paper_pipeline.utils import ensure_dir, relative_posix


@dataclass
class PdfPreflightRow:
    filename: str
    pages: int = 0
    file_mb: float = 0.0
    text_chars: int = 0
    chars_per_page: float = 0.0
    likely_scanned: bool = False
    huge_pdf: bool = False
    filename_year: str = ""
    extracted_year: str = ""
    extracted_title: str = ""
    extracted_doi: str = ""
    extracted_source: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def preflight_pdfs(config: AppConfig) -> OperationResult:
    raw_dir = config.path("raw_pdf_dir")
    reports_dir = ensure_dir(config.path("reports_dir"))
    report_path = reports_dir / "pdf_preflight_report.md"
    pdfs = list_pdfs(raw_dir)

    if not pdfs:
        _write_report(report_path, [])
        return OperationResult(
            messages=[
                NO_PDFS_MESSAGE,
                f"Wrote PDF preflight report: {report_path}",
            ]
        )

    rows = [inspect_pdf(path, raw_dir) for path in pdfs]
    _write_report(report_path, rows)
    warnings = [
        f"{row.filename}: {warning}"
        for row in rows
        for warning in row.warnings
    ]
    return OperationResult(
        messages=[
            f"Preflight checked {len(rows)} PDFs.",
            f"Wrote PDF preflight report: {report_path}",
        ],
        warnings=warnings,
        rows=[row.to_dict() for row in rows],
    )


def inspect_pdf(pdf_path: Path, raw_dir: Path) -> PdfPreflightRow:
    filename = relative_posix(pdf_path, raw_dir)
    extracted = extract_pdf_metadata(pdf_path)
    row = PdfPreflightRow(
        filename=filename,
        file_mb=round(pdf_path.stat().st_size / (1024 * 1024), 2),
        huge_pdf=pdf_path.stat().st_size >= 25 * 1024 * 1024,
        filename_year=year_from_filename(filename),
        extracted_year=extracted.year,
        extracted_title=extracted.title,
        extracted_doi=extracted.doi,
        extracted_source=extracted.source,
        warnings=list(extracted.warnings),
    )

    try:
        import pypdfium2 as pdfium
    except Exception as exc:
        row.warnings.append(f"pypdfium2 unavailable: {exc}")
        return row

    try:
        document = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:
        row.warnings.append(f"could not open PDF text layer: {exc}")
        return row

    try:
        row.pages = len(document)
        for index in range(row.pages):
            page = document[index]
            text_page = page.get_textpage()
            row.text_chars += len(text_page.get_text_range().strip())
            text_page.close()
            page.close()
    except Exception as exc:
        row.warnings.append(f"could not inspect full text layer: {exc}")
    finally:
        document.close()

    row.chars_per_page = round(row.text_chars / row.pages, 1) if row.pages else 0.0
    row.likely_scanned = bool(row.pages and row.chars_per_page < 200)
    row.warnings.extend(_quality_warnings(row, extracted))
    return row


def _quality_warnings(row: PdfPreflightRow, extracted: ExtractedPdfMetadata) -> list[str]:
    warnings: list[str] = []
    if row.filename_year and extracted.year and row.filename_year != extracted.year:
        warnings.append(
            f"filename year {row.filename_year} differs from extracted PDF year {extracted.year}"
        )
    if row.likely_scanned:
        warnings.append("very little text layer detected; PDF may be scanned")
    if row.huge_pdf:
        warnings.append(f"large PDF file ({row.file_mb} MB)")
    if not row.extracted_title:
        warnings.append("title not found in PDF metadata")
    if is_suspicious_source(row.extracted_source):
        warnings.append(f"source looks suspicious: {row.extracted_source}")
    return list(dict.fromkeys(warnings))


def _write_report(path: Path, rows: list[PdfPreflightRow]) -> None:
    lines = [
        "# PDF Preflight Report",
        "",
        "This report is generated locally before conversion.",
        "",
        "## Summary",
        "",
        f"- PDFs found: {len(rows)}",
        f"- Likely scanned PDFs: {sum(1 for row in rows if row.likely_scanned)}",
        f"- Large PDFs (>25 MB): {sum(1 for row in rows if row.huge_pdf)}",
        f"- PDFs with warnings: {sum(1 for row in rows if row.warnings)}",
        "",
    ]
    if not rows:
        lines.extend(
            [
                "No PDFs found yet. Add examiner publications to `data/raw_pdfs/`.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## PDFs",
                "",
                "| PDF | Pages | Text chars | Chars/page | Year | DOI | Warnings |",
                "| --- | ---: | ---: | ---: | --- | --- | --- |",
            ]
        )
        for row in rows:
            year = row.filename_year or row.extracted_year
            warnings = "; ".join(row.warnings) if row.warnings else ""
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(row.filename),
                        str(row.pages),
                        str(row.text_chars),
                        str(row.chars_per_page),
                        _cell(year),
                        _cell(row.extracted_doi),
                        _cell(warnings),
                    ]
                )
                + " |"
            )
        lines.append("")

    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")
