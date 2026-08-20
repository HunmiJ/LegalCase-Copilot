"""Unified result and canonical identity helpers for case retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CaseSearchResult:
    case_id: str
    title: str
    case_number: str | None = None
    database_case_number: str | None = None
    case_type: str | None = None
    keywords: list[str] = field(default_factory=list)
    basic_facts: str | None = None
    dispute_focus: str | None = None
    case_gist: str | None = None
    court_reasoning: str | None = None
    judgment_result: str | None = None
    source_name: str = ""
    source_url: str | None = None
    source_file: str | None = None
    retrieved_at: str = ""
    retrieval_source: str = "local"
    score: float = 0.0
    matched_sources: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.title.strip():
            raise ValueError("case_id and title must be non-empty")
        if self.retrieval_source not in {"local", "official", "cache"}:
            raise ValueError("invalid retrieval_source")


def canonical_case_key(result: CaseSearchResult) -> str:
    """Return a cross-provider identity without merging similar case numbers."""

    if result.database_case_number:
        return f"database:{result.database_case_number}"
    if result.case_number:
        return f"case:{result.case_number}\x1f{result.title}"
    return f"fallback:{result.title}\x1f{result.source_file or result.source_url or result.case_id}"


def deduplicate_results(results: list[CaseSearchResult]) -> list[CaseSearchResult]:
    """Merge duplicate provider results while preserving provenance."""

    merged: dict[str, CaseSearchResult] = {}
    order: list[str] = []
    for result in results:
        key = canonical_case_key(result)
        if key not in merged:
            result.matched_sources = list(dict.fromkeys(result.matched_sources or [result.retrieval_source]))
            merged[key] = result
            order.append(key)
            continue
        current = merged[key]
        current.matched_sources = list(dict.fromkeys(current.matched_sources + result.matched_sources + [result.retrieval_source]))
        if result.score > current.score:
            current.score = result.score
        for field_name in ("source_url", "source_file", "case_number", "case_type", "basic_facts", "dispute_focus", "case_gist", "court_reasoning", "judgment_result"):
            if getattr(current, field_name) in (None, "") and getattr(result, field_name) not in (None, ""):
                setattr(current, field_name, getattr(result, field_name))
    return [merged[key] for key in order]
