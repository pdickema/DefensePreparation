from __future__ import annotations

from paper_pipeline.chunking import chunk_paper
from paper_pipeline.metadata import paper_id, slugify
from paper_pipeline.utils import read_jsonl, write_jsonl


def test_filename_slug_generation():
    assert slugify("Marc Wouters: Cost Accounting!") == "marc-wouters-cost-accounting"


def test_paper_id_generation():
    row = {"examiner": "Marc Wouters", "title": "Cost Accounting", "year": "2015"}
    assert paper_id(row) == "marc-wouters_2015_cost-accounting"


def test_section_aware_chunking_schema(tmp_path):
    paper = {
        "paper_id": "marc-wouters_2015_cost-accounting",
        "metadata": {
            "filename": "paper.pdf",
            "examiner": "Marc Wouters",
            "title": "Cost Accounting",
            "year": 2015,
            "doi": "10.test/example",
            "sha256": "abc",
        },
        "sections": [
            {
                "section_id": "sec_0001",
                "heading": "Abstract",
                "level": 1,
                "page_start": None,
                "page_end": None,
                "text": " ".join(["accounting"] * 150),
            }
        ],
    }

    chunks = chunk_paper(paper, target_tokens=80, overlap_tokens=10)
    output = tmp_path / "chunks.jsonl"
    write_jsonl(output, chunks)
    rows = read_jsonl(output)

    assert rows
    assert rows[0]["chunk_id"].startswith("marc-wouters_cost-accounting_")
    assert rows[0]["section"] == "Abstract"
    assert rows[0]["source_pdf"] == "paper.pdf"
    assert isinstance(rows[0]["token_count_estimate"], int)
