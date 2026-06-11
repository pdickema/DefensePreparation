from __future__ import annotations

from paper_pipeline.sectioning import parse_markdown_sections


def test_markdown_section_detection():
    markdown = "# Abstract\n\nText.\n\n# Methods\n\nMethod text."

    sections = parse_markdown_sections(markdown)

    assert [section["heading"] for section in sections] == ["Abstract", "Methods"]


def test_numbered_heading_detection():
    markdown = "Title page\n\n1. Introduction\n\nIntro text.\n\n2. Methods\n\nMethod text."

    sections = parse_markdown_sections(markdown)

    assert [section["heading"] for section in sections] == ["Body", "1. Introduction", "2. Methods"]


def test_numbered_heading_detection_with_spaced_dot():
    markdown = "Abstract text.\n1 . Introduction\nIntro text.\nReferences\nReference text."

    sections = parse_markdown_sections(markdown)

    assert [section["heading"] for section in sections] == [
        "Body",
        "1 . Introduction",
        "References",
    ]


def test_footnotes_and_long_numbers_are_not_section_headings():
    markdown = (
        "Opening text.\n\n"
        "1 The CHAP model and input files can be downloaded from this website: http:\n"
        "More body text.\n\n"
        "1. Introduction\n"
        "Intro text.\n"
        "17791669. All other data used in this study cannot be shared publicly\n"
        "More introduction text.\n"
    )

    sections = parse_markdown_sections(markdown)

    assert [section["heading"] for section in sections] == ["Body", "1. Introduction"]
    assert "1 The CHAP model" in sections[0]["text"]
    assert "17791669. All other data" in sections[1]["text"]
