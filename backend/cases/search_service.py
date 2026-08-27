"""Unified local/official/cache-aware case search service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .corpus_config import CaseCorpusConfig, resolve_case_corpus
from .search.models import CaseSearchResult, deduplicate_results
from .sources.base import CaseSourceProvider, CaseSourceSearchRequest, ProviderUnavailableError
from .sources.local import LocalCuratedCaseProvider


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    search_available: bool
    status: str


class UnifiedCaseSearchService:
    def __init__(self, local_provider: LocalCuratedCaseProvider | None = None, official_providers: list[CaseSourceProvider] | None = None,
                 corpus_path: Path | str | None = None) -> None:
        self.corpus_config: CaseCorpusConfig = resolve_case_corpus(corpus_path)
        self.local_provider = local_provider or LocalCuratedCaseProvider(self.corpus_config.corpus_path)
        self.official_providers = official_providers or []
        self.last_reranker_status = "not_used"
        self.provider_status = [
            ProviderStatus(provider.name, bool(getattr(provider, "search_available", True)), getattr(provider, "provider_status", "unknown"))
            for provider in self.official_providers
        ]

    def search(self, query: str, top_k: int = 10, sources: list[str] | None = None, mode: str = "hybrid") -> list[CaseSearchResult]:
        if mode not in {"bm25", "semantic", "hybrid", "reranked"}:
            raise ValueError("mode must be bm25, semantic, hybrid, or reranked")
        if mode == "hybrid":
            from .sources.hybrid_local import LocalHybridCaseProvider
            return LocalHybridCaseProvider(corpus_path=self.corpus_config.corpus_path).search(CaseSourceSearchRequest(query=query, limit=top_k))
        request = CaseSourceSearchRequest(query=query, limit=top_k)
        if mode == "semantic":
            from .sources.semantic_local import LocalSemanticCaseProvider
            return LocalSemanticCaseProvider(corpus_path=self.corpus_config.corpus_path).search(request)
        if mode == "reranked":
            from .sources.reranked_local import LocalRerankedCaseProvider
            provider = LocalRerankedCaseProvider(corpus_path=self.corpus_config.corpus_path)
            results = provider.search(request)
            self.last_reranker_status = "available" if provider.reranker_available else f"unavailable: {provider.unavailable_reason}"
            return results
        results: list[CaseSearchResult] = []
        selected = [provider for provider in self.official_providers if not sources or provider.name in sources]
        for provider in selected:
            if not getattr(provider, "search_available", False):
                continue
            try:
                results.extend(provider.search(request))
            except ProviderUnavailableError:
                continue
        if not results:
            results = self.local_provider.search(request)
        return deduplicate_results(results)[:top_k]
