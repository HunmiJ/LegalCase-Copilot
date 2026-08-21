from __future__ import annotations

import unittest

from .case_context_builder import CaseAugmentedContextBuilder


class FakeLawRetriever:
    def search(self, query: str, limit: int = 5):
        return [{"law_name": "劳动合同法", "article_number": "第三十九条", "article_content": f"与{query}相关的法规内容"}]


class FakeCaseRetriever:
    def search(self, query: str, top_k: int = 5, mode: str = "keyword"):
        return [{"case_id": "runtime-1", "title": f"{query}案例", "dispute_focus": query, "judgment_result": "支持部分请求", "score": 1.0}]


class CaseContextBuilderTest(unittest.TestCase):
    def setUp(self):
        self.builder = CaseAugmentedContextBuilder(FakeLawRetriever(), FakeCaseRetriever())

    def test_context_contains_law_and_case_sources_for_required_queries(self):
        for query in ("违法解除劳动合同", "加班费争议", "竞业限制"):
            context = self.builder.build(query)
            self.assertEqual(set(context), {"laws", "cases", "context_text"})
            self.assertEqual(context["laws"][0]["law_title"], "劳动合同法")
            self.assertEqual(context["cases"][0]["case_title"], f"{query}案例")
            self.assertIn("LEGAL_SOURCES:", context["context_text"])
            self.assertIn("CASE_SOURCES:", context["context_text"])

    def test_empty_results_produce_stable_shape(self):
        class Empty:
            def search(self, *args, **kwargs): return []
        context = CaseAugmentedContextBuilder(Empty(), Empty()).build("劳动争议")
        self.assertEqual(context, {"laws": [], "cases": [], "context_text": ""})


if __name__ == "__main__":
    unittest.main()
