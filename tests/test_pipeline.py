from __future__ import annotations

from paper_pipeline.config import AppConfig, ConversionConfig, PrivacyConfig
from paper_pipeline.converters.common import ConversionResult
from paper_pipeline.manifest import initialize_data, write_manifest
from paper_pipeline.pipeline import (
    _clear_generated_paper_outputs,
    _convert_with_fallbacks,
    _grobid_upload_allowed,
    _is_local_url,
    chunk_processed_papers,
)
from paper_pipeline.utils import read_jsonl, write_json


def test_grobid_local_urls_are_allowed_by_default():
    assert _is_local_url("http://localhost:8070")
    assert _is_local_url("http://127.0.0.1:8070")


def test_grobid_external_url_requires_explicit_pdf_upload_permission():
    blocked = AppConfig(
        conversion=ConversionConfig(
            use_grobid=True,
            grobid_url="https://grobid.example.org",
        )
    )
    allowed = AppConfig(
        conversion=ConversionConfig(
            use_grobid=True,
            grobid_url="https://grobid.example.org",
        ),
        privacy=PrivacyConfig(allow_external_pdf_upload=True),
    )

    assert not _grobid_upload_allowed(blocked)
    assert _grobid_upload_allowed(allowed)


def test_pypdfium_primary_is_not_marked_as_fallback(monkeypatch, tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"mock pdf")

    def fake_pdfium_convert(path):
        assert path == pdf_path
        return ConversionResult(
            markdown="Extracted text",
            tool="pypdfium2-text",
            fallback_used=True,
            warnings=["fallback wording"],
        )

    def fail_docling(path):
        raise AssertionError("Docling should not run when pypdfium2-text is primary")

    monkeypatch.setattr(
        "paper_pipeline.pipeline.pdfium_text_converter.convert_pdf",
        fake_pdfium_convert,
    )
    monkeypatch.setattr("paper_pipeline.pipeline.docling_converter.convert_pdf", fail_docling)

    conversion = _convert_with_fallbacks(
        AppConfig(conversion=ConversionConfig(primary="pypdfium2-text")),
        pdf_path,
        [],
    )

    assert conversion is not None
    assert conversion.tool == "pypdfium2-text"
    assert conversion.fallback_used is False
    assert conversion.warnings == []


def test_clear_generated_paper_outputs_preserves_gitkeep(tmp_path):
    config = AppConfig(project_root=tmp_path)
    for path_name, filename in [
        ("json_dir", "old.json"),
        ("markdown_dir", "old.md"),
        ("tei_dir", "old.tei.xml"),
    ]:
        directory = config.path(path_name)
        directory.mkdir(parents=True)
        (directory / filename).write_text("old", encoding="utf-8")
        (directory / ".gitkeep").write_text("", encoding="utf-8")

    _clear_generated_paper_outputs(config)

    assert not (config.path("json_dir") / "old.json").exists()
    assert not (config.path("markdown_dir") / "old.md").exists()
    assert not (config.path("tei_dir") / "old.tei.xml").exists()
    assert (config.path("json_dir") / ".gitkeep").exists()


def test_chunk_processed_papers_ignores_stale_json_not_in_manifest(tmp_path):
    config = AppConfig(project_root=tmp_path)
    initialize_data(config)
    write_manifest(
        config.path("manifest_path"),
        [
            {
                "filename": "Wolf Fichtner/current.pdf",
                "examiner": "Wolf Fichtner",
                "title": "Current Title",
                "year": "2026",
                "doi": "",
                "source": "Manual",
                "notes": "",
            }
        ],
    )
    current = {
        "paper_id": "wolf-fichtner_2026_current-title",
        "metadata": {
            "filename": "Wolf Fichtner/current.pdf",
            "examiner": "Wolf Fichtner",
            "title": "Current Title",
            "year": 2026,
        },
        "sections": [{"heading": "Abstract", "level": 1, "text": "current text"}],
    }
    stale = {
        **current,
        "paper_id": "wolf-fichtner_2026_old-title",
        "metadata": {**current["metadata"], "title": "Old Title"},
        "sections": [{"heading": "Abstract", "level": 1, "text": "stale text"}],
    }
    write_json(config.path("json_dir") / "wolf-fichtner_2026_current-title.json", current)
    write_json(config.path("json_dir") / "wolf-fichtner_2026_old-title.json", stale)

    chunk_processed_papers(config)
    chunks = read_jsonl(config.path("chunks_jsonl"))

    assert len(chunks) == 1
    assert chunks[0]["title"] == "Current Title"
    assert chunks[0]["text"] == "current text"
