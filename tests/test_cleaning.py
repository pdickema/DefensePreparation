from __future__ import annotations

from paper_pipeline.cleaning import clean_markdown, clean_text


def test_cleaning_fixes_hyphenation_and_page_numbers():
    text = "A manage-\nment accounting paper\n\n12\n\nwith   extra   spaces"

    cleaned = clean_text(text)

    assert "management accounting" in cleaned
    assert "\n12\n" not in cleaned
    assert "extra spaces" in cleaned


def test_clean_markdown_repairs_and_wraps_split_urls():
    markdown = "Report URL: http://\nwww.example.org/path."

    cleaned = clean_markdown(markdown)

    assert cleaned == "Report URL: <http://www.example.org/path>."
