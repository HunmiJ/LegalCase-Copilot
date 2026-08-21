from __future__ import annotations

import unittest

from evaluate_case_augmented_rag import evaluate_benchmark


class FakeLawRetriever:
    def search(self, query: str, limit: int = 5):
        return [{"law_name": "劳动合同法", "article_number": "第三十九条", "article_content": "与劳动争议相关的条文", "source_file": "law.docx"}]


class FakeCaseRetriever:
    def search(self, query: str, top_k: int = 5, mode: str = "keyword"):
        return [{"case_id": "case-1", "title": "相关案例", "dispute_focus": query, "judgment_result": "支持部分请求", "score": 1.0}]


class CaseAugmentedRAGEvaluationTest(unittest.TestCase):
    def test_baseline_and_enhanced_metrics_are_reported(self):
        benchmark = [{"id": "q1", "query": "违法解除劳动合同", "expected_law_terms": ["劳动合同法"], "expected_case_ids": ["case-1"]}]
        result = evaluate_benchmark(benchmark, FakeLawRetriever(), FakeCaseRetriever(), top_k=5)
        self.assertEqual(result["baseline"]["aggregate"]["law_recall_at_k"], 1.0)
        self.assertEqual(result["baseline"]["aggregate"]["case_recall_at_k"], 0.0)
        self.assertEqual(result["enhanced"]["aggregate"]["case_recall_at_k"], 1.0)
        self.assertIn("answer_success_rate", result["enhanced"]["aggregate"])


if __name__ == "__main__":
    unittest.main()
