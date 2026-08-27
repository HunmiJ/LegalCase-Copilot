from __future__ import annotations

import json
import unittest

from backend.cases.search.models import CaseSearchResult
from backend.rag.context_builder import build_context
from backend.rag.generator import GroundedGenerator, EVIDENCE_INSUFFICIENT_MESSAGE


class EnhancedProvider:
    def __init__(self, citation="LAW-1"):
        self.citation = citation

    def complete(self, messages, response_format=None, temperature=0):
        return json.dumps({
            "answer": "现有证据显示该问题需要结合具体事实判断。",
            "legal_basis": [{"citation": self.citation, "content": "模型提供的内容将由程序按 citation 回填。"}],
            "related_cases": [], "risk_note": "不构成确定性法律意见。", "confidence": "medium",
        }, ensure_ascii=False)


class CaseProvider:
    def complete(self, messages, response_format=None, temperature=0):
        return json.dumps({
            "answer": "该案例只能作为相似事实参考。",
            "legal_basis": [{"citation": "LAW-1", "content": "法规依据"}],
            "related_cases": [{"citation": "CASE-1", "title": "模型标题", "reasoning": "模型理由"}],
            "risk_note": "需要核对全部事实。", "confidence": "low",
        }, ensure_ascii=False)


class RAGSafetyTest(unittest.TestCase):
    def setUp(self):
        self.law = {"id": "law-1", "law_name": "劳动合同法", "article_number": "第三十九条",
                    "article_content": "用人单位可以解除劳动合同。", "source_file": "law.docx"}
        case = CaseSearchResult(case_id="case-1", title="违法解除案", basic_facts="解除劳动合同",
                                dispute_focus="违法解除", judgment_result="支持赔偿请求",
                                source_file="case.pdf", source_name="人民法院案例库")
        self.law_context = build_context(law_items=[self.law])
        self.case_context = build_context(law_items=[self.law], case_items=[{
            "citation_id": "CASE-1", "type": "case", "case_id": case.case_id,
            "title": case.title, "court": "", "date": "", "facts": case.basic_facts,
            "legal_issue": case.dispute_focus, "judgment": case.judgment_result, "source": case.source_file,
        }])

    def test_normal_labor_question_returns_enhanced_structure(self):
        response, meta = GroundedGenerator(EnhancedProvider()).generate("违法解除劳动合同怎么办？", self.law_context)
        self.assertEqual(response["generation_status"], "success")
        self.assertTrue({"answer", "legal_basis", "related_cases", "risk_note", "confidence"} <= response.keys())
        self.assertEqual(response["legal_basis"][0]["citation"], "LAW-1")
        self.assertEqual(meta["validation"]["citation_validity"], 1.0)

    def test_empty_context_refuses(self):
        response, _ = GroundedGenerator(EnhancedProvider()).generate("违法解除劳动合同怎么办？", {})
        self.assertEqual(response["answer"], EVIDENCE_INSUFFICIENT_MESSAGE)
        self.assertEqual(response["generation_status"], "evidence_insufficient")

    def test_non_labor_question_refuses(self):
        response, _ = GroundedGenerator(EnhancedProvider()).generate("今天天气怎么样？", self.law_context)
        self.assertEqual(response["answer"], EVIDENCE_INSUFFICIENT_MESSAGE)

    def test_unsupported_citation_refuses(self):
        response, meta = GroundedGenerator(EnhancedProvider("LAW-99"), max_retries=0).generate("违法解除劳动合同怎么办？", self.law_context)
        self.assertEqual(response["generation_status"], "evidence_insufficient")
        self.assertEqual(response["answer"], EVIDENCE_INSUFFICIENT_MESSAGE)
        self.assertGreaterEqual(meta["validation"]["unsupported_citation_rate"], 0.0)

    def test_case_citation_is_materialized_from_context(self):
        response, meta = GroundedGenerator(CaseProvider()).generate("违法解除劳动合同的类似案例？", self.case_context)
        self.assertEqual(response["generation_status"], "success")
        self.assertEqual(response["related_cases"][0]["citation"], "CASE-1")
        self.assertEqual(response["related_cases"][0]["title"], "违法解除案")
        self.assertEqual(meta["validation"]["citation_validity"], 1.0)


if __name__ == "__main__":
    unittest.main()
