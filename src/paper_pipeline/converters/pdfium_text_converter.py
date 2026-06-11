from __future__ import annotations

from pathlib import Path

from paper_pipeline.converters.common import ConversionResult, ConversionUnavailable


def is_available() -> bool:
    try:
        import pypdfium2  # noqa: F401
    except Exception:
        return False
    return True


def convert_pdf(pdf_path: Path) -> ConversionResult:
    try:
        import pypdfium2 as pdfium
    except Exception as exc:
        raise ConversionUnavailable(f"pypdfium2 is not installed: {exc}") from exc

    try:
        document = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:
        raise RuntimeError(f"Could not open PDF with pypdfium2: {exc}") from exc

    pages: list[str] = []
    try:
        for index in range(len(document)):
            page = document[index]
            text_page = page.get_textpage()
            text = text_page.get_text_range().strip()
            if text:
                pages.append(f"<!-- page {index + 1} -->\n\n{text}")
            text_page.close()
            page.close()
    finally:
        document.close()

    markdown = "\n\n".join(pages).strip()
    if not markdown:
        raise RuntimeError("pypdfium2 returned no extractable text")

    return ConversionResult(
        markdown=markdown,
        tool="pypdfium2-text",
        fallback_used=True,
        warnings=["Docling failed; used local pypdfium2 text-layer fallback"],
    )
