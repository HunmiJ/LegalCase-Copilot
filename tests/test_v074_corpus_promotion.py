from __future__ import annotations

import csv
import json
import subprocess
import unittest
from pathlib import Path

from backend.cases.schemas import CaseRecord


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/cases"
CORPUS = ROOT / "data/processed/cases/cases.jsonl"


class V074CorpusPromotionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]
        with (RAW / "source_urls.csv").open(encoding="utf-8-sig", newline="") as handle:
            cls.urls = {row["filename"]: row["source_url"] for row in csv.DictReader(handle)}

    def test_all_pdfs_and_main_records_are_present(self):
        self.assertEqual(len(list(RAW.glob("*.pdf"))), 18)
        self.assertEqual(len(self.rows), 17)

    def test_main_records_validate_and_have_unique_official_ids(self):
        records = [CaseRecord.from_dict(row) for row in self.rows]
        self.assertEqual(len({record.case_id for record in records}), 17)
        self.assertEqual(len({record.database_case_number for record in records}), 17)
        for record in records:
            self.assertEqual(record.source_name, "人民法院案例库")
            self.assertTrue(record.source_url.startswith("https://rmfyalk.court.gov.cn/"))
            self.assertTrue((ROOT / record.source_file).is_file())
            self.assertEqual(record.source_url, self.urls[Path(record.source_file).name])

    def test_parser_regression_fields_are_not_cross_section_merged(self):
        by_id = {row["database_case_number"]: row for row in self.rows}
        self.assertTrue(by_id["2022-18-2-186-001"]["title"].endswith("确认劳动关系案"))
        self.assertEqual(by_id["2022-18-2-186-001"]["keywords"], ["民事", "确认劳动关系", "合作经营", "书面劳动合同"])
        self.assertTrue(by_id["2024-18-2-186-001"]["title"].endswith("确认劳动关系纠纷案"))
        self.assertTrue(by_id["2024-18-2-186-002"]["title"].endswith("确认劳动关系纠纷案"))
        for row in (by_id["2022-18-2-186-001"], by_id["2024-18-2-186-001"], by_id["2024-18-2-186-002"]):
            self.assertTrue(row["case_gist"])
            self.assertTrue(row["judgment_result"])

    def test_original_pdfs_are_unchanged(self):
        result = subprocess.run(["git", "diff", "--name-only", "--", "data/raw/cases"], cwd=ROOT, capture_output=True, text=True)
        self.assertNotIn(".pdf", result.stdout)

    def test_auxiliary_case_is_audited_but_excluded_from_main_corpus(self):
        metadata = json.loads((ROOT / "data/case_metadata.json").read_text(encoding="utf-8"))
        auxiliary = [item for item in metadata if item["corpus_status"] == "AUXILIARY_ONLY"]
        self.assertEqual(len(auxiliary), 1)
        self.assertEqual(auxiliary[0]["database_case_number"], "2014-18-1-232-001")
        self.assertNotIn(auxiliary[0]["database_case_number"], {row["database_case_number"] for row in self.rows})

    def test_eligibility_metadata_has_all_audited_pdfs(self):
        eligibility = json.loads((ROOT / "data/case_eligibility.json").read_text(encoding="utf-8"))
        self.assertEqual(len(eligibility), 18)
        self.assertEqual({item["corpus_status"] for item in eligibility}, {"ELIGIBLE_MAIN_CORPUS", "AUXILIARY_ONLY"})
