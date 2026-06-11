from __future__ import annotations

from pathlib import Path

import requests


def is_available(grobid_url: str, timeout: float = 3.0) -> bool:
    url = grobid_url.rstrip("/") + "/api/isalive"
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException:
        return False
    return response.ok and "true" in response.text.lower()


def process_fulltext(
    pdf_path: Path,
    output_path: Path,
    grobid_url: str,
    timeout: float = 60.0,
) -> bool:
    url = grobid_url.rstrip("/") + "/api/processFulltextDocument"
    try:
        with pdf_path.open("rb") as handle:
            response = requests.post(
                url,
                files={"input": (pdf_path.name, handle, "application/pdf")},
                timeout=timeout,
            )
    except requests.RequestException:
        return False

    if not response.ok or not response.text.strip():
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(response.text, encoding="utf-8")
    return True
