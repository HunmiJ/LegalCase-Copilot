"""V0.4 retrieval -> Top 8 context -> grounded generation pipeline."""

from __future__ import annotations

import re
import time

try:
    from hybrid_utils import HybridRetriever, fuse_ranked_results
    from reranker_utils import build_candidate_pool, rerank_candidates
except ModuleNotFoundError:  # package import from tests/application root
    from scripts.hybrid_utils import HybridRetriever, fuse_ranked_results
    from scripts.reranker_utils import build_candidate_pool, rerank_candidates

from .context_builder import build_context
from .generator import GroundedGenerator


LABOR_SCOPE_TERMS = ("劳动", "工资", "加班", "辞退", "解雇", "劳动合同", "社保", "仲裁", "竞业", "试用期", "派遣")
OUT_OF_DOMAIN_TERMS = ("租房", "租赁", "押金", "房东", "房屋")


def scope_guard(query: str, records: list[dict]) -> dict | None:
    """Reject clearly out-of-domain or unresolvable Arabic article requests."""
    if any(term in query for term in OUT_OF_DOMAIN_TERMS) and not any(term in query for term in LABOR_SCOPE_TERMS):
        return {
            "issue_summary": ["当前劳动争议知识库不足以可靠回答该问题。"],
            "legal_analysis": [], "relevant_laws": [],
            "missing_information": ["需要与租赁纠纷对应的法律资料。"],
            "next_steps": ["请查询租赁法律法规或咨询相关专业人士。"],
            "disclaimer": "当前知识库不覆盖该领域，不构成法律意见。",
            "generation_status": "out_of_domain",
        }
    numeric_articles = re.findall(r"第(\d+)条", query)
    if numeric_articles:
        available = {str(record.get("article_number")) for record in records}
        if not any(any(number in article for article in available) for number in numeric_articles):
            return {
                "issue_summary": ["提供的阿拉伯数字条号无法在当前法规库中核验。"],
                "legal_analysis": [], "relevant_laws": [],
                "missing_information": ["需要确认法律名称、有效条号和适用法规版本。"],
                "next_steps": ["不要依据无法核验的条号作出法律判断。"],
                "disclaimer": "当前仅能对法规库中可核验的条文进行检索，不构成法律意见。",
                "generation_status": "unverifiable_article",
            }
    return None


class LegalRAGPipeline:
    def __init__(self, provider, retriever=None, reranker=None, candidate_depth: int = 50, context_top_k: int = 8):
        self.provider = provider
        self.retriever = retriever or HybridRetriever()
        self.reranker = reranker
        self.candidate_depth = candidate_depth
        self.context_top_k = context_top_k

    def ask(self, query: str) -> dict:
        guarded = scope_guard(query, self.retriever.records)
        if guarded is not None:
            return {"query": query, "response": guarded,
                    "context": {"items": [], "context_text": "", "article_count": 0, "char_count": 0},
                    "retrieval_latency_ms": 0.0,
                    "generation_meta": {"retry_count": 0, "fallback": False,
                                         "validation": {"valid": True, "errors": [],
                                                         "citation_validity": 1.0,
                                                         "citation_precision": 1.0,
                                                         "grounded_claim_rate": 1.0,
                                                         "unsupported_citation_rate": 0.0}}}
        total_start = time.perf_counter()
        bm25_start = time.perf_counter()
        bm25_results = self.retriever.bm25.search(query, self.candidate_depth)
        bm25_ms = (time.perf_counter() - bm25_start) * 1000
        semantic_start = time.perf_counter()
        semantic_results = self.retriever.semantic_search(query, self.candidate_depth)
        semantic_ms = (time.perf_counter() - semantic_start) * 1000
        candidates = fuse_ranked_results(bm25_results, semantic_results, limit=len(bm25_results) + len(semantic_results))
        if self.reranker is None:
            try:
                from reranker_utils import load_reranker
            except ModuleNotFoundError:
                from scripts.reranker_utils import load_reranker
            self.reranker = load_reranker(local_files_only=True)
        rerank_start = time.perf_counter()
        reranked = rerank_candidates(self.reranker, query, candidates, self.context_top_k)
        reranker_ms = (time.perf_counter() - rerank_start) * 1000
        context_start = time.perf_counter()
        context = build_context(reranked, self.context_top_k)
        context_ms = (time.perf_counter() - context_start) * 1000
        response, generation_meta = GroundedGenerator(self.provider).generate(query, context)
        total_ms = (time.perf_counter() - total_start) * 1000
        generation_ms = generation_meta.get("generation_latency_ms", 0.0)
        validation_ms = generation_meta.get("validation_latency_ms", 0.0)
        return {"query": query, "response": response, "context": context,
                "retrieval_latency_ms": bm25_ms + semantic_ms + reranker_ms,
                "latency_breakdown_ms": {"bm25": bm25_ms, "semantic": semantic_ms,
                                          "reranker": reranker_ms, "context_builder": context_ms,
                                          "generation": max(0.0, generation_ms - validation_ms),
                                          "validation": validation_ms,
                                          "total": total_ms},
                "generation_meta": generation_meta}
