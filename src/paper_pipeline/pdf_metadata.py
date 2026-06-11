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
SOURCE_JOURNAL_WORDS = {
    "buildings",
    "computers",
    "ecology",
    "energy",
    "journal",
    "management",
    "operations",
    "policy",
    "reports",
    "research",
    "review",
    "reviews",
    "science",
    "sustainability",
    "systems",
}
TEXT_SOURCE_WORDS = {
    "buildings",
    "ecology",
    "journal",
    "management",
    "operations",
    "policy",
    "reports",
    "reviews",
    "science",
    "sustainability",
}


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
    title = _clean_title(metadata.get("Title", "")) or _extract_title_from_text(text)
    doi = _extract_doi(searchable)
    year = _extract_year(metadata, text)
    source = _extract_source(metadata, text, title)
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


def _extract_source(metadata: dict[str, str], text: str, title: str = "") -> str:
    subject = str(metadata.get("Subject") or "").strip()
    if subject:
        source = subject.split(",")[0].strip()
        if _is_useful_source(source, title=title):
            return source

    creator = str(metadata.get("Creator") or "").strip()
    if _is_useful_source(creator, title=title):
        return creator

    for raw_line in (text or "").splitlines()[:100]:
        line = _source_candidate_from_line(raw_line)
        if (
            _is_useful_source(line, title=title)
            and _has_journal_word(line)
            and not line.lower().startswith("contents lists")
        ):
            return line
    return ""


def _extract_title_from_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    title_lines: list[str] = []
    for line in lines[:35]:
        if _skip_title_candidate(line):
            continue
        if title_lines and _looks_like_title_stop(line):
            break
        title_lines.append(line)
        if len(title_lines) >= 3 or len(" ".join(title_lines)) > 160:
            break

    while title_lines and _looks_like_title_stop(title_lines[-1]):
        title_lines.pop()
    return _clean_title(" ".join(title_lines))


def _skip_title_candidate(line: str) -> bool:
    lower = line.lower()
    skip_fragments = [
        "contents lists available",
        "journal homepage",
        "original paper",
        "research paper",
        "article info",
    ]
    return any(fragment in lower for fragment in skip_fragments)


def _looks_like_title_stop(line: str) -> bool:
    lower = line.lower().strip()
    if lower in {"article info", "article history:", "abstract", "keywords:"}:
        return True
    stop_fragments = [
        "accepted ",
        "available online",
        "chair of ",
        "chair for ",
        "doi ",
        "e-mail",
        "institute ",
        "published online",
        "received",
        "university",
    ]
    if any(fragment in lower for fragment in stop_fragments):
        return True
    if _is_standalone_date(line):
        return True
    if re.match(r"^[A-Z]\.\s+[A-Z][A-Za-z-]+", line):
        return True
    if " & " in line and not any(word in lower for word in SOURCE_JOURNAL_WORDS):
        return True
    return bool(re.search(r"\s[n∗*]\s*$", line))


def _clean_title(title: str) -> str:
    title = _repair_title_punctuation(title)
    title = re.sub(r"\s+", " ", title or "").strip()
    if not title or len(title) < 8:
        return ""
    lower = title.lower()
    bad_fragments = ["microsoft word", "untitled", ".pdf", "acrobat", "original paper"]
    if any(fragment in lower for fragment in bad_fragments):
        return ""
    return title


def _repair_title_punctuation(title: str) -> str:
    title = title or ""
    title = re.sub(r"(?<=\w)_\s+(?=[A-Z])", ": ", title)
    title = re.sub(r"(?<=\w)_+(?=\w)", " ", title)
    return title


def _is_useful_source(source: str, title: str = "") -> bool:
    if not source or len(source) < 4 or len(source) > 120:
        return False
    if source.lstrip().startswith(","):
        return False
    if source[0].islower():
        return False
    lower = source.lower()
    if _skip_title_candidate(source) or _looks_like_title_stop(source):
        return False
    if lower in {"abstract", "keywords", "keywords:", "article history:"}:
        return False
    if lower.startswith("keywords"):
        return False
    if source.startswith("#") or "all rights reserved" in lower or "copyright" in lower:
        return False
    has_journal_word = any(word in lower for word in SOURCE_JOURNAL_WORDS)
    if "fichtner" in lower and not has_journal_word:
        return False
    if not has_journal_word and re.fullmatch(r"[A-Z][A-Za-z-]+(?:\s+[A-Z][A-Za-z-]+){1,3}", source):
        return False
    if " & " in source and not any(word in lower for word in SOURCE_JOURNAL_WORDS):
        return False
    bad_fragments = [
        "3b2",
        "doi:",
        "http://",
        "https://",
        "acrobat",
        "distiller",
        "microsoft word",
        "publishing system",
        "research paper",
        "total publishing",
        "unicode",
    ]
    if any(fragment in lower for fragment in bad_fragments):
        return False
    title_lower = title.lower().strip()
    if title_lower and (
        lower == title_lower
        or lower in title_lower
        or title_lower in lower
    ):
        return False
    return True


def _source_candidate_from_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line or "").strip()
    consum_policy = re.search(r"(J\s+Consum\s+Policy\s+\(\d{4}\).*)", line)
    if consum_policy:
        return consum_policy.group(1)
    return line


def _has_journal_word(source: str) -> bool:
    lower = source.lower()
    return any(word in lower for word in TEXT_SOURCE_WORDS)


def _is_standalone_date(value: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}\s+[A-Z][a-z]+\s+\d{4}", value.strip()))
