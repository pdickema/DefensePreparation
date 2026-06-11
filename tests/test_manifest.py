from __future__ import annotations

import csv

from paper_pipeline.config import AppConfig, PathsConfig
from paper_pipeline.manifest import (
    NO_PDFS_MESSAGE,
    initialize_data,
    read_manifest,
    scan_pdfs,
    validate_manifest,
    write_manifest,
)


def make_config(tmp_path):
    return AppConfig(project_root=tmp_path, paths=PathsConfig())


def test_data_folder_initialization(tmp_path):
    config = make_config(tmp_path)
    result = initialize_data(config)

    assert result.messages
    assert config.path("raw_pdf_dir").exists()
    assert config.path("markdown_dir").exists()
    assert config.path("json_dir").exists()
    assert config.path("manifest_path").exists()


def test_scan_pdfs_empty_folder_is_friendly(tmp_path):
    config = make_config(tmp_path)
    initialize_data(config)

    result = scan_pdfs(config)

    assert NO_PDFS_MESSAGE in result.messages
    assert config.path("manifest_path").exists()


def test_scan_pdfs_adds_mock_filenames(tmp_path):
    config = make_config(tmp_path)
    initialize_data(config)
    pdf_path = config.path("raw_pdf_dir") / "wouters-2015-test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 mock")

    result = scan_pdfs(config)
    rows = read_manifest(config.path("manifest_path"))

    assert any(row["filename"] == "wouters-2015-test.pdf" for row in rows)
    assert any("Added draft manifest row" in message for message in result.messages)


def test_validate_manifest_detects_duplicate_hashes(tmp_path):
    config = make_config(tmp_path)
    initialize_data(config)
    raw_dir = config.path("raw_pdf_dir")
    (raw_dir / "a.pdf").write_bytes(b"same pdf bytes")
    (raw_dir / "b.pdf").write_bytes(b"same pdf bytes")
    write_manifest(
        config.path("manifest_path"),
        [
            {
                "filename": "a.pdf",
                "examiner": "A",
                "title": "Paper A",
                "year": "2020",
                "doi": "",
                "source": "Manual",
                "notes": "",
            },
            {
                "filename": "b.pdf",
                "examiner": "B",
                "title": "Paper B",
                "year": "2021",
                "doi": "",
                "source": "Manual",
                "notes": "",
            },
        ],
    )

    validate_manifest(config)

    with (config.path("processed_dir") / "manifest_enriched.csv").open(
        "r", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["duplicate_sha256"] == "true"
    assert rows[1]["duplicate_sha256"] == "true"
