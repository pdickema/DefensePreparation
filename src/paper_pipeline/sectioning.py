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
            if (
                stripped.lower() in STANDARD_SECTION_NAMES
                and len(stripped) <= 40
                and current_lines
                and not current_lines[-1].strip()
            ):
                flush()
                current_heading = stripped
                current_level = 1
                current_lines = []
            else:
                current_lines.append(line)

    flush()
    return [section.to_dict() for section in sections if str(section.text).strip()]
