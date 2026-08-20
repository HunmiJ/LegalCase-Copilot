from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/cases"


class V074Phase8PromotionTest(unittest.TestCase):
    def test_collection_status_distinguishes_not_found_and_pending_retry(self):
        with (RAW / "case_collection_plan.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = {row["planned_number"]: row for row in csv.DictReader(handle)}
        for number in ("010", "018", "021"):
            self.assertEqual(rows[number]["status"], "not_found")
            self.assertFalse(rows[number]["filename"])
        for number in ("022", "023"):
            self.assertEqual(rows[number]["status"], "downloaded")
            self.assertTrue(rows[number]["filename"])

    def test_new_cases_are_promoted_with_actual_topics(self):
        metadata = json.loads((ROOT / "data/case_metadata.json").read_text(encoding="utf-8"))
        by_file = {Path(item["source_file"]).name: item for item in metadata}
        expected = {
            "019_孟某诉天津某云商有限公司劳动争议案.pdf": "不定时工时制未实际履行与休息日加班费",
            "020_上海某品牌管理有限公司诉姚某劳动合同纠纷案.pdf": "异地调岗、工作地点变更与违法解除",
        }
        for filename, topic in expected.items():
            self.assertEqual(by_file[filename]["corpus_status"], "ELIGIBLE_MAIN_CORPUS")
            self.assertEqual(by_file[filename]["actual_topic"], topic)
        rows = [json.loads(line) for line in (ROOT / "data/processed/cases/cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 19)
        self.assertIn("2024-07-2-490-009", {row["case_id"] for row in rows})
        self.assertIn("2023-07-2-186-011", {row["case_id"] for row in rows})

    def test_new_case_provenance_is_official_and_pdf_has_text_layer(self):
        with (RAW / "source_urls.csv").open(encoding="utf-8-sig", newline="") as handle:
            urls = {row["filename"]: row["source_url"] for row in csv.DictReader(handle)}
        from pypdf import PdfReader
        for path in list(RAW.glob("019_*.pdf")) + list(RAW.glob("020_*.pdf")):
            self.assertTrue(urls[path.name].startswith("https://rmfyalk.court.gov.cn/"))
            self.assertTrue(any((page.extract_text() or "").strip() for page in PdfReader(str(path)).pages))


if __name__ == "__main__":
    unittest.main()
