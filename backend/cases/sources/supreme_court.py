"""Supreme People's Court provider contract; no scraper or undocumented API."""

from __future__ import annotations

from .base import CaseSourceProvider, CaseSourceResult, CaseSourceSearchRequest, ProviderUnavailableError


class SupremeCourtOfficialProvider(CaseSourceProvider):
    name = "supreme_court_official"

    def search(self, request: CaseSourceSearchRequest) -> list[CaseSourceResult]:
        raise ProviderUnavailableError(
            "Official web retrieval is intentionally not implemented without a documented API"
        )
