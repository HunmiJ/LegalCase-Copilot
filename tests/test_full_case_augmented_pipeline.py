from __future__ import annotations

import unittest
from pathlib import Path

from backend.cases.search.models import CaseSearchResult
from backend.cases.search_service import UnifiedCaseSearchService
from backend.rag.case_context_adapter import adapt_case_results
from backend.rag.context_builder import build_context
from backend.rag.pipeline import LegalRAGPipeline


ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT / "data/processed/full_cases"


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


class FakeCaseService:
    def __init__(self, results):
        self.results = results

    def search(self, query, top_k=10, mode="hybrid"):
        return self.results[:top_k]


class FakeReranker:
    def predict(self, pairs, **kwargs):
        return [1.0] * len(pairs)


class FullCaseAugmentedPipelineTest(unittest.TestCase):
    def test_full_corpus_loads_6492_cases(self):
        service = UnifiedCaseSearchService(corpus_path=FULL)
        self.assertEqual(len(service.local_provider.index.records), 6492)
        self.assertEqual(service.corpus_config.directory, FULL.resolve())

    def test_full_case_result_enters_context_with_complete_fields(self):
        result = CaseSearchResult(
            case_id="full-1", title="违法解除劳动合同案", court="某市人民法院",
            judgment_date="2024-01-01", basic_facts="员工被解除",
            dispute_focus="违法解除", judgment_result="支付赔偿金",
            legal_basis=["《劳动合同法》第四十八条"], source_file="labor_case_dataset_6492",
            source_name="labor_case_dataset_6492",
        )
        case_item = adapt_case_results([result])[0]
        context = build_context(
            law_items=[{"law_name": "劳动合同法", "article_number": "第四十八条",
                        "article_content": "违法解除应承担责任。", "source_file": "law.docx"}],
            case_items=[case_item],
        )
        self.assertIn("[LAW-1]", context["context_text"])
        self.assertIn("[CASE-1]", context["context_text"])
        for value in ("违法解除劳动合同案", "某市人民法院", "2024-01-01", "违法解除", "员工被解除", "支付赔偿金", "《劳动合同法》第四十八条"):
            self.assertIn(value, context["context_text"])

    def test_law_and_case_namespaces_do_not_collide(self):
        context = build_context(
            law_items=[{"law_name": "劳动法", "article_number": "第一条",
                        "article_content": "法规正文", "source_file": "law.docx"}],
            case_items=[adapt_case_results([CaseSearchResult(case_id="case-1", title="案例", basic_facts="事实")])[0]],
        )
        citations = [item["citation_id"] for item in context["items"]]
        self.assertEqual(citations, ["LAW-1", "CASE-1"])
        self.assertEqual(len(citations), len(set(citations)))

    def test_pipeline_without_cases_falls_back_to_law_context(self):
        pipeline = LegalRAGPipeline(
            provider=object(), retriever=FakeLawRetriever(), reranker=FakeReranker(),
            include_cases=True, case_search_service=FakeCaseService([]),
        )
        result = pipeline.ask("劳动合同法第一条是什么？")
        self.assertEqual(result["context"]["case_items"], [])
        self.assertIn("[LAW-1]", result["context"]["context_text"])

    def test_pipeline_defaults_case_service_to_full_corpus(self):
        pipeline = LegalRAGPipeline(provider=object(), retriever=FakeLawRetriever(), include_cases=True)
        self.assertEqual(pipeline.case_search_service.corpus_config.directory, FULL.resolve())
        self.assertEqual(len(pipeline.case_search_service.local_provider.index.records), 6492)


if __name__ == "__main__":
    unittest.main()
