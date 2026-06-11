from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from paper_pipeline.config import AppConfig
from paper_pipeline.utils import ensure_dir, read_jsonl

METHOD_TERMS = [
    "case study",
    "survey",
    "simulation",
    "experiment",
    "field study",
    "archival",
    "design science",
    "interview",
    "workshop",
    "literature review",
]

THEORY_TERMS = [
    "contingency theory",
    "institutional theory",
    "agency theory",
    "stakeholder theory",
    "legitimacy theory",
    "resource-based view",
    "transaction cost theory",
]

STOPWORDS = {
    "about",
    "after",
    "also",
    "among",
    "because",
    "between",
    "could",
    "from",
    "have",
    "into",
    "more",
    "other",
    "paper",
    "papers",
    "research",
    "such",
    "than",
    "that",
    "their",
    "there",
    "these",
    "this",
    "with",
    "were",
    "which",
    "will",
}


def generate_defense_prep(config: AppConfig) -> list[Path]:
    reports_dir = config.path("reports_dir")
    ensure_dir(reports_dir)
    chunks = read_jsonl(config.path("chunks_jsonl"))
    paths = [
        reports_dir / "examiner_overview.md",
        reports_dir / "theme_index.md",
        reports_dir / "method_index.md",
        reports_dir / "theory_index.md",
    ]

    if not chunks:
        for path in paths:
            path.write_text(
                "# Not Enough Corpus Data Yet\n\n"
                "No chunks were found. Add PDFs, run the processing pipeline, then run "
                "`python -m paper_pipeline.cli defense-prep` again.\n",
                encoding="utf-8",
            )
        return paths

    _write_examiner_overview(paths[0], chunks)
    _write_term_index(paths[1], chunks, title="Theme Index", mode="frequent")
    _write_term_index(paths[2], chunks, title="Method Index", terms=METHOD_TERMS)
    _write_term_index(paths[3], chunks, title="Theory Index", terms=THEORY_TERMS)
    return paths


def _write_examiner_overview(path: Path, chunks: list[dict[str, object]]) -> None:
    papers: dict[tuple[str, str, object, str], int] = defaultdict(int)
    for chunk in chunks:
        key = (
            str(chunk.get("examiner") or "Unknown examiner"),
            str(chunk.get("title") or "Untitled"),
            chunk.get("year") or "",
            str(chunk.get("doi") or ""),
        )
        papers[key] += 1

    lines = ["# Examiner Overview", ""]
    by_examiner: dict[str, list[tuple[str, object, str, int]]] = defaultdict(list)
    for (examiner, title, year, doi), count in papers.items():
        by_examiner[examiner].append((title, year, doi, count))

    for examiner in sorted(by_examiner):
        lines.extend([f"## {examiner}", ""])
        for title, year, doi, count in sorted(by_examiner[examiner]):
            doi_text = f", DOI: {doi}" if doi else ""
            lines.append(f"- {year}: {title}{doi_text} ({count} chunks)")
        lines.append("")

    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _write_term_index(
    path: Path,
    chunks: list[dict[str, object]],
    title: str,
    mode: str = "terms",
    terms: Iterable[str] | None = None,
) -> None:
    lines = [f"# {title}", ""]
    by_examiner: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        by_examiner[str(chunk.get("examiner") or "Unknown examiner")].append(
            str(chunk.get("text") or "")
        )

    for examiner in sorted(by_examiner):
        text = "\n".join(by_examiner[examiner]).lower()
        lines.extend([f"## {examiner}", ""])
        if mode == "frequent":
            words = [
                word
                for word in re.findall(r"[a-z][a-z\-]{3,}", text)
                if word not in STOPWORDS
            ]
            for word, count in Counter(words).most_common(25):
                lines.append(f"- {word}: {count}")
        else:
            found = [(term, text.count(term.lower())) for term in terms or []]
            found = [(term, count) for term, count in found if count]
            if not found:
                lines.append("- No configured terms found.")
            else:
                for term, count in found:
                    lines.append(f"- {term}: {count}")
        lines.append("")

    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
