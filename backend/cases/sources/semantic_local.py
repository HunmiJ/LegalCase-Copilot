"""Local semantic provider backed by precomputed case embeddings."""

from __future__ import annotations

from pathlib import Path

from ..corpus_config import resolve_case_corpus
from ..search.semantic import CaseSemanticIndex
from ..search.models import CaseSearchResult
from .base import CaseSourceSearchRequest


class LocalSemanticCaseProvider:
    name = "curated_local_case_semantic"
    search_available = True
    provider_status = "available"

    def __init__(self, corpus_path: Path | None = None, embeddings_path: Path | None = None, index_path: Path | None = None, model=None) -> None:
        config = resolve_case_corpus(corpus_path)
        embeddings_path = embeddings_path or config.embeddings_path
        index_path = index_path or config.index_path
        self.index = CaseSemanticIndex.from_files(config.corpus_path, embeddings_path, index_path, model=model)

    def search(self, request: CaseSourceSearchRequest | str, top_k: int = 10) -> list[CaseSearchResult]:
        if isinstance(request, str):
            return self.index.search(request, top_k)
        return self.index.search(request.query, request.limit)
