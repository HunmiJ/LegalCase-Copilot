from __future__ import annotations

import unittest

from frontend_demo.app import normalize_result, presentation_status, run_query


class FakePipeline:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def ask(self, query):
        self.calls.append(query)
        return self.response


class DemoIntegrationTest(unittest.TestCase):
    def test_pipeline_can_be_called_and_fields_are_complete(self):
        pipeline = FakePipeline({
            "response": {
                "answer": "需要结合事实判断。",
                "legal_basis": [{"citation": "LAW-1", "content": "劳动合同法相关规定"}],
                "related_cases": [{"citation": "CASE-1", "title": "相关案例", "reasoning": "仅作类案参考"}],
                "risk_note": "不构成法律意见。",
                "confidence": "medium",
            },
            "context": {},
        })

        result = run_query(pipeline, "违法解除劳动合同怎么办？")

        self.assertEqual(pipeline.calls, ["违法解除劳动合同怎么办？"])
        self.assertEqual(
            set(result),
            {"answer", "legal_analysis", "legal_basis", "related_cases", "risk_note", "confidence",
             "generation_status", "generation_failed", "generation_meta"},
        )
        self.assertEqual(result["legal_basis"][0]["citation"], "LAW-1")
        self.assertEqual(result["related_cases"][0]["citation"], "CASE-1")

    def test_missing_citations_are_rendered_as_empty_lists(self):
        pipeline = FakePipeline({
            "response": {
                "answer": "无法基于当前法律数据库提供可靠回答。",
                "risk_note": "证据不足。",
                "confidence": "low",
            },
            "context": {},
        })

        result = run_query(pipeline, "无法核验的问题？")

        self.assertEqual(result["legal_basis"], [])
        self.assertEqual(result["related_cases"], [])
        self.assertEqual(result["confidence"], "low")

    def test_empty_query_is_handled_without_calling_pipeline(self):
        pipeline = FakePipeline({})

        result = run_query(pipeline, "   ")

        self.assertEqual(pipeline.calls, [])
        self.assertEqual(result["legal_basis"], [])
        self.assertEqual(result["related_cases"], [])
        self.assertEqual(result["confidence"], "low")

    def test_legacy_pipeline_response_is_normalized(self):
        result = normalize_result({
            "response": {
                "issue_summary": ["旧版回答"],
                "relevant_laws": [{"citation": "[1]", "text": "法规正文"}],
                "disclaimer": "旧版风险提示",
            },
            "context": {"case_items": []},
        })

        self.assertEqual(result["answer"], "旧版回答")
        self.assertEqual(result["legal_basis"][0]["citation"], "[1]")
        self.assertEqual(result["risk_note"], "旧版风险提示")

    def test_retrieval_only_result_is_not_presented_as_ai_success(self):
        result = normalize_result({
            "response": {
                "answer": "生成模型未能在有限重试内完成可靠的结构化回答。",
                "generation_status": "retrieval_only",
                "legal_basis": [{"citation": "LAW-1", "content": "已检索法规"}],
                "related_cases": [{"citation": "CASE-1", "title": "已检索案例"}],
                "risk_note": "生成失败。",
                "confidence": "low",
            },
            "context": {},
            "generation_meta": {"fallback": True},
        })

        self.assertEqual(result["answer"], "AI总结生成暂时不可用。")
        self.assertEqual(result["legal_basis"][0]["citation"], "LAW-1")
        self.assertEqual(result["related_cases"][0]["citation"], "CASE-1")
        self.assertIn("以上为检索结果，不代表AI生成结论。", result["risk_note"])

    def test_normalized_result_preserves_analysis_and_citation_metadata(self):
        result = normalize_result({
            "response": {
                "answer": "需要结合解除理由和证据判断。",
                "legal_analysis": "该问题需要核对解除理由及程序证据。",
                "legal_basis": [{
                    "citation": "LAW-1", "law_name": "劳动合同法",
                    "article_number": "第八十七条", "text": "违法解除的赔偿规定。",
                    "source": "法规数据库",
                }],
                "related_cases": [{
                    "citation": "CASE-1", "case_id": "case-001",
                    "title": "某公司劳动争议判决书", "court": "某市人民法院",
                    "judgment_date": "2024-01-01", "dispute_focus": "违法解除",
                    "judgment_summary": "法院围绕解除理由进行审查。",
                    "legal_basis": ["劳动合同法第八十七条"],
                }],
                "risk_note": "需要结合完整事实。", "confidence": "medium",
            },
            "context": {},
        })

        self.assertEqual(result["legal_analysis"], "该问题需要核对解除理由及程序证据。")
        self.assertEqual(result["legal_basis"][0]["law_name"], "劳动合同法")
        self.assertEqual(result["legal_basis"][0]["article_number"], "第八十七条")
        self.assertEqual(result["related_cases"][0]["court"], "某市人民法院")
        self.assertEqual(result["related_cases"][0]["dispute_focus"], "违法解除")

    def test_presentation_status_distinguishes_mock_and_retrieval_only(self):
        status = presentation_status(
            {"generation_status": "retrieval_only", "generation_failed": True},
            provider_name="mock",
            mode="law_and_cases",
        )

        self.assertEqual(status["provider_label"], "Mock 演示模式")
        self.assertEqual(status["mode_label"], "法规 + 类案增强")
        self.assertEqual(status["generation_label"], "Retrieval-only")
        self.assertIn("不代表真实 AI 生成结果", status["provider_note"])

    def test_presentation_status_does_not_call_domain_guard_mock_output(self):
        status = presentation_status(
            {"generation_status": "out_of_domain", "generation_failed": False},
            provider_name="mock",
            mode="law_only",
        )

        self.assertEqual(status["generation_label"], "未生成 AI 结论")

    def test_fallback_law_citation_is_enriched_from_retrieval_context(self):
        result = normalize_result({
            "response": {
                "generation_status": "retrieval_only",
                "legal_basis": [{"citation": "LAW-1", "content": "已检索法规正文"}],
            },
            "context": {"items": [{
                "citation_id": "LAW-1", "law_name": "劳动合同法",
                "article_number": "第八十七条", "article_content": "已检索法规正文",
                "source": "法规数据库",
            }]},
            "generation_meta": {"fallback": True},
        })

        self.assertEqual(result["legal_basis"][0]["law_name"], "劳动合同法")
        self.assertEqual(result["legal_basis"][0]["article_number"], "第八十七条")


if __name__ == "__main__":
    unittest.main()
