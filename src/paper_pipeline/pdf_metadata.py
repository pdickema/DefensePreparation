from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractedPdfMetadata:
    title: str = ""
    year: str = ""
    doi: str = ""
    source: str = ""
    warnings: list[str] = field(default_factory=list)


DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2}|2100)\b")


def extract_pdf_metadata(pdf_path: Path, max_pages: int = 2) -> ExtractedPdfMetadata:
    try:
        import pypdfium2 as pdfium
    except Exception as exc:
        return ExtractedPdfMetadata(warnings=[f"pypdfium2 unavailable: {exc}"])

    try:
        document = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:
        return ExtractedPdfMetadata(warnings=[f"could not open PDF metadata: {exc}"])

    try:
        metadata = document.get_metadata_dict() or {}
        text = _first_pages_text(document, max_pages=max_pages)
    except Exception as exc:
        return ExtractedPdfMetadata(warnings=[f"could not extract PDF metadata/text: {exc}"])
    finally:
        document.close()

    return metadata_from_values(metadata, text)


def metadata_from_values(metadata: dict[str, str], text: str = "") -> ExtractedPdfMetadata:
    searchable = "\n".join(str(value or "") for value in metadata.values()) + "\n" + (text or "")
    title = _clean_title(metadata.get("Title", ""))
    doi = _extract_doi(searchable)
    year = _extract_year(metadata, text)
    source = _extract_source(metadata, text)
    return ExtractedPdfMetadata(title=title, year=year, doi=doi, source=source)


def _first_pages_text(document, max_pages: int) -> str:
    pages: list[str] = []
    for index in range(min(len(document), max_pages)):
        page = document[index]
        text_page = page.get_textpage()
        pages.append(text_page.get_text_range())
        text_page.close()
        page.close()
    return "\n".join(pages)


def _extract_doi(text: str) -> str:
    normalized = re.sub(r"[\u00ad\u200b]", "", text or "")
    normalized = re.sub(r"(?i)doi\s*:\s*", "doi:", normalized)
    match = DOI_RE.search(normalized)
    if not match:
        return ""
    return match.group(0).rstrip(".,;:)]}")


def _extract_year(metadata: dict[str, str], text: str) -> str:
    for field_name in ["Subject", "CreationDate", "ModDate", "Title"]:
        year = _first_year(str(metadata.get(field_name) or ""))
        if year:
            return year
    return _first_year((text or "")[:2500])


def _first_year(text: str) -> str:
    for match in YEAR_RE.finditer(text or ""):
        year = int(match.group(1))
        if 1900 <= year <= 2100:
            return str(year)
    return ""


def _extract_source(metadata: dict[str, str], text: str) -> str:
    subject = str(metadata.get("Subject") or "").strip()
    if subject:
        source = subject.split(",")[0].strip()
        if _is_useful_source(source):
            return source

    creator = str(metadata.get("Creator") or "").strip()
    if _is_useful_source(creator):
        return creator

    for line in (text or "").splitlines()[:20]:
        line = re.sub(r"\s+", " ", line).strip()
        if _is_useful_source(line) and not line.lower().startswith("contents lists"):
            return line
    return ""


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip()
    if not title or len(title) < 8:
        return ""
    lower = title.lower()
    bad_fragments = ["microsoft word", "untitled", ".pdf", "acrobat"]
    if any(fragment in lower for fragment in bad_fragments):
        return ""
    return title


def _is_useful_source(source: str) -> bool:
    if not source or len(source) < 4 or len(source) > 120:
        return False
    lower = source.lower()
    bad_fragments = ["doi:", "http://", "https://", "acrobat", "distiller"]
    return not any(fragment in lower for fragment in bad_fragments)
