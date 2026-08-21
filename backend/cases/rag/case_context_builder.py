"""Build a unified law + runtime-case context without changing the RAG core."""

from __future__ import annotations

from typing import Any

from ..retrieval import RuntimeCaseRetriever


class CaseAugmentedContextBuilder:
    def __init__(self, law_retriever=None, case_retriever=None):
        if law_retriever is None:
            try:
                from scripts.hybrid_utils import HybridRetriever
            except ModuleNotFoundError:
                from hybrid_utils import HybridRetriever
            law_retriever = HybridRetriever()
        self.law_retriever = law_retriever
        self.case_retriever = case_retriever or RuntimeCaseRetriever()

    def build(self, query: str, law_top_k: int = 5, case_top_k: int = 5, case_mode: str = "keyword") -> dict[str, Any]:
        law_results = self.law_retriever.search(query, limit=law_top_k)
        case_results = self.case_retriever.search(query, top_k=case_top_k, mode=case_mode)
        laws = [{
            "law_title": result.get("law_title") or result.get("law_name"),
            "article": result.get("article") or result.get("article_number"),
            "content": result.get("content") or result.get("article_content"),
        } for result in law_results]
        cases = [{
            "case_id": result.get("case_id"),
            "case_title": result.get("case_title") or result.get("title"),
            "dispute_focus": result.get("dispute_focus"),
            "judgment_result": result.get("judgment_result"),
        } for result in case_results]
        legal_text = "\n".join(f"{item['law_title']} {item['article']}：{item['content']}" for item in laws if item["content"])
        case_text = "\n".join(f"{item['case_title']}；争点：{item['dispute_focus'] or ''}；裁判结果：{item['judgment_result'] or ''}" for item in cases)
        sections = []
        if legal_text:
            sections.append("LEGAL_SOURCES:\n" + legal_text)
        if case_text:
            sections.append("CASE_SOURCES:\n" + case_text)
        return {"laws": laws, "cases": cases, "context_text": "\n\n".join(sections)}
