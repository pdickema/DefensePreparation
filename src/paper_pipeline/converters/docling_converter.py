from __future__ import annotations

import importlib.util
from pathlib import Path

from paper_pipeline.converters.common import ConversionResult, ConversionUnavailable


def is_available() -> bool:
    return importlib.util.find_spec("docling") is not None


def convert_pdf(pdf_path: Path) -> ConversionResult:
    if not is_available():
        raise ConversionUnavailable(
            "Docling is not installed. Install it with: python -m pip install -e \".[docling]\""
        )

    try:
        from docling.document_converter import DocumentConverter
    except Exception as exc:  # pragma: no cover - depends on optional package
        raise ConversionUnavailable(f"Docling could not be imported: {exc}") from exc

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    document = result.document
    if hasattr(document, "export_to_markdown"):
        markdown = document.export_to_markdown()
    else:  # pragma: no cover - defensive for API changes
        markdown = str(document)

    if not markdown.strip():
        raise RuntimeError("Docling returned empty Markdown")

    return ConversionResult(markdown=markdown, tool="docling")
