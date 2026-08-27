"""Optional Cross-Encoder case provider with safe Hybrid fallback."""

from __future__ import annotations

from pathlib import Path

from .base import CaseSourceSearchRequest
from ..search.reranker import DEFAULT_CANDIDATE_DEPTH, RerankerUnavailableError, load_case_reranker, rerank
from .hybrid_local import LocalHybridCaseProvider


class LocalRerankedCaseProvider:
    name = "curated_local_case_reranked"
    search_available = True
    provider_status = "available"

    def __init__(self, model=None, model_loader=load_case_reranker, hybrid_provider=None, corpus_path: Path | None = None) -> None:
        self.hybrid_provider = hybrid_provider or LocalHybridCaseProvider(model=model, corpus_path=corpus_path)
        self.model = model
        self.model_loader = model_loader
        self.reranker_available = model is not None
        self.unavailable_reason: str | None = None

    def search(self, request: CaseSourceSearchRequest | str, top_k: int = DEFAULT_CANDIDATE_DEPTH):
        if isinstance(request, str):
            query, limit = request, top_k
        else:
            query, limit = request.query, request.limit
        candidates = self.hybrid_provider.search(CaseSourceSearchRequest(query=query, limit=DEFAULT_CANDIDATE_DEPTH))
        try:
            if self.model is None:
                try:
                    self.model = self.model_loader(local_files_only=True)
                except Exception as exc:
                    raise RerankerUnavailableError(str(exc)) from exc
            self.reranker_available = True
            return rerank(self.model, query, candidates, top_k=limit)
        except RerankerUnavailableError as exc:
            self.reranker_available = False
            self.unavailable_reason = str(exc)
            return candidates[:limit]
