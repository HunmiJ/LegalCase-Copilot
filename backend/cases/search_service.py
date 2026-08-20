"""Unified local/official/cache-aware case search service."""

from __future__ import annotations

from dataclasses import dataclass

from .search.models import CaseSearchResult, deduplicate_results
from .sources.base import CaseSourceProvider, CaseSourceSearchRequest, ProviderUnavailableError
from .sources.local import LocalCuratedCaseProvider


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    search_available: bool
    status: str


class UnifiedCaseSearchService:
    def __init__(self, local_provider: LocalCuratedCaseProvider | None = None, official_providers: list[CaseSourceProvider] | None = None) -> None:
        self.local_provider = local_provider or LocalCuratedCaseProvider()
        self.official_providers = official_providers or []
        self.provider_status = [
            ProviderStatus(provider.name, bool(getattr(provider, "search_available", True)), getattr(provider, "provider_status", "unknown"))
            for provider in self.official_providers
        ]

    def search(self, query: str, top_k: int = 10, sources: list[str] | None = None) -> list[CaseSearchResult]:
        request = CaseSourceSearchRequest(query=query, limit=top_k)
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
