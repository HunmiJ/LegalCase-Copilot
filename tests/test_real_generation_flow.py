from __future__ import annotations

import json
import unittest

from backend.rag.context_builder import build_context
from backend.rag.generator import GroundedGenerator


class FakeRealProvider:
    name = "real_llm"
    model = "test-real-provider"

    def __init__(self, payload):
        self.payload = payload
        self.messages = []

    def complete_with_metadata(self, messages, response_format=None, temperature=0):
        self.messages.append(messages)
        return {
            "content": json.dumps(self.payload, ensure_ascii=False),
            "finish_reason": "stop",
            "response_structure_type": "str",
            "http_api_success": True,
        }


class FailingRealProvider:
    name = "real_llm"
    model = "test-real-provider"

    def complete_with_metadata(self, messages, response_format=None, temperature=0):
        raise OSError("network unavailable")


class RealGenerationFlowTest(unittest.TestCase):
    def setUp(self):
        self.context = build_context(law_items=[{
            "id": "law-real-1",
            "law_name": "劳动合同法",
            "article_number": "第四十八条",
            "article_content": "违法解除劳动合同的，应当依照规定承担责任。",
            "source_file": "law.docx",
        }])

    def test_real_provider_response_is_parsed_into_complete_structured_output(self):
        provider = FakeRealProvider({
            "answer": "是否需要赔偿取决于解除理由、程序和证据。",
            "legal_basis": [{"citation": "LAW-1", "content": "模型返回的法规摘要"}],
            "related_cases": [],
            "risk_note": "需要核对解除事实和证据。",
            "confidence": "medium",
        })

        response, meta = GroundedGenerator(provider, max_retries=0).generate(
            "公司无故辞退员工需要赔偿吗？", self.context
        )

        self.assertEqual(response["generation_status"], "success")
        self.assertEqual(
            {"answer", "legal_basis", "related_cases", "risk_note", "confidence"} <= response.keys(),
            True,
        )
        self.assertEqual(response["answer"], "是否需要赔偿取决于解除理由、程序和证据。")
        self.assertEqual(response["legal_basis"][0]["citation"], "LAW-1")
        self.assertEqual(meta["validation"]["valid"], True)
        self.assertEqual(provider.messages[0][0]["role"], "system")

    def test_provider_failure_is_diagnosed_and_not_reported_as_success(self):
        response, meta = GroundedGenerator(FailingRealProvider(), max_retries=0).generate(
            "公司无故辞退员工需要赔偿吗？", self.context
        )

        self.assertNotEqual(response["generation_status"], "success")
        self.assertTrue(meta["fallback"])
        attempt = meta["attempts"][0]
        self.assertEqual(attempt["provider_error_type"], "OSError")
        self.assertEqual(attempt["error_detail"], "network unavailable")

    def test_json_code_fence_from_provider_is_supported(self):
        provider = FakeRealProvider({
            "answer": "需要结合解除理由判断。",
            "legal_basis": [{"citation": "[LAW-1]", "content": "法规依据"}],
            "related_cases": [],
            "risk_note": "请补充证据。",
            "confidence": "low",
        })
        original = provider.complete_with_metadata

        def fenced(messages, response_format=None, temperature=0):
            result = original(messages, response_format, temperature)
            result["content"] = "\x60\x60\x60json\n" + result["content"] + "\n\x60\x60\x60"
            return result

        provider.complete_with_metadata = fenced
        response, _ = GroundedGenerator(provider, max_retries=0).generate(
            "公司无故辞退员工需要赔偿吗？", self.context
        )
        self.assertEqual(response["generation_status"], "success")
        self.assertEqual(response["legal_basis"][0]["citation"], "LAW-1")


if __name__ == "__main__":
    unittest.main()
