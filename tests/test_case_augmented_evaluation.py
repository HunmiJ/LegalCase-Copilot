from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.rag.case_context_adapter import adapt_case_results
from backend.rag.context_builder import build_context
from backend.cases.search.models import CaseSearchResult


ROOT = Path(__file__).resolve().parents[1]


class CaseAugmentedEvaluationTest(unittest.TestCase):
    def setUp(self):
        self.case = CaseSearchResult(
            case_id="case-eval-1", title="竞业限制案", basic_facts="离职后进入竞争公司",
            dispute_focus="竞业限制效力", judgment_result="支持部分请求",
            source_file="case.pdf", source_name="人民法院案例库",
        )
        self.law = {
            "id": "law-eval-1", "law_name": "劳动合同法", "article_number": "第二十三条",
            "article_content": "可以约定竞业限制。", "source_file": "law.docx",
        }

    def test_integrated_query_set_has_at_least_twenty_items(self):
        queries = json.loads((ROOT / "evaluation/case_augmented_rag/integrated_queries.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(queries), 20)
        self.assertTrue(all({"query", "expected_laws", "expected_cases"} <= set(row) for row in queries))

    def test_law_and_case_citations_are_generated_without_confusion(self):
        context = build_context(law_items=[self.law], case_items=adapt_case_results([self.case]))
        citations = {item["citation_id"] for item in context["items"]}
        self.assertEqual(citations, {"LAW-1", "CASE-1"})
        self.assertTrue(all(item["citation_id"].startswith(("LAW-", "CASE-")) for item in context["items"]))
        self.assertNotEqual("LAW-1", "CASE-1")

    def test_empty_case_context_falls_back_to_law_context(self):
        context = build_context(law_items=[self.law], case_items=[])
        self.assertEqual(context["case_count"], 0)
        self.assertEqual([item["citation_id"] for item in context["items"]], ["LAW-1"])
        self.assertIn("[LAW-1]", context["context_text"])


if __name__ == "__main__":
    unittest.main()
