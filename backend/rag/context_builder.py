"""Build a bounded, citation-addressable law and case context."""

from __future__ import annotations

from typing import Any

try:
    from hybrid_utils import canonical_id
except ModuleNotFoundError:  # package import from tests/application root
    from scripts.hybrid_utils import canonical_id


def _build_law_item(result: dict[str, Any], position: int) -> dict[str, Any] | None:
    content = str(result.get("article_content") or "")
    if not content:
        return None
    block = " ".join(filter(None, [result.get("law_name"), result.get("chapter"),
                                     result.get("article_number"), content]))
    return {
        "citation_id": f"LAW-{position}",
        "type": "law",
        "canonical_id": canonical_id(result),
        "law_name": result.get("law_name"),
        "article_number": result.get("article_number"),
        "chapter": result.get("chapter"),
        "article_content": content,
        "source_file": result.get("source_file"),
        "text": block,
    }


def _safe_truncate(value: Any, max_chars: int) -> str:
    text = str(value or "")
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def build_context(
    results: list[dict] | None = None,
    max_articles: int = 5,
    max_chars: int = 24000,
    *,
    law_items: list[dict[str, Any]] | None = None,
    case_items: list[dict[str, Any]] | None = None,
    max_cases: int = 5,
    case_fact_max_chars: int | None = None,
) -> dict:
    """Build context while preserving the original law-only call signature.

    The legacy positional form (``build_context(results, max_articles)``)
    retains its historic ``[1]`` citation IDs. Supplying ``law_items`` or
    ``case_items`` uses the V0.8 isolated namespaces ``LAW-*`` and ``CASE-*``.
    """

    augmented = law_items is not None or case_items is not None
    if law_items is None:
        law_items = results or []
    if case_items is None:
        case_items = []

    items: list[dict[str, Any]] = []
    law_context_items: list[dict[str, Any]] = []
    case_context_items: list[dict[str, Any]] = []
    used_chars = 0

    for result in law_items[:max_articles]:
        item = _build_law_item(result, len(law_context_items) + 1)
        if item is None:
            continue
        if not augmented:
            item["citation_id"] = f"[{len(law_context_items) + 1}]"
        if used_chars + len(item["text"]) > max_chars and items:
            continue
        items.append(item)
        law_context_items.append(item)
        used_chars += len(item["text"])

    for source in case_items[:max_cases]:
        item = dict(source)
        item.setdefault("type", "case")
        item.setdefault("citation_id", f"CASE-{len(case_context_items) + 1}")
        facts = item.get("basic_facts") or item.get("facts")
        if case_fact_max_chars is not None:
            facts = _safe_truncate(facts, case_fact_max_chars)
            if "basic_facts" in item:
                item["basic_facts"] = facts
            elif "facts" in item:
                item["facts"] = facts
        block = " ".join(filter(None, [
            item.get("title"), item.get("court"), item.get("date"),
            item.get("dispute_focus") or item.get("legal_issue"),
            facts,
            item.get("judgment_result") or item.get("judgment"),
            "；".join(str(value) for value in item.get("legal_basis", []) or []),
        ]))
        if not block:
            continue
        if used_chars + len(block) > max_chars and items:
            continue
        # Keep the legacy retrieval-only fallback safe when it iterates over
        # the unified item list and expects law-shaped keys.
        item.setdefault("law_name", "")
        item.setdefault("article_number", "")
        item.setdefault("article_content", "")
        item.setdefault("source_file", item.get("source", ""))
        item["text"] = block
        items.append(item)
        case_context_items.append(item)
        used_chars += len(block)

    lines = []
    for item in items:
        source = item.get("source") or item.get("source_file") or ""
        lines.append(f"[{item['citation_id']}] {item['text']}\n来源：{source}")
    context_text = "\n".join(lines)
    return {
        "items": items,
        "law_items": law_context_items,
        "case_items": case_context_items,
        "context_text": context_text,
        "article_count": len(law_context_items),
        "case_count": len(case_context_items),
        "char_count": len(context_text),
    }
