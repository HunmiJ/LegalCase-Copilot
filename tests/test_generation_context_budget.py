from __future__ import annotations

import unittest

from backend.cases.search.models import CaseSearchResult
from backend.rag.context_builder import build_context
from backend.rag.pipeline import LegalRAGPipeline


class _LawIndex:
    def search(self, query, limit):
        return [{"id": f"law-{i}", "law_name": "劳动合同法", "article_number": f"第{i}条",
                 "article_content": f"法规正文{i}", "source_file": "laws.jsonl",
                 "rank": i, "bm25_score": 1.0} for i in range(1, min(limit, 8) + 1)]


class _LawRetriever:
    def __init__(self):
        self.bm25 = _LawIndex()
        self.records = [{"article_number": "第一条"}]

    def semantic_search(self, query, limit):
        results = self.bm25.search(query, limit)
        for result in results:
            result["similarity_score"] = 1.0
        return results


class _Reranker:
    def __init__(self):
        self.candidate_count = None

    def predict(self, pairs, **kwargs):
        self.candidate_count = len(pairs)
        return [1.0] * len(pairs)


class _Cases:
    def __init__(self, results):
        self.results = results

    def search(self, query, top_k=10, mode="hybrid"):
        return self.results[:top_k]


class _FailingProvider:
    def complete_with_metadata(self, *args, **kwargs):
        raise OSError("not called successfully in budget test")


class GenerationContextBudgetTest(unittest.TestCase):
    def _case(self):
        return CaseSearchResult(
            case_id="case-1", title="劳动合同解除案", court="基层法院",
            judgment_date="2024-01-01", dispute_focus="违法解除",
            basic_facts="事实" * 1000, judgment_result="裁判结果保留",
            legal_basis=["劳动合同法第四十八条"], source_file="cases.jsonl",
        )

    def test_pipeline_keeps_upstream_retrieval_depth_but_generation_defaults_are_3_and_2(self):
        reranker = _Reranker()
        pipeline = LegalRAGPipeline(
            _FailingProvider(), retriever=_LawRetriever(), reranker=reranker,
            include_cases=True, case_search_service=_Cases([self._case()] * 5),
        )
        result = pipeline.ask("劳动合同解除是否合法？")
        self.assertEqual(pipeline.generation_law_top_k, 3)
        self.assertEqual(pipeline.generation_case_top_k, 2)
        self.assertEqual(result["context"]["article_count"], 3)
        self.assertEqual(result["context"]["case_count"], 2)
        self.assertEqual(reranker.candidate_count, 8)

    def test_basic_facts_are_safely_truncated_and_citations_survive(self):
        context = build_context(
            law_items=[{"id": "law-1", "law_name": "劳动合同法", "article_number": "第四十八条",
                        "article_content": "法规依据", "source_file": "laws.jsonl"}],
            case_items=[{"citation_id": "CASE-1", "type": "case", "title": "案件",
                         "court": "法院", "date": "2024-01-01", "dispute_focus": "违法解除",
                         "judgment_result": "裁判结果保留", "legal_basis": ["劳动合同法第四十八条"],
                         "basic_facts": "事实" * 1000}],
            max_articles=1, max_cases=1, max_chars=3500, case_fact_max_chars=40,
        )
        case = context["case_items"][0]
        self.assertLessEqual(len(context["context_text"]), 3500)
        self.assertEqual(case["citation_id"], "CASE-1")
        self.assertIn("裁判结果保留", case["text"])
        self.assertIn("劳动合同法第四十八条", case["text"])
        self.assertLessEqual(len(case["basic_facts"]), 41)
        self.assertEqual(context["law_items"][0]["citation_id"], "LAW-1")

    def test_budget_prefers_law_and_omits_case_when_no_safe_room(self):
        context = build_context(
            law_items=[{"id": "law-1", "law_name": "劳动法", "article_number": "第一条",
                        "article_content": "法条" * 1000, "source_file": "laws.jsonl"}],
            case_items=[{"citation_id": "CASE-1", "type": "case", "title": "案件",
                         "judgment_result": "结果", "basic_facts": "事实" * 100}],
            max_articles=1, max_cases=1, max_chars=100,
            case_fact_max_chars=20,
        )
        self.assertEqual([item["citation_id"] for item in context["items"]], ["LAW-1"])
        self.assertNotIn("CASE-1", context["context_text"])


if __name__ == "__main__":
    unittest.main()
