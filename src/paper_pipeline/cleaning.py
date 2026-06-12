from __future__ import annotations

import re
import unicodedata
from collections import Counter


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def fix_hyphenation(text: str) -> str:
    return re.sub(r"(\w)-\n(\w)", r"\1\2", text)


def fix_broken_urls(text: str) -> str:
    return re.sub(r"\b(https?://)\s*\n\s*", r"\1", text)


def remove_repeated_headers_footers(text: str) -> str:
    pages = text.split("\f")
    if len(pages) < 3:
        return text

    candidates: list[str] = []
    page_lines: list[list[str]] = []
    for page in pages:
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        page_lines.append(lines)
        if lines:
            candidates.append(lines[0])
            candidates.append(lines[-1])

    repeated = {
        line
        for line, count in Counter(candidates).items()
        if count >= 3 and len(line) > 5 and not re.fullmatch(r"\d+", line)
    }
    if not repeated:
        return text

    cleaned_pages: list[str] = []
    for lines in page_lines:
        kept = [line for line in lines if line not in repeated]
        cleaned_pages.append("\n".join(kept))
    return "\n\n".join(cleaned_pages)


def remove_isolated_page_numbers(text: str) -> str:
    return re.sub(r"(?m)^\s*\d{1,4}\s*$", "", text)


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def clean_text(text: str) -> str:
    text = normalize_unicode(text)
    text = fix_hyphenation(text)
    text = fix_broken_urls(text)
    text = remove_repeated_headers_footers(text)
    text = remove_isolated_page_numbers(text)
    return normalize_whitespace(text)


def clean_markdown(markdown: str) -> str:
    return wrap_bare_urls(clean_text(markdown))


def wrap_bare_urls(text: str) -> str:
    return re.sub(r"(?<![<(])\bhttps?://[^\s<>)]+", _wrap_url_match, text)


def _wrap_url_match(match: re.Match[str]) -> str:
    url = match.group(0)
    trailing = ""
    while url and url[-1] in ".,;:]":
        trailing = url[-1] + trailing
        url = url[:-1]
    return f"<{url}>{trailing}"
