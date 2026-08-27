from __future__ import annotations

import unittest

from backend.cases.search.models import CaseSearchResult
from backend.rag.context_builder import build_context
from backend.rag.pipeline import LegalRAGPipeline


class FakeLawRetriever:
    records = [{"article_number": "第一条"}]

    def __init__(self):
        self.bm25 = self

    def search(self, query, limit):
        return [{
            "id": "law-1", "law_name": "劳动合同法", "article_number": "第一条",
            "chapter": "第一章", "article_content": "保护劳动者合法权益。",
            "source_file": "law.docx", "rank": 1, "bm25_score": 1.0,
        }]

    def semantic_search(self, query, limit):
        result = self.search(query, limit)[0].copy()
        result["similarity_score"] = 1.0
        result["rank"] = 1
        return [result]


class FakeCaseSearchService:
    def __init__(self, results):
        self.results = results

    def search(self, query, top_k=10, mode="hybrid"):
        return self.results[:top_k]


class FakeReranker:
    def predict(self, pairs, **kwargs):
        return [1.0] * len(pairs)


class CaseAugmentedPipelineTest(unittest.TestCase):
    def setUp(self):
        self.case = CaseSearchResult(
            case_id="case-1", title="确认劳动关系案", basic_facts="长期接受公司管理",
            dispute_focus="劳动关系认定", judgment_result="确认存在劳动关系",
            source_file="case.pdf", source_name="人民法院案例库",
        )

    def test_law_and_case_results_enter_unified_context(self):
        context = build_context(
            law_items=[{
                "id": "law-1", "law_name": "劳动合同法", "article_number": "第一条",
                "article_content": "保护劳动者合法权益。", "source_file": "law.docx",
            }],
            case_items=[{
                "citation_id": "CASE-1", "type": "case", "case_id": "case-1",
                "title": "确认劳动关系案", "court": "", "date": "",
                "facts": "长期接受公司管理", "legal_issue": "劳动关系认定",
                "judgment": "确认存在劳动关系", "source": "case.pdf",
            }],
        )

        self.assertIn("[LAW-1]", context["context_text"])
        self.assertIn("[CASE-1]", context["context_text"])
        self.assertEqual({item["type"] for item in context["items"]}, {"law", "case"})

    def test_pipeline_calls_case_service_and_keeps_namespaces_isolated(self):
        service = FakeCaseSearchService([self.case])
        pipeline = LegalRAGPipeline(
            provider=object(), retriever=FakeLawRetriever(), reranker=FakeReranker(),
            include_cases=True, case_search_service=service,
        )
        # The fake provider is sufficient here because context construction is
        # completed before generation; generation failure is safely contained.
        result = pipeline.ask("如何确认劳动关系？")
        citations = [item["citation_id"] for item in result["context"]["items"]]
        self.assertIn("LAW-1", citations)
        self.assertIn("CASE-1", citations)
        self.assertNotIn("LAW-1", {"CASE-1"})

    def test_empty_cases_keep_pipeline_running(self):
        pipeline = LegalRAGPipeline(
            provider=object(), retriever=FakeLawRetriever(), reranker=FakeReranker(),
            include_cases=True, case_search_service=FakeCaseSearchService([]),
        )
        result = pipeline.ask("劳动合同法第一条是什么？")
        self.assertEqual(result["context"]["case_items"], [])
        self.assertEqual(result["context"]["case_count"], 0)
        self.assertIn("LAW-1", result["context"]["context_text"])

    def test_legacy_law_only_context_call_remains_available(self):
        context = build_context([{
            "id": "law-1", "law_name": "劳动法", "article_number": "第一条",
            "article_content": "正文", "source_file": "law.docx",
        }])
        self.assertEqual(context["items"][0]["citation_id"], "[1]")


if __name__ == "__main__":
    unittest.main()
