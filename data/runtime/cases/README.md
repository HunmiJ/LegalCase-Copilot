# V0.7.8 Runtime Case Corpus

This directory is physically and logically separate from the frozen
`data/raw/cases/` and `data/processed/cases/` benchmark corpus.

The builder is implemented in `backend/cases/runtime_builder.py` and is
initialized with:

```powershell
python scripts/build_runtime_corpus.py
```

Runtime discovery and ingestion are resumable through the ignored files
`manifest.jsonl`, `collection_plan.json`, and `collection_stats.json`.
Downloaded PDFs, processed JSONL, embeddings, and embedding indexes are
intentionally excluded from Git. Credentials and browser session data must
remain in the browser session and must never be written here.
