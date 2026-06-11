from __future__ import annotations

from paper_pipeline.sectioning import parse_markdown_sections


def test_markdown_section_detection():
    markdown = "# Abstract\n\nText.\n\n# Methods\n\nMethod text."

    sections = parse_markdown_sections(markdown)

    assert [section["heading"] for section in sections] == ["Abstract", "Methods"]
