from __future__ import annotations

import re
from dataclasses import asdict, dataclass

STANDARD_SECTION_NAMES = {
    "abstract",
    "introduction",
    "literature review",
    "theory",
    "method",
    "methods",
    "results",
    "findings",
    "discussion",
    "conclusion",
    "references",
}
NUMBERED_HEADING_RE = re.compile(
    r"^(?:[1-9]|[1-9]\d)\s*\.\s*(?:\d+\s*\.\s*)*[A-Z][A-Za-z0-9,;:()/%&\- ]{2,100}$"
)


@dataclass
class Section:
    section_id: str
    heading: str
    level: int
    page_start: int | None
    page_end: int | None
    text: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def strip_front_matter(markdown: str) -> str:
    if markdown.startswith("---\n"):
        end = markdown.find("\n---\n", 4)
        if end != -1:
            return markdown[end + 5 :].lstrip()
    return markdown


def parse_markdown_sections(markdown: str) -> list[dict[str, object]]:
    markdown = strip_front_matter(markdown)
    heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    sections: list[Section] = []
    current_heading = "Body"
    current_level = 1
    current_lines: list[str] = []

    def flush() -> None:
        text = "\n".join(current_lines).strip()
        if text or not sections:
            index = len(sections) + 1
            sections.append(
                Section(
                    section_id=f"sec_{index:04d}",
                    heading=current_heading,
                    level=current_level,
                    page_start=None,
                    page_end=None,
                    text=text,
                )
            )

    for line in markdown.splitlines():
        match = heading_re.match(line)
        if match:
            flush()
            current_heading = match.group(2).strip()
            current_level = len(match.group(1))
            current_lines = []
        else:
            stripped = line.strip()
            if _is_plain_heading(stripped, current_lines):
                flush()
                current_heading = stripped
                current_level = _plain_heading_level(stripped)
                current_lines = []
            else:
                current_lines.append(line)

    flush()
    return [section.to_dict() for section in sections if str(section.text).strip()]


def _is_plain_heading(stripped: str, current_lines: list[str]) -> bool:
    if not stripped:
        return False
    normalized = stripped.lower().strip(".")
    if normalized in STANDARD_SECTION_NAMES and len(stripped) <= 60:
        return True
    if NUMBERED_HEADING_RE.match(stripped):
        return True
    if not current_lines or current_lines[-1].strip():
        return False
    return normalized in {"acknowledgements", "acknowledgments", "appendix"}


def _plain_heading_level(stripped: str) -> int:
    match = re.match(r"^((?:\d+\s*\.\s*)+)", stripped)
    if not match:
        return 1
    return min(6, max(1, match.group(1).count(".")))
