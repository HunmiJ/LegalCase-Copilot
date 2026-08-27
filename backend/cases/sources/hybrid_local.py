"""Local BM25 + Semantic case provider using a frozen V0.7.6 configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..corpus_config import resolve_case_corpus
from ..search.bm25 import CaseBM25Index
from ..search.hybrid import CaseHybridIndex
from ..search.semantic import CaseSemanticIndex
from .base import CaseSourceSearchRequest


class LocalHybridCaseProvider:
    name = "curated_local_case_hybrid"
    search_available = True
    provider_status = "available"

    def __init__(self, config_path: Path | None = None, model=None, corpus_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[3]
        config_path = config_path or root / "evaluation/v076_hybrid_config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        corpus_config = resolve_case_corpus(corpus_path)
        bm25 = CaseBM25Index.from_jsonl(corpus_config.corpus_path)
        semantic = CaseSemanticIndex.from_files(corpus_config.corpus_path, corpus_config.embeddings_path,
                                                corpus_config.index_path, model=model)
        configured_weight = os.getenv("CASE_SEMANTIC_WEIGHT")
        semantic_weight = float(configured_weight) if configured_weight is not None else config.get("semantic_weight", 0.8)
        if not 0.0 <= semantic_weight <= 1.0:
            raise ValueError("CASE_SEMANTIC_WEIGHT must be between 0 and 1")
        self.index = CaseHybridIndex(bm25, semantic, method=config["method"], rrf_k=config.get("rrf_k") or 60,
                                     semantic_weight=semantic_weight,
                                     candidate_top_k=config.get("bm25_top_k", 10))

    def search(self, request: CaseSourceSearchRequest | str, top_k: int = 10):
        if isinstance(request, str):
            return self.index.search(request, top_k)
        return self.index.search(request.query, request.limit)
