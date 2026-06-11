from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

from paper_pipeline.config import load_config
from paper_pipeline.defense_prep import generate_defense_prep
from paper_pipeline.indexing import build_index as build_vector_index
from paper_pipeline.indexing import query_index
from paper_pipeline.llm_export import export_llm_corpus
from paper_pipeline.manifest import initialize_data
from paper_pipeline.manifest import scan_pdfs as scan_pdfs_command
from paper_pipeline.manifest import validate_manifest as validate_manifest_command
from paper_pipeline.pipeline import chunk_processed_papers, process_papers
from paper_pipeline.pipeline import run_all as run_all_steps
from paper_pipeline.quality import generate_quality_report

app = typer.Typer(no_args_is_help=True)
ConfigOption = Annotated[Path, typer.Option("--config", "-c", help="Path to config YAML.")]


def _config(config: Path):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    return load_config(config)


def _print_result(messages: list[str], warnings: list[str] | None = None) -> None:
    for message in messages:
        typer.echo(message)
    for warning in warnings or []:
        typer.secho(f"Warning: {warning}", fg=typer.colors.YELLOW)


@app.command()
def init_data(
    config: ConfigOption = Path("config/config.yaml"),
    force_manifest: Annotated[
        bool, typer.Option("--force-manifest", help="Overwrite data/manifest.csv.")
    ] = False,
) -> None:
    """Create data folders and an example manifest without requiring PDFs."""
    result = initialize_data(_config(config), force_manifest=force_manifest)
    _print_result(result.messages, result.warnings)


@app.command()
def scan_pdfs(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Scan data/raw_pdfs and add draft manifest rows for new PDFs."""
    result = scan_pdfs_command(_config(config))
    _print_result(result.messages, result.warnings)


@app.command()
def validate_manifest(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Validate manifest filenames, metadata, hashes, and duplicates."""
    result = validate_manifest_command(_config(config))
    _print_result(result.messages, result.warnings)


@app.command()
def process(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Convert PDFs into Markdown and structured JSON."""
    result = process_papers(_config(config))
    _print_result(result.messages, result.warnings)


@app.command()
def chunk(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Create RAG-ready JSONL chunks from processed paper JSON."""
    result = chunk_processed_papers(_config(config))
    _print_result(result.messages, result.warnings)


@app.command()
def report(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Generate the conversion quality report."""
    path = generate_quality_report(_config(config))
    typer.echo(f"Wrote quality report: {path}")


@app.command()
def defense_prep(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Generate local defense-preparation helper outputs."""
    paths = generate_defense_prep(_config(config))
    for path in paths:
        typer.echo(f"Wrote defense-prep output: {path}")


@app.command()
def export_llm(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Export paste-friendly and RAG-friendly local LLM corpus files."""
    result = export_llm_corpus(_config(config))
    _print_result(result.messages, result.warnings)


@app.command()
def build_index(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Build an optional local ChromaDB vector index."""
    for message in build_vector_index(_config(config)):
        typer.echo(message)


@app.command()
def query(
    question: str,
    config: ConfigOption = Path("config/config.yaml"),
    n_results: Annotated[int, typer.Option("--n-results", min=1, max=20)] = 5,
) -> None:
    """Query the optional local vector index."""
    for message in query_index(_config(config), question, n_results=n_results):
        typer.echo(message)
        typer.echo("")


@app.command()
def run_all(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Run init, scan, validate, process, chunk, report, defense-prep, and export-llm."""
    result = run_all_steps(_config(config))
    _print_result(result.messages, result.warnings)


if __name__ == "__main__":
    app()
