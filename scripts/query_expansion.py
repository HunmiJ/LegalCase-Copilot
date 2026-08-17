"""Expansion and normalization helpers for structured query understanding."""

from __future__ import annotations


def expanded_queries(structured: dict, original_query: str, limit: int = 3) -> list[str]:
    """Return bounded unique search queries, always retaining the original query."""
    candidates = [original_query] + list(structured.get("search_queries", []))
    concepts = structured.get("legal_concepts", [])
    if concepts:
        candidates.append("劳动争议 " + " ".join(concepts[:5]))
    output = []
    seen = set()
    for query in candidates:
        if isinstance(query, str) and query.strip() and query not in seen:
            output.append(query.strip())
            seen.add(query)
        if len(output) >= limit:
            break
    return output or [original_query]
