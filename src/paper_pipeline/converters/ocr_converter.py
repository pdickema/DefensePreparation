from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def tool_status() -> dict[str, bool]:
    return {
        "ocrmypdf": shutil.which("ocrmypdf") is not None,
        "tesseract": shutil.which("tesseract") is not None,
        "ghostscript": shutil.which("gs") is not None or shutil.which("gswin64c") is not None,
    }


def is_available() -> bool:
    status = tool_status()
    return status["ocrmypdf"] and status["tesseract"] and status["ghostscript"]


def ocr_pdf(input_pdf: Path, output_pdf: Path) -> bool:
    if not is_available():
        return False
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["ocrmypdf", "--skip-text", str(input_pdf), str(output_pdf)],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and output_pdf.exists()
