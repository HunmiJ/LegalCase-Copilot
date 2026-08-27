from __future__ import annotations

import unittest

from backend.rag.citation_validator import validate_citations
from backend.rag.context_builder import build_context
from backend.rag.generator import normalize_citation_format


def _context(include_case: bool = True):
    cases = [{
        "citation_id": "CASE-1", "type": "case", "case_id": "c1",
        "title": "解除劳动合同案", "facts": "解除争议",
        "legal_issue": "违法解除", "judgment": "依法审查",
    }] if include_case else []
    return build_context(law_items=[{
        "id": "law-1", "law_name": "劳动合同法", "article_number": "第四十八条",
        "article_content": "违法解除劳动合同的，应当承担责任。", "source_file": "law.jsonl",
    }], case_items=cases)


def _response(citations):
    return normalize_citation_format({
        "answer": "需要结合事实判断。",
        "legal_basis": [{"citation": citations[0], "content": "法规依据"}] if citations else [],
        "related_cases": ([{"citation": citations[1], "title": "解除劳动合同案", "reasoning": "类案参考"}]
                          if len(citations) > 1 else []),
        "risk_note": "请核对事实和证据。", "confidence": "medium",
    })


class CitationNamespaceTest(unittest.TestCase):
    def test_valid_law_citation_passes(self):
        result = validate_citations(_response(["LAW-1"]), _context())
        self.assertTrue(result["valid"])

    def test_valid_case_citation_passes(self):
        result = validate_citations(_response(["LAW-1", "CASE-1"]), _context())
        self.assertTrue(result["valid"])

    def test_bracketed_namespaced_citations_are_safely_normalized(self):
        response = _response(["[LAW-1]", "[CASE-1]"])
        self.assertEqual(response["legal_analysis"][0]["citations"], ["LAW-1"])
        self.assertEqual(response["legal_analysis"][1]["citations"], ["CASE-1"])
        self.assertTrue(validate_citations(response, _context())["valid"])

    def test_unknown_law_citation_is_rejected(self):
        result = validate_citations(_response(["LAW-99"]), _context())
        self.assertFalse(result["valid"])
        self.assertIn("unsupported citation: LAW-99", result["errors"])

    def test_unknown_case_citation_is_rejected(self):
        result = validate_citations(_response(["LAW-1", "CASE-99"]), _context())
        self.assertFalse(result["valid"])
        self.assertIn("unsupported citation: CASE-99", result["errors"])

    def test_law_only_context_has_no_case_namespace_dependency(self):
        context = _context(include_case=False)
        result = validate_citations(_response(["LAW-1"]), context)
        self.assertTrue(result["valid"])
        self.assertNotIn("CASE-1", {item["citation_id"] for item in context["items"]})


if __name__ == "__main__":
    unittest.main()
