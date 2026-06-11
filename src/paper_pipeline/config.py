from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class PathsConfig(BaseModel):
    data_dir: Path = Path("data")
    raw_pdf_dir: Path = Path("data/raw_pdfs")
    manifest_path: Path = Path("data/manifest.csv")
    processed_dir: Path = Path("data/processed")
    markdown_dir: Path = Path("data/processed/markdown")
    json_dir: Path = Path("data/processed/json")
    tei_dir: Path = Path("data/processed/tei")
    chunks_dir: Path = Path("data/chunks")
    chunks_jsonl: Path = Path("data/chunks/chunks.jsonl")
    index_dir: Path = Path("data/index")
    reports_dir: Path = Path("data/reports")
    exports_dir: Path = Path("data/exports")
    llm_export_dir: Path = Path("data/exports/llm")


class ConversionConfig(BaseModel):
    primary: Literal["docling", "pypdfium2-text"] = "pypdfium2-text"
    use_grobid: bool = False
    grobid_url: str = "http://localhost:8070"
    fallback_marker: bool = False
    fallback_ocr: bool = False
    preserve_references: bool = True
    suspicious_text_length: int = 1200


class ChunkingConfig(BaseModel):
    target_tokens: int = Field(default=900, ge=100)
    overlap_tokens: int = Field(default=120, ge=0)

    @field_validator("overlap_tokens")
    @classmethod
    def overlap_smaller_than_target(cls, value: int, info: Any) -> int:
        target = info.data.get("target_tokens", 900)
        if value >= target:
            raise ValueError("overlap_tokens must be smaller than target_tokens")
        return value


class IndexConfig(BaseModel):
    enabled: bool = False
    provider: Literal["sentence-transformers", "openai"] = "sentence-transformers"
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    vector_store: Literal["chromadb"] = "chromadb"
    allow_external_embeddings: bool = False


class PrivacyConfig(BaseModel):
    local_only: bool = True
    allow_external_pdf_upload: bool = False
    allow_external_text_upload: bool = False
    allow_llm_generation: bool = False


class DefensePrepConfig(BaseModel):
    enabled: bool = True
    generate_llm_hooks: bool = True


class ProcessingConfig(BaseModel):
    clean_generated_outputs: bool = False


class LlmExportConfig(BaseModel):
    enabled: bool = True
    max_chunks_per_examiner: int = Field(default=24, ge=1)
    max_chars_per_chunk: int = Field(default=1800, ge=200)
    include_references: bool = True
    include_full_chunk_text: bool = True


class AppConfig(BaseModel):
    project_root: Path = Field(default_factory=Path.cwd)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    conversion: ConversionConfig = Field(default_factory=ConversionConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    defense_prep: DefensePrepConfig = Field(default_factory=DefensePrepConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    llm_export: LlmExportConfig = Field(default_factory=LlmExportConfig)

    def resolve(self, path: Path | str) -> Path:
        path = Path(path)
        if path.is_absolute():
            return path
        return (self.project_root / path).resolve()

    def path(self, name: str) -> Path:
        return self.resolve(getattr(self.paths, name))


def load_config(config_path: Path | str = "config/config.yaml") -> AppConfig:
    config_path = Path(config_path)
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()

    data: dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Config file must contain a mapping: {config_path}")
        data = loaded

    data["project_root"] = config_path.parent.parent

    grobid_url = os.getenv("GROBID_URL")
    if grobid_url:
        data.setdefault("conversion", {})["grobid_url"] = grobid_url

    return AppConfig.model_validate(data)
