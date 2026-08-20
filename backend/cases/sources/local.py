"""Local curated corpus provider contract.

The implementation is intentionally deferred to the existing parser/database
workflow. Runtime cache and curated corpus must not be silently merged.
"""

from __future__ import annotations

from .base import CaseSourceProvider, CaseSourceResult, CaseSourceSearchRequest, ProviderUnavailableError


class LocalCuratedCaseProvider(CaseSourceProvider):
    name = "curated_local_case_corpus"

    def search(self, request: CaseSourceSearchRequest) -> list[CaseSourceResult]:
        raise ProviderUnavailableError(
            "Local case retrieval adapter is not implemented in V0.7.1B audit"
        )
