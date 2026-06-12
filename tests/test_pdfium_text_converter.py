from __future__ import annotations

from paper_pipeline.converters.pdfium_text_converter import _markdown_safe_text


def test_markdown_safe_text_escapes_accidental_headings_and_wraps_urls():
    text = "# Springer Science\nSee https://example.org/paper."

    cleaned = _markdown_safe_text(text)

    assert cleaned == "\\# Springer Science\nSee <https://example.org/paper>."
