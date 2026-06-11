# DefensePreparationPhilip

Local Python pipeline for converting scientific PDF papers into a clean,
structured, RAG-ready research corpus for private doctoral-defense preparation.

This project is for local corpus preparation, not model fine-tuning. It keeps
paper metadata, extracted text, sections, chunks, and source provenance together
so the publications of examiners can be searched, summarized, and inspected
without uploading full texts by default.

## Privacy Defaults

- Local processing only by default.
- No PDFs are uploaded.
- No extracted full texts are uploaded.
- No embedding or LLM API calls are made unless explicitly enabled in
  `config/config.yaml` and the required environment variables are present.
- Use the extracted corpus for private research preparation only. Do not
  redistribute copyrighted full texts or generated full-text derivatives.

## Windows Setup

Open this repository as a normal local folder in VS Code, not only through
GitHub RemoteHub. The recommended local path is:

```powershell
C:\pdickema\DefensePreparation
```

Create and activate a Python 3.11 virtual environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For PDF conversion with Docling, also install:

```powershell
python -m pip install -e ".[docling]"
```

For optional local vector search:

```powershell
python -m pip install -e ".[index]"
```

If editable extras are inconvenient, the base dependencies are also listed in
`requirements.txt`.

## First Run Before PDFs Exist

Initialize the data folders:

```powershell
python -m paper_pipeline.cli init-data
```

This creates:

- `data/raw_pdfs/`
- `data/processed/markdown/`
- `data/processed/json/`
- `data/processed/tei/`
- `data/chunks/`
- `data/index/`
- `data/reports/`
- `data/manifest.csv`

The example manifest rows are placeholders. Replace them later with real paper
metadata after adding PDFs.

If there are no PDFs yet, these commands should still be friendly:

```powershell
python -m paper_pipeline.cli scan-pdfs
python -m paper_pipeline.cli validate-manifest
python -m paper_pipeline.cli run-all
```

## Add PDFs Later

1. Put examiner publications in:

   ```text
   data/raw_pdfs/
   ```

2. Generate or update the draft manifest:

   ```powershell
   python -m paper_pipeline.cli scan-pdfs
   ```

3. Fill in missing metadata in:

   ```text
   data/manifest.csv
   ```

   Required columns:

   ```text
   filename,examiner,title,year,doi,source,notes
   ```

4. Validate the manifest:

   ```powershell
   python -m paper_pipeline.cli validate-manifest
   ```

5. Run the pipeline:

   ```powershell
   python -m paper_pipeline.cli run-all
   ```

## CLI Commands

```powershell
python -m paper_pipeline.cli init-data
python -m paper_pipeline.cli scan-pdfs
python -m paper_pipeline.cli validate-manifest
python -m paper_pipeline.cli process
python -m paper_pipeline.cli chunk
python -m paper_pipeline.cli report
python -m paper_pipeline.cli defense-prep
python -m paper_pipeline.cli build-index
python -m paper_pipeline.cli query "Which themes in Marc Wouters' papers might be relevant?"
python -m paper_pipeline.cli run-all
```

All commands read `config/config.yaml` by default.

## Outputs

- Clean Markdown per paper:
  - `data/processed/markdown/`
- Structured JSON per paper:
  - `data/processed/json/`
- Optional GROBID TEI XML:
  - `data/processed/tei/`
- RAG chunks:
  - `data/chunks/chunks.jsonl`
- Quality report:
  - `data/reports/conversion_quality_report.md`
- Defense-preparation helpers:
  - `data/reports/examiner_overview.md`
  - `data/reports/theme_index.md`
  - `data/reports/method_index.md`
  - `data/reports/theory_index.md`

## Optional GROBID Setup

GROBID is optional and is best run with Docker. Docker was not found during the
initial environment inspection, so install Docker Desktop first if you want this.

Start GROBID:

```powershell
docker run --rm -p 8070:8070 lfoppiano/grobid:latest
```

Test it:

```powershell
Invoke-WebRequest http://localhost:8070/api/isalive
```

Configure `config/config.yaml`:

```yaml
conversion:
  use_grobid: true
  grobid_url: "http://localhost:8070"
```

If GROBID is enabled but unavailable, the pipeline logs a warning and continues
with Docling or another configured fallback.

## Optional OCR Setup

OCR is disabled by default. Enable it only if you need scanned PDF support.

Install the system tools manually:

- Tesseract
- OCRmyPDF
- Ghostscript

Then set:

```yaml
conversion:
  fallback_ocr: true
```

If OCR is enabled but the tools are missing, the pipeline warns clearly and
continues where possible.

## Optional Marker Fallback

Marker is disabled by default and treated as an optional fallback. If enabled,
the code checks whether the Marker command is available before using it.

```yaml
conversion:
  fallback_marker: true
```

## Optional Local Vector Index

The default vector-index plan is local Sentence Transformers plus ChromaDB. It is
disabled until dependencies are installed and `index.enabled` is true.

```powershell
python -m pip install -e ".[index]"
python -m paper_pipeline.cli build-index
python -m paper_pipeline.cli query "What are the main methods used by examiner X?"
```

OpenAI embeddings are not used unless explicitly enabled in config and an API key
is provided through the environment.

## VS Code Recommendations

Recommended extensions:

- Python
- Pylance
- Ruff
- Rainbow CSV
- Docker, only if using GROBID through Docker
- Jupyter, optional for exploratory analysis

The pipeline does not require proprietary extensions.

## MCP Notes

MCP is optional and not required for version 1. Useful future MCP servers could
include narrow-permission filesystem/project access, GitHub access, Docker
control for GROBID, and documentation lookup. Avoid broad MCP permissions unless
there is a concrete need.

## Version-Control Notes

Usually commit:

- source code
- tests
- README
- config examples
- `.env.example`
- `.gitignore`
- placeholder `.gitkeep` files
- example `data/manifest.csv`

Usually do not commit:

- raw PDFs
- processed full texts
- vector indexes
- logs
- `.env`
- OCR intermediate files
- large generated reports

## Tests

Run:

```powershell
pytest
ruff check .
```

## Known Limitations

- Page ranges are only populated when the converter provides them.
- Docling, GROBID, Marker, OCR, and vector search are optional integrations and
  depend on external packages or services.
- The cleaning step is conservative and prioritizes faithful extraction over
  aggressive rewriting.
