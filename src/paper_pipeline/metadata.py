from __future__ import annotations

from pathlib import Path
from typing import Any

from paper_pipeline.utils import slugify


def parse_year(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        year = int(str(value).strip())
    except ValueError:
        return None
    if year < 1500 or year > 2200:
        return None
    return year


def paper_slug(row: dict[str, Any]) -> str:
    title = str(row.get("title") or "").strip()
    filename = Path(str(row.get("filename") or "paper")).stem
    return slugify(title or filename, fallback="paper")


def examiner_slug(row: dict[str, Any]) -> str:
    return slugify(str(row.get("examiner") or "unknown-examiner"), fallback="unknown-examiner")


def paper_id(row: dict[str, Any]) -> str:
    year = str(row.get("year") or "unknown-year").strip() or "unknown-year"
    return f"{examiner_slug(row)}_{year}_{paper_slug(row)}"


def build_metadata(row: dict[str, Any], sha256: str | None = None) -> dict[str, Any]:
    return {
        "filename": str(row.get("filename") or ""),
        "examiner": str(row.get("examiner") or ""),
        "title": str(row.get("title") or ""),
        "year": parse_year(row.get("year")),
        "doi": str(row.get("doi") or ""),
        "source": str(row.get("source") or ""),
        "notes": str(row.get("notes") or ""),
        "sha256": sha256 or str(row.get("sha256") or ""),
    }
