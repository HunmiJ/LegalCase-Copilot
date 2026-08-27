from __future__ import annotations

import unittest

from backend.rag.context_builder import build_context
from backend.rag.generator import _allowed_context_guide, materialize_legal_basis, materialize_related_cases


class GenerationContractTest(unittest.TestCase):
    def setUp(self):
        self.context = build_context(
            law_items=[{"id": "l1", "law_name": "劳动合同法", "article_number": "第四十七条",
                        "article_content": "经济补偿依据。", "source_file": "laws.jsonl"}],
            case_items=[{"citation_id": "CASE-1", "type": "case", "case_id": "c1",
                         "title": "解除案", "court": "法院", "date": "2024-01-01",
                         "dispute_focus": "解除", "judgment_result": "类案结果"}],
        )

    def test_allowlist_contains_only_context_citations_and_articles(self):
        guide = _allowed_context_guide(self.context)
        self.assertIn("LAW-1", guide)
        self.assertIn("CASE-1", guide)
        self.assertIn("劳动合同法第四十七条", guide)
        self.assertIn("不在允许列表的条号必须省略", guide)

    def test_context_article_is_allowed_but_unknown_article_is_not_added(self):
        guide = _allowed_context_guide(self.context)
        self.assertIn("第四十七条", guide)
        self.assertNotIn("第八十七条", guide)

    def test_metadata_is_materialized_only_for_existing_citations(self):
        response = {"legal_analysis": [{"citations": ["LAW-1", "LAW-99", "CASE-1"]}]}
        legal_basis = materialize_legal_basis(response, self.context)
        related_cases = materialize_related_cases(response, self.context)
        self.assertEqual([item["citation"] for item in legal_basis], ["LAW-1"])
        self.assertEqual([item["citation"] for item in related_cases], ["CASE-1"])
        self.assertNotIn("LAW-99", {item["citation"] for item in legal_basis})


if __name__ == "__main__":
    unittest.main()
