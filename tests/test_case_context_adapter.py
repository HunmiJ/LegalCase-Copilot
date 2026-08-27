from __future__ import annotations

import unittest

from backend.cases.search.models import CaseSearchResult
from backend.rag.case_context_adapter import adapt_case_result, adapt_case_results


class CaseContextAdapterTest(unittest.TestCase):
    def _result(self, case_id: str, title: str, **kwargs) -> CaseSearchResult:
        return CaseSearchResult(
            case_id=case_id,
            title=title,
            basic_facts=kwargs.get("basic_facts", "劳动者主张确认劳动关系"),
            dispute_focus=kwargs.get("dispute_focus", "劳动关系认定"),
            judgment_result=kwargs.get("judgment_result", "支持诉请"),
            source_name="人民法院案例库",
            source_file=kwargs.get("source_file", "data/raw/cases/example.pdf"),
        )

    def test_adapts_result_to_required_case_context_shape(self):
        item = adapt_case_result(self._result("case-001", "确认劳动关系案"), 1)

        self.assertEqual(
            item,
            {
                "citation_id": "CASE-1",
                "type": "case",
                "case_id": "case-001",
                "title": "确认劳动关系案",
                "court": "",
                "date": "",
                "facts": "劳动者主张确认劳动关系",
                "legal_issue": "劳动关系认定",
                "judgment": "支持诉请",
                "source": "data/raw/cases/example.pdf",
            },
        )

    def test_assigns_independent_sequential_case_citations(self):
        items = adapt_case_results([
            self._result("case-001", "第一案"),
            self._result("case-002", "第二案"),
        ])

        self.assertEqual([item["citation_id"] for item in items], ["CASE-1", "CASE-2"])
        self.assertTrue(all(item["citation_id"].startswith("CASE-") for item in items))
        self.assertNotIn("LAW-1", {item["citation_id"] for item in items})

    def test_prefers_official_url_as_source(self):
        result = self._result("case-001", "案例", source_file="local.pdf")
        result.source_url = "https://example.test/case-001"

        self.assertEqual(adapt_case_results([result])[0]["source"], "https://example.test/case-001")

    def test_rejects_non_positive_position(self):
        with self.assertRaises(ValueError):
            adapt_case_result(self._result("case-001", "案例"), 0)


if __name__ == "__main__":
    unittest.main()
