"""People's Court Case Library provider contract; no scraper or private API."""

from __future__ import annotations

from .base import CaseSourceProvider, CaseSourceResult, CaseSourceSearchRequest, ProviderUnavailableError


class PeopleCourtCaseLibraryProvider(CaseSourceProvider):
    name = "people_court_case_library"
    search_available = False
    provider_status = "unavailable_no_documented_public_api"

    def search(self, request: CaseSourceSearchRequest) -> list[CaseSourceResult]:
        raise ProviderUnavailableError(
            "Case Library retrieval is intentionally not implemented without a documented API"
        )
