# LegalCase-Copilot

AI Labor Law RAG Assistant for Chinese labor-dispute research. The project combines traceable labor-law retrieval, similar-case retrieval, grounded generation, and safety checks. It is a research and demonstration system, not a substitute for qualified legal advice.

## Project Overview

The assistant supports:

- Labor-law and judicial-interpretation retrieval
- Similar labor-dispute case retrieval
- BM25, embedding, and hybrid retrieval
- Cross-encoder reranking
- Case-Augmented RAG
- Citation verification and provenance tracking
- Safety guards and evidence-insufficient refusal

The corpus is source-traceable: law records retain their source documents, and curated cases retain official source URLs, source PDFs, stable case IDs, and eligibility metadata.

## Architecture

```text
User question
      ↓
Query Understanding
      ↓
Law Retrieval ─────────┐
      ↓                │
Case Retrieval ────────┤
      ↓                │
Reranker               │
      ↓                │
Context Builder ◄─────┘
      ↓
LLM Generation
      ↓
Citation Validator
      ↓
Structured answer / safe refusal
```

The legacy law-only path remains available. Case augmentation is enabled by passing a case search service or `include_cases=True` to `LegalRAGPipeline`.

## Technical Highlights

- BM25 keyword retrieval with Chinese tokenization
- BGE embedding retrieval
- Deterministic hybrid fusion
- Cross-encoder reranking with `BAAI/bge-reranker-base`
- Case-Augmented RAG with separate law and case evidence
- Grounded generation with bounded retries
- Citation namespaces: `LAW-*` and `CASE-*`
- Citation validation against the actual retrieved context
- Evidence-insufficient fallback for unsupported or out-of-domain questions

## Evaluation Results

Results below are frozen artifacts already produced in `evaluation/`.

### Law retrieval

Held-out V0.7.6 hybrid test, 10 queries:

| Method | Recall@1 | Recall@3 | Recall@5 |
|---|---:|---:|---:|
| BM25 | 1.0000 | 1.0000 | 1.0000 |
| Semantic | 0.9000 | 1.0000 | 1.0000 |
| Hybrid | 1.0000 | 1.0000 | 1.0000 |

### Case retrieval

V0.7.6 Full-30 descriptive case benchmark:

| Method | Recall@1 | Recall@3 | Recall@5 |
|---|---:|---:|---:|
| BM25 | 0.8667 | 1.0000 | 1.0000 |
| Semantic | 0.9333 | 1.0000 | 1.0000 |
| Hybrid | 0.9667 | 1.0000 | 1.0000 |

### Grounded RAG

Deterministic V0.6 evaluation:

| Citation validity | Grounded claim rate | Unsupported citation rate |
|---:|---:|---:|
| 1.0000 | 1.0000 | 0.0000 |

### Case-Augmented RAG

20-query integrated evaluation:

| Mode | Law recall | Case recall | Citation validity |
|---|---:|---:|---:|
| Law-only | 0.9750 | 0.0000 | 1.0000 |
| Law + case | 0.9750 | 0.9750 | 1.0000 |

### Safety

Deterministic V0.9 safety smoke evaluation:

| Refusal accuracy | Unsupported claim rate |
|---:|---:|
| 1.0000 | 0.0000 |

These are benchmark and deterministic smoke results, not a claim of production-level legal accuracy.

## Project Structure

```text
backend/
├─ cases/                  # Case schema, sources, search, retrieval
├─ llm/                    # Provider interface and configuration
└─ rag/                    # Context, generation, validation, pipeline
data/
├─ raw/                    # Source documents and PDFs
├─ processed/              # Curated JSONL, SQLite, embeddings, indexes
└─ runtime/                # Separately managed runtime case artifacts
docs/                      # Architecture, data, and evaluation documentation
evaluation/                # Reproducible benchmark runners and outputs
scripts/                   # Parsing, indexing, search, and demo utilities
tests/                     # Unit and regression tests
```

## Quick Start

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH = ".;scripts"
python -m pytest tests
```

Or run the Windows demo workflow:

```powershell
.\scripts\run_demo.ps1
```

To run a deterministic local query without an external LLM:

```powershell
$env:PYTHONPATH = ".;scripts"
python scripts/ask_legal.py "公司违法解除劳动合同怎么办？" --provider mock
```

For a real OpenAI-compatible provider, copy `.env.example` to `.env` and set the API key locally. Never commit real credentials.

## Documentation

- [Architecture](docs/architecture.md)
- [Evaluation report](docs/evaluation_report.md)
- [Data sources](docs/data_sources.md)
- [Case data specification](docs/case_data_spec.md)

## Reproducibility Notes

- Formal corpora and benchmark labels are kept separate from runtime collection artifacts.
- Case IDs and law canonical IDs are used for identity; titles and article numbers alone are not sufficient.
- The default evaluation provider is deterministic and makes no network calls.
- Cached files, compiled Python files, debug captures, and smoke-test outputs are excluded from the public project surface.
