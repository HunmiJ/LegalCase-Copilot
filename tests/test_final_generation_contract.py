import json
import unittest

from backend.rag.context_builder import build_context
from backend.rag.generator import GroundedGenerator, materialize_legal_basis, materialize_related_cases


class _Provider:
    name = "test"
    model = "test"

    def __init__(self, payload):
        self.payload = payload

    def complete_with_metadata(self, messages, response_format=None, temperature=0):
        return {"content": json.dumps(self.payload, ensure_ascii=False),
                "http_api_success": True, "finish_reason": "stop"}


def _context(include_case=True):
    cases = [{
        "citation_id": "CASE-1", "type": "case", "case_id": "c-1",
        "title": "劳动合同解除争议案", "court": "某市中级人民法院",
        "date": "2024-01-02", "dispute_focus": "违法解除",
        "basic_facts": "员工主张解除程序违法。", "judgment_result": "法院结合证据审查解除是否合法。",
        "legal_basis": ["劳动合同法"], "source": "full_cases/cases.jsonl",
    }] if include_case else []
    return build_context(
        law_items=[{"law_name": "劳动合同法", "article_number": "第四十七条",
                    "article_content": "经济补偿按工作年限计算。", "source_file": "laws.jsonl"}],
        case_items=cases, max_articles=3, max_cases=2, max_chars=3500,
    )


class FinalGenerationContractTests(unittest.TestCase):
    def _payload(self, law=True, case=False, claim=None):
        citations = (["LAW-1"] if law else []) + (["CASE-1"] if case else [])
        return {
            "answer": "应结合解除原因、程序和证据判断。",
            "legal_analysis": claim or "相关法律依据需要结合事实核验。",
            "law_citations": ["LAW-1"] if law else [],
            "case_citations": ["CASE-1"] if case else [],
            "risk_note": "事实和证据不足时不能作确定结论。",
            "confidence": 0.6,
        }

    def test_valid_law_and_case_ids_and_metadata_are_deterministic(self):
        result, meta = GroundedGenerator(_Provider(self._payload(case=True)), max_retries=0).generate("违法解除怎么办", _context())
        self.assertEqual(result["generation_status"], "success")
        self.assertEqual(result["legal_basis"][0]["law_name"], "劳动合同法")
        self.assertEqual(result["legal_basis"][0]["article_number"], "第四十七条")
        self.assertEqual(result["related_cases"][0]["title"], "劳动合同解除争议案")
        self.assertEqual(result["related_cases"][0]["court"], "某市中级人民法院")
        self.assertEqual(meta["sanitation_events"], [])

    def test_unknown_ids_are_rejected_without_metadata(self):
        payload = self._payload()
        payload["law_citations"] = ["LAW-99"]
        payload["legal_analysis"] = "相关法律依据需要结合事实核验。"
        result, _ = GroundedGenerator(_Provider(payload), max_retries=0).generate("劳动争议", _context(False))
        self.assertNotEqual(result.get("generation_status"), "success")
        self.assertNotIn("LAW-99", {item.get("citation") for item in result.get("legal_basis", [])})

    def test_list_of_strings_is_safely_normalized(self):
        payload = self._payload()
        payload["legal_analysis"] = ["分析A", "分析B"]
        result, meta = GroundedGenerator(_Provider(payload), max_retries=0).generate("劳动争议", _context(False))
        self.assertEqual(result["generation_status"], "success")
        self.assertEqual(result["legal_analysis"], "分析A\n分析B")
        self.assertEqual(meta["normalization_count"], 1)

    def test_single_analysis_object_is_safely_normalized(self):
        payload = self._payload()
        payload["legal_analysis"] = {"analysis": "单一分析"}
        result, meta = GroundedGenerator(_Provider(payload), max_retries=0).generate("劳动争议", _context(False))
        self.assertEqual(result["generation_status"], "success")
        self.assertEqual(result["legal_analysis"], "单一分析")
        self.assertEqual(meta["normalization_count"], 1)

    def test_ambiguous_nested_analysis_and_missing_analysis_are_rejected(self):
        for value in ({"analysis": "A", "extra": "B"}, None):
            payload = self._payload()
            if value is None:
                payload.pop("legal_analysis")
            else:
                payload["legal_analysis"] = value
            result, _ = GroundedGenerator(_Provider(payload), max_retries=0).generate("劳动争议", _context(False))
            self.assertNotEqual(result.get("generation_status"), "success")

    def test_invalid_case_id_is_rejected_and_law_only_allows_empty_cases(self):
        payload = self._payload(case=False)
        result, _ = GroundedGenerator(_Provider(payload), max_retries=0).generate("劳动争议", _context(False))
        self.assertEqual(result["generation_status"], "success")
        self.assertEqual(result["related_cases"], [])
        payload = self._payload(law=True, case=True)
        payload["case_citations"] = ["CASE-99"]
        result, _ = GroundedGenerator(_Provider(payload), max_retries=0).generate("劳动争议", _context())
        self.assertNotEqual(result.get("generation_status"), "success")

    def test_canonical_contract_does_not_require_metadata_from_model(self):
        payload = self._payload()
        self.assertNotIn("law_name", payload)
        self.assertNotIn("article_number", payload)
        self.assertNotIn("title", payload)

    def test_unsupported_article_is_sanitized_but_does_not_create_citation(self):
        payload = self._payload(claim="依据劳动合同法第八十七条，应结合事实判断。")
        result, meta = GroundedGenerator(_Provider(payload), max_retries=0).generate("违法解除怎么办", _context(False))
        self.assertEqual(result["generation_status"], "success")
        self.assertIn("相关法律规定", result["legal_analysis"])
        self.assertNotIn("第八十七条", result["legal_analysis"])
        self.assertEqual(result["legal_basis"][0]["citation"], "LAW-1")
        self.assertEqual(len(meta["sanitation_events"]), 1)

    def test_unsafe_article_range_is_rejected(self):
        payload = self._payload(claim="适用第八十七条至第八十八条。")
        result, _ = GroundedGenerator(_Provider(payload), max_retries=0).generate("违法解除怎么办", _context(False))
        self.assertNotEqual(result.get("generation_status"), "success")

    def test_unreferenced_sources_are_not_rendered(self):
        payload = self._payload(law=True, case=False)
        result, _ = GroundedGenerator(_Provider(payload), max_retries=0).generate("劳动争议", _context(True))
        self.assertEqual([item["citation"] for item in result["legal_basis"]], ["LAW-1"])
        self.assertEqual(result["related_cases"], [])
        self.assertEqual(materialize_related_cases(result, _context(True)), [])


if __name__ == "__main__":
    unittest.main()
