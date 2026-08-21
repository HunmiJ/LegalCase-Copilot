from __future__ import annotations

import unittest

from evaluate_runtime_cases import evaluate_records


class RuntimeCorpusQualityTest(unittest.TestCase):
    def test_complete_record_is_valid(self):
        record = {
            "case_id": "2024-18-2-490-002", "title": "劳动争议案", "source_file": "data/runtime/cases/raw/a.pdf", "raw_text": "案情",
            "basic_facts": "事实", "dispute_focus": "争点", "court_reasoning": "理由", "judgment_result": "结果",
            "legal_basis": ["劳动合同法"], "keywords": ["劳动争议"],
        }
        report = evaluate_records([record])
        self.assertEqual(report["total_cases"], 1)
        self.assertEqual(report["valid_cases"], 1)
        self.assertEqual(report["field_completion_rate"]["keywords"], 1.0)
        self.assertEqual(report["cases"][0]["issues"], [])

    def test_missing_required_and_quality_fields_are_reported(self):
        report = evaluate_records([{"case_id": "case-1", "title": "案例", "source_file": "a.pdf", "raw_text": "文本", "keywords": []}])
        self.assertEqual(report["valid_cases"], 0)
        self.assertEqual(report["missing_fields"]["basic_facts"], 1)
        self.assertEqual(report["missing_fields"]["keywords"], 1)
        self.assertIn("missing_or_empty:legal_basis", report["cases"][0]["issues"])


if __name__ == "__main__":
    unittest.main()
