"""Adapt case search results into citation-addressable RAG context items."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from backend.cases.search.models import CaseSearchResult


def _text(value: Any) -> str:
    """Return an optional result field as a clean string."""

    return "" if value is None else str(value)


def adapt_case_result(result: CaseSearchResult, position: int) -> dict[str, str]:
    """Convert one ``CaseSearchResult`` to an isolated CASE citation item.

    Court, judgment date, and legal basis are copied from the normalized case
    result when available; ``getattr`` keeps the adapter compatible with
    lightweight providers used by older callers.
    """

    if position < 1:
        raise ValueError("position must be positive")

    source = result.source_url or result.source_file or result.source_name
    item = {
        "citation_id": f"CASE-{position}",
        "type": "case",
        "case_id": _text(result.case_id),
        "title": _text(result.title),
        "court": _text(getattr(result, "court", None)),
        "date": _text(getattr(result, "judgment_date", None)),
        "facts": _text(result.basic_facts),
        "legal_issue": _text(result.dispute_focus),
        "judgment": _text(result.judgment_result),
        "source": _text(source),
    }
    legal_basis = [str(value) for value in getattr(result, "legal_basis", []) or []]
    if item["court"] or item["date"] or legal_basis:
        item.update({
            "dispute_focus": _text(result.dispute_focus),
            "basic_facts": _text(result.basic_facts),
            "judgment_result": _text(result.judgment_result),
            "legal_basis": legal_basis,
        })
    return item


def adapt_case_results(results: Iterable[CaseSearchResult]) -> list[dict[str, str]]:
    """Convert ranked case results to ``CASE-1``, ``CASE-2``, ... items."""

    return [adapt_case_result(result, position) for position, result in enumerate(results, 1)]


__all__ = ["adapt_case_result", "adapt_case_results"]
