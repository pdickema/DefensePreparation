from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from paper_pipeline.converters.common import ConversionResult, ConversionUnavailable


def command() -> str | None:
    return shutil.which("marker_single") or shutil.which("marker")


def is_available() -> bool:
    return command() is not None


def convert_pdf(pdf_path: Path) -> ConversionResult:
    marker_cmd = command()
    if not marker_cmd:
        raise ConversionUnavailable("Marker is not installed or not on PATH.")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        completed = subprocess.run(
            [marker_cmd, str(pdf_path), "--output_dir", str(output_dir)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Marker conversion failed")
        markdown_files = list(output_dir.rglob("*.md"))
        if not markdown_files:
            raise RuntimeError("Marker did not produce a Markdown file")
        markdown = markdown_files[0].read_text(encoding="utf-8")

    return ConversionResult(markdown=markdown, tool="marker", fallback_used=True)
