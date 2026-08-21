"""Local BM25 + Semantic case provider using a frozen V0.7.6 configuration."""

from __future__ import annotations

import json
from pathlib import Path

from ..search.bm25 import CaseBM25Index
from ..search.hybrid import CaseHybridIndex
from ..search.semantic import CaseSemanticIndex
from .base import CaseSourceSearchRequest


class LocalHybridCaseProvider:
    name = "curated_local_case_hybrid"
    search_available = True
    provider_status = "available"

    def __init__(self, config_path: Path | None = None, model=None) -> None:
        root = Path(__file__).resolve().parents[3]
        config_path = config_path or root / "evaluation/v076_hybrid_config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        corpus = root / "data/processed/cases/cases.jsonl"
        bm25 = CaseBM25Index.from_jsonl(corpus)
        semantic = CaseSemanticIndex.from_files(corpus, root / "data/processed/cases/case_embeddings.npy",
                                                root / "data/processed/cases/case_embedding_index.json", model=model)
        self.index = CaseHybridIndex(bm25, semantic, method=config["method"], rrf_k=config.get("rrf_k") or 60,
                                     semantic_weight=config.get("semantic_weight", 0.8),
                                     candidate_top_k=config.get("bm25_top_k", 10))

    def search(self, request: CaseSourceSearchRequest | str, top_k: int = 10):
        if isinstance(request, str):
            return self.index.search(request, top_k)
        return self.index.search(request.query, request.limit)
