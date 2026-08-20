"""Stable contracts for unified case-source retrieval.

This module deliberately contains no network access. Provider implementations
must be added only after an official, documented access mechanism is verified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class CaseSourceSearchRequest:
    """Normalized search request shared by all case providers."""

    query: str
    limit: int = 10
    filters: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query must not be empty")
        if self.limit < 1:
            raise ValueError("limit must be positive")


@dataclass(frozen=True)
class CaseSourceResult:
    """A source-traceable, normalized case search result."""

    title: str
    database_case_number: str | None
    case_number: str | None
    case_type: str | None
    basic_facts: str | None
    case_gist: str | None
    source_name: str
    source_url: str
    retrieved_at: str

    @classmethod
    def now_utc(cls, **kwargs: object) -> "CaseSourceResult":
        """Construct a result with an explicit UTC retrieval timestamp."""

        return cls(
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            **kwargs,
        )


class CaseSourceProvider(Protocol):
    """Provider contract for local, official, and future public API sources."""

    name: str

    def search(self, request: CaseSourceSearchRequest) -> list[CaseSourceResult]:
        """Search the provider and return normalized, traceable results."""
        ...


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider cannot be used without unsafe or undocumented access."""


def choose_provider(
    official_provider: CaseSourceProvider | None,
    local_provider: CaseSourceProvider,
    request: CaseSourceSearchRequest,
) -> list[CaseSourceResult]:
    """Use official results when available, otherwise fall back to local corpus.

    This policy does not perform retries, scraping, or implicit network access.
    """

    if official_provider is not None:
        try:
            results = official_provider.search(request)
        except ProviderUnavailableError:
            results = []
        if results:
            return results[: request.limit]
    return local_provider.search(request)[: request.limit]
