from __future__ import annotations

import csv

from paper_pipeline.config import AppConfig, PathsConfig
from paper_pipeline.manifest import (
    NO_PDFS_MESSAGE,
    initialize_data,
    merge_extracted_metadata,
    read_manifest,
    scan_pdfs,
    validate_manifest,
    write_manifest,
)
from paper_pipeline.pdf_metadata import ExtractedPdfMetadata, metadata_from_values


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


def test_scan_pdfs_infers_examiner_from_folder(tmp_path):
    config = make_config(tmp_path)
    initialize_data(config)
    examiner_dir = config.path("raw_pdf_dir") / "Wolf Fichtner"
    examiner_dir.mkdir()
    pdf_path = examiner_dir / "energy-accounting.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 mock")

    scan_pdfs(config)
    rows = read_manifest(config.path("manifest_path"))
    row = next(row for row in rows if row["filename"] == "Wolf Fichtner/energy-accounting.pdf")

    assert row["examiner"] == "Wolf Fichtner"
    assert row["title"] == "energy accounting"


def test_scan_pdfs_handles_multiple_examiner_folders(tmp_path):
    config = make_config(tmp_path)
    initialize_data(config)
    for examiner, filename in [
        ("Wolf Fichtner", "energy-storage.pdf"),
        ("Marc Wouters", "management-accounting.pdf"),
    ]:
        pdf_path = config.path("raw_pdf_dir") / examiner / filename
        pdf_path.parent.mkdir()
        pdf_path.write_bytes(b"%PDF-1.4 mock")

    scan_pdfs(config)
    rows = read_manifest(config.path("manifest_path"))

    assert {row["examiner"] for row in rows} == {"Wolf Fichtner", "Marc Wouters"}
    assert {row["filename"] for row in rows} == {
        "Wolf Fichtner/energy-storage.pdf",
        "Marc Wouters/management-accounting.pdf",
    }


def test_scan_pdfs_replaces_example_rows_when_real_pdfs_are_found(tmp_path):
    config = make_config(tmp_path)
    initialize_data(config)
    pdf_path = config.path("raw_pdf_dir") / "Wolf Fichtner" / "energy-accounting.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-1.4 mock")

    scan_pdfs(config)
    rows = read_manifest(config.path("manifest_path"))

    assert [row["filename"] for row in rows] == ["Wolf Fichtner/energy-accounting.pdf"]


def test_merge_extracted_metadata_preserves_manual_values():
    row = {
        "filename": "Wolf Fichtner/paper.pdf",
        "examiner": "Wolf Fichtner",
        "title": "Manual Title",
        "year": "2024",
        "doi": "",
        "source": "",
        "notes": "Curated by hand",
    }
    extracted = ExtractedPdfMetadata(
        title="Extracted Title",
        year="2026",
        doi="10.1016/example",
        source="Energy Journal",
    )

    updated, changed = merge_extracted_metadata(row, extracted, row["filename"])

    assert updated["title"] == "Manual Title"
    assert updated["year"] == "2024"
    assert updated["doi"] == "10.1016/example"
    assert updated["source"] == "Energy Journal"
    assert changed == ["doi", "source"]


def test_metadata_from_pdf_values_extracts_scientific_fields():
    extracted = metadata_from_values(
        {
            "Title": "Design limits and investment risks of mid-term storage",
            "Subject": "Energy Conversion and Management, 360 (2026) 121554. "
            "doi:10.1016/j.enconman.2026.121554",
            "Creator": "Elsevier",
        },
        "",
    )

    assert extracted.title == "Design limits and investment risks of mid-term storage"
    assert extracted.year == "2026"
    assert extracted.doi == "10.1016/j.enconman.2026.121554"
    assert extracted.source == "Energy Conversion and Management"


def test_metadata_year_prefers_publication_year_over_body_year():
    extracted = metadata_from_values(
        {
            "Title": "A stochastic multi-energy simulation model for UK residential buildings",
            "Subject": "Energy & Buildings, 168 (2018) 470-489. "
            "doi:10.1016/j.enbuild.2018.02.051",
            "Creator": "Elsevier",
        },
        "The UK government is aiming at a national carbon emission reduction target by 2050.",
    )

    assert extracted.year == "2018"
    assert extracted.doi == "10.1016/j.enbuild.2018.02.051"


def test_doi_does_not_consume_following_metadata():
    extracted = metadata_from_values(
        {
            "Subject": "Journal, 1 (2026) 1. doi:10.1016/j.test.2026.123456",
            "Creator": "Elsevier",
        },
        "",
    )

    assert extracted.doi == "10.1016/j.test.2026.123456"


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
