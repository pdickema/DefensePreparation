from __future__ import annotations

from paper_pipeline.config import AppConfig, PathsConfig
from paper_pipeline.manifest import initialize_data, write_manifest
from paper_pipeline.quality import generate_quality_report
from paper_pipeline.utils import write_json, write_jsonl


def test_quality_report_includes_per_paper_converter_and_tiny_chunks(tmp_path):
    config = AppConfig(project_root=tmp_path, paths=PathsConfig())
    initialize_data(config)
    pdf_path = config.path("raw_pdf_dir") / "Wolf Fichtner" / "paper.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-1.4 mock")
    write_manifest(
        config.path("manifest_path"),
        [
            {
                "filename": "Wolf Fichtner/paper.pdf",
                "examiner": "Wolf Fichtner",
                "title": "Paper",
                "year": "2026",
                "doi": "",
                "source": "Manual",
                "notes": "",
            }
        ],
    )
    paper = {
        "paper_id": "wolf-fichtner_2026_paper",
        "metadata": {
            "filename": "Wolf Fichtner/paper.pdf",
            "examiner": "Wolf Fichtner",
            "title": "Paper",
            "year": "2026",
        },
        "conversion": {
            "primary_tool": "docling",
            "actual_tool": "pypdfium2-text",
            "fallback_used": True,
            "grobid_available": False,
            "warnings": [],
        },
        "sections": [{"heading": "Abstract", "text": "Short section."}],
    }
    write_json(config.path("json_dir") / "wolf-fichtner_2026_paper.json", paper)
    write_jsonl(
        config.path("chunks_jsonl"),
        [
            {
                "chunk_id": "wolf-fichtner_paper_0001",
                "paper_id": "wolf-fichtner_2026_paper",
                "text": "tiny",
            }
        ],
    )

    report = generate_quality_report(config).read_text(encoding="utf-8")

    assert "Tiny chunks (<30 tokens): 1" in report
    assert "Wolf Fichtner/paper.pdf: pypdfium2-text (fallback), 1 sections, 1 chunks" in report
