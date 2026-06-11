from __future__ import annotations

from paper_pipeline.config import AppConfig, PathsConfig
from paper_pipeline.manifest import initialize_data
from paper_pipeline.preflight import PdfPreflightRow, preflight_pdfs


def make_config(tmp_path):
    return AppConfig(project_root=tmp_path, paths=PathsConfig())


def test_preflight_pdfs_empty_folder_is_friendly(tmp_path):
    config = make_config(tmp_path)
    initialize_data(config)

    result = preflight_pdfs(config)

    assert any("No PDFs found yet" in message for message in result.messages)
    assert (config.path("reports_dir") / "pdf_preflight_report.md").exists()


def test_preflight_pdfs_reports_populated_folder(monkeypatch, tmp_path):
    config = make_config(tmp_path)
    initialize_data(config)
    pdf_path = config.path("raw_pdf_dir") / "Wolf Fichtner" / "paper-2026.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-1.4 mock")

    def fake_inspect(path, raw_dir):
        assert path == pdf_path
        return PdfPreflightRow(
            filename="Wolf Fichtner/paper-2026.pdf",
            pages=10,
            text_chars=100,
            chars_per_page=10.0,
            likely_scanned=True,
            filename_year="2026",
            extracted_year="2025",
            warnings=["very little text layer detected; PDF may be scanned"],
        )

    monkeypatch.setattr("paper_pipeline.preflight.inspect_pdf", fake_inspect)

    result = preflight_pdfs(config)
    report = (config.path("reports_dir") / "pdf_preflight_report.md").read_text(
        encoding="utf-8"
    )

    assert any("very little text layer" in warning for warning in result.warnings)
    assert "Wolf Fichtner/paper-2026.pdf" in report
    assert "Likely scanned PDFs: 1" in report
