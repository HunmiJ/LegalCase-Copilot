"""Build a bounded, citation-addressable context from V0.4 results."""

from __future__ import annotations

try:
    from hybrid_utils import canonical_id
except ModuleNotFoundError:  # package import from tests/application root
    from scripts.hybrid_utils import canonical_id


def build_context(results: list[dict], max_articles: int = 5, max_chars: int = 24000) -> dict:
    items = []
    used_chars = 0
    for result in results[:max_articles]:
        content = str(result.get("article_content") or "")
        if not content:
            continue
        block = " ".join(filter(None, [result.get("law_name"), result.get("chapter"),
                                         result.get("article_number"), content]))
        if used_chars + len(block) > max_chars and items:
            continue
        citation_id = f"[{len(items) + 1}]"
        item = {
            "citation_id": citation_id,
            "canonical_id": canonical_id(result),
            "law_name": result.get("law_name"),
            "article_number": result.get("article_number"),
            "chapter": result.get("chapter"),
            "article_content": content,
            "source_file": result.get("source_file"),
        }
        item["text"] = block
        items.append(item)
        used_chars += len(block)
    context_text = "\n".join(f"{item['citation_id']} {item['text']}\n来源文件：{item['source_file']}" for item in items)
    return {"items": items, "context_text": context_text, "article_count": len(items), "char_count": len(context_text)}
