# Architecture

## System boundary

LegalCase-Copilot is a labor-law research assistant. It retrieves source-grounded legal materials and produces structured, citation-addressable output. It does not decide cases or replace legal advice.

## Data flow

1. A user submits a labor-dispute question.
2. Query understanding identifies the labor-law scope and retrieval intent. The stable production path keeps query expansion optional.
3. Law retrieval searches the processed law corpus with BM25 and embedding retrieval.
4. Case retrieval searches the curated case corpus independently with BM25, semantic retrieval, hybrid fusion, and optional case reranking.
5. The reranker orders the law candidate pool and, where enabled, the case candidate pool.
6. The Context Builder creates bounded evidence blocks and preserves source provenance.
7. The generator receives only the assembled context and returns structured JSON.
8. The Citation Validator checks every cited ID against the exact context items. Invalid or unsupported evidence triggers retry or a safe refusal.

## Module responsibilities

| Layer | Main location | Responsibility |
|---|---|---|
| Law data | `data/raw/laws`, `data/processed` | Source documents, normalized law records, SQLite and vector artifacts |
| Case data | `data/raw/cases`, `data/processed/cases` | Official PDFs, eligibility, normalized records and case vectors |
| Law retrieval | `scripts/bm25_utils.py`, `scripts/semantic_utils.py`, `scripts/hybrid_utils.py` | BM25, semantic retrieval and law rank fusion |
| Case retrieval | `backend/cases/search/`, `backend/cases/search_service.py` | Case BM25, semantic, hybrid, reranker and provider orchestration |
| Pipeline | `backend/rag/pipeline.py` | Query-to-context orchestration while preserving law-only mode |
| Context | `backend/rag/context_builder.py`, `backend/rag/case_context_adapter.py` | Bounded, typed and citation-addressable evidence |
| Generation | `backend/rag/generator.py` | Structured grounded answer, retries and evidence-insufficient fallback |
| Validation | `backend/rag/citation_validator.py` | Citation validity, precision, grounded claim and unsupported citation checks |
| Evaluation | `evaluation/` | Frozen retrieval, case, RAG and safety benchmarks |

## Citation design

Citations are identifiers of context items, not free-form references invented by the model.

- Law items use `LAW-1`, `LAW-2`, and so on.
- Case items use `CASE-1`, `CASE-2`, and so on.
- The namespaces are independent; a case can never satisfy a law citation.
- The context item retains canonical identity and source provenance.
- The final structured answer materializes law content and case metadata from validated context, not from untrusted model text.

The text presentation wraps identifiers in brackets, for example `[LAW-1]`, while the structured citation value remains `LAW-1`.

## Law and case isolation

Laws and cases are intentionally stored and retrieved separately:

- Laws provide normative authority: statutes, regulations and judicial interpretations.
- Cases provide analogical evidence: facts, issues, reasoning and outcomes.
- A similar case cannot replace a legal rule.
- Law recall and case recall are evaluated independently.
- Case retrieval failure leaves the law-only path available.
- Case data is not merged into the law SQLite/FTS schema or law embedding index.

## Reproducibility and safety

Formal corpora, benchmark labels and evaluation outputs are separate from runtime collection artifacts. Stable IDs and source URLs permit auditability. The default evaluation providers are deterministic and offline. When context is empty, a citation is unsupported, or the question is outside the labor-law scope, generation returns an evidence-insufficient response rather than guessing.
