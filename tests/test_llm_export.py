from __future__ import annotations

from paper_pipeline.config import AppConfig, LlmExportConfig, PathsConfig
from paper_pipeline.llm_export import _select_examiner_chunks, export_llm_corpus
from paper_pipeline.manifest import initialize_data
from paper_pipeline.utils import read_jsonl, write_json, write_jsonl


def make_config(tmp_path, export: LlmExportConfig | None = None):
    return AppConfig(
        project_root=tmp_path,
        paths=PathsConfig(),
        llm_export=export or LlmExportConfig(),
    )


def test_export_llm_empty_corpus_is_friendly(tmp_path):
    config = make_config(tmp_path)
    initialize_data(config)

    result = export_llm_corpus(config)

    assert any("No chunks found yet" in message for message in result.messages)
    assert (config.path("llm_export_dir") / "corpus_overview.md").exists()
    assert (config.path("llm_export_dir") / "llm_prompt_template.md").exists()
    assert read_jsonl(config.path("llm_export_dir") / "chunks_for_rag.jsonl") == []


def test_export_llm_writes_examiner_pack(tmp_path):
    config = make_config(tmp_path)
    initialize_data(config)
    _write_mock_corpus(config)

    export_llm_corpus(config)

    pack = config.path("llm_export_dir") / "examiner_pack_wolf-fichtner.md"
    text = pack.read_text(encoding="utf-8")

    assert "LLM Examiner Pack: Wolf Fichtner" in text
    assert "Design limits and investment risks" in text
    assert "chunk_0001" in text
    assert "Source PDF: `Wolf Fichtner/paper.pdf`" in text


def test_export_llm_rag_jsonl_preserves_metadata(tmp_path):
    config = make_config(tmp_path)
    initialize_data(config)
    _write_mock_corpus(config)

    export_llm_corpus(config)
    rows = read_jsonl(config.path("llm_export_dir") / "chunks_for_rag.jsonl")

    assert rows[0]["chunk_id"] == "chunk_0001"
    assert rows[0]["title"] == "Design limits and investment risks"
    assert rows[0]["examiner"] == "Wolf Fichtner"
    assert rows[0]["doi"] == "10.1016/example"
    assert rows[0]["section"] == "Methods"
    assert rows[0]["source_pdf"] == "Wolf Fichtner/paper.pdf"
    assert "simulation" in rows[0]["text"]


def test_export_llm_can_exclude_references(tmp_path):
    config = make_config(tmp_path, LlmExportConfig(include_references=False))
    initialize_data(config)
    _write_mock_corpus(config, include_reference_chunk=True)

    export_llm_corpus(config)
    rows = read_jsonl(config.path("llm_export_dir") / "chunks_for_rag.jsonl")

    assert [row["chunk_id"] for row in rows] == ["chunk_0001"]


def test_export_llm_selects_excerpts_across_papers():
    chunks = []
    for paper_index in range(3):
        for chunk_index, section in enumerate(["References", "Introduction", "Methods"], start=1):
            chunks.append(
                {
                    "chunk_id": f"paper_{paper_index}_{chunk_index}",
                    "paper_id": f"paper_{paper_index}",
                    "title": f"Paper {paper_index}",
                    "chunk_index": chunk_index,
                    "section": section,
                }
            )

    selected = _select_examiner_chunks(chunks, limit=3)

    assert {chunk["paper_id"] for chunk in selected} == {"paper_0", "paper_1", "paper_2"}
    assert all(chunk["section"] == "Introduction" for chunk in selected)


def _write_mock_corpus(config: AppConfig, include_reference_chunk: bool = False) -> None:
    paper_id = "wolf-fichtner_2026_design-limits"
    paper = {
        "paper_id": paper_id,
        "metadata": {
            "filename": "Wolf Fichtner/paper.pdf",
            "examiner": "Wolf Fichtner",
            "title": "Design limits and investment risks",
            "year": 2026,
            "doi": "10.1016/example",
            "source": "Energy Journal",
        },
        "conversion": {
            "primary_tool": "docling",
            "actual_tool": "pypdfium2-text",
            "fallback_used": True,
            "warnings": ["Docling output appears incomplete"],
        },
        "sections": [{"heading": "Methods", "text": "Simulation method text."}],
    }
    write_json(config.path("json_dir") / "paper.json", paper)
    chunks = [
        {
            "chunk_id": "chunk_0001",
            "paper_id": paper_id,
            "examiner": "Wolf Fichtner",
            "title": "Design limits and investment risks",
            "year": 2026,
            "doi": "10.1016/example",
            "source_pdf": "Wolf Fichtner/paper.pdf",
            "section": "Methods",
            "section_level": 1,
            "page_start": None,
            "page_end": None,
            "chunk_index": 1,
            "sha256": "abc",
            "text": "This chunk discusses simulation, storage design, and investment risk.",
            "token_count_estimate": 12,
        }
    ]
    if include_reference_chunk:
        chunks.append(
            {
                **chunks[0],
                "chunk_id": "chunk_0002",
                "section": "References",
                "chunk_index": 2,
                "text": "Reference list entry.",
            }
        )
    write_jsonl(config.path("chunks_jsonl"), chunks)
