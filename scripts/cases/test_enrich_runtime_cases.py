from __future__ import annotations

import unittest

from enrich_runtime_cases import enrich_records


class RuntimeCaseEnrichmentTest(unittest.TestCase):
    def test_missing_focus_is_derived_from_existing_fields(self):
        records, count = enrich_records([{
            "case_id": "case-1", "title": "某公司违法解除劳动合同案", "keywords": ["劳动争议"],
            "basic_facts": "公司解除劳动合同", "judgment_result": "解除违法", "raw_text": "完整文本",
            "dispute_focus": None,
        }])
        self.assertEqual(count, 1)
        self.assertEqual(records[0]["dispute_focus"], "违法解除")

    def test_existing_focus_is_not_overwritten(self):
        records, count = enrich_records([{"case_id": "case-2", "title": "案例", "dispute_focus": "原有争点"}])
        self.assertEqual(count, 0)
        self.assertEqual(records[0]["dispute_focus"], "原有争点")


if __name__ == "__main__":
    unittest.main()
