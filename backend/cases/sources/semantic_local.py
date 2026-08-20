"""Local semantic provider backed by precomputed case embeddings."""

from __future__ import annotations

from pathlib import Path

from ..search.semantic import CaseSemanticIndex
from ..search.models import CaseSearchResult
from .base import CaseSourceSearchRequest


class LocalSemanticCaseProvider:
    name = "curated_local_case_semantic"
    search_available = True
    provider_status = "available"

    def __init__(self, corpus_path: Path | None = None, embeddings_path: Path | None = None, index_path: Path | None = None, model=None) -> None:
        root = Path(__file__).resolve().parents[3]
        corpus_path = corpus_path or root / "data/processed/cases/cases.jsonl"
        embeddings_path = embeddings_path or root / "data/processed/cases/case_embeddings.npy"
        index_path = index_path or root / "data/processed/cases/case_embedding_index.json"
        self.index = CaseSemanticIndex.from_files(corpus_path, embeddings_path, index_path, model=model)

    def search(self, request: CaseSourceSearchRequest | str, top_k: int = 10) -> list[CaseSearchResult]:
        if isinstance(request, str):
            return self.index.search(request, top_k)
        return self.index.search(request.query, request.limit)
