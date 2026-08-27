from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.cases.schemas import CaseRecord, CaseValidationError, detect_duplicate_case_ids
from scripts.inspect_cases import inspect_cases


def valid_case(**overrides):
    value = {
        "case_id": "case-001", "title": "劳动争议示例标题", "case_type": "参考案例",
        "source_name": "人民法院案例库", "source_file": "case-001.txt", "raw_text": "原始案例正文",
        "source_url": None, "keywords": [], "legal_basis": [],
    }
    value.update(overrides)
    return value


class V07CaseBootstrapTest(unittest.TestCase):
    def test_case_schema_can_create_and_nullable_fields_are_allowed(self):
        record = CaseRecord.from_dict(valid_case())
        self.assertEqual(record.case_id, "case-001")
        self.assertIsNone(record.source_url)

    def test_missing_required_field_fails_validation(self):
        value = valid_case()
        del value["raw_text"]
        with self.assertRaises(CaseValidationError):
            CaseRecord.from_dict(value)

    def test_duplicate_case_ids_are_detected(self):
        records = [CaseRecord.from_dict(valid_case()), CaseRecord.from_dict(valid_case(title="另一个标题"))]
        self.assertEqual(detect_duplicate_case_ids(records), ["case-001"])

    def test_empty_case_corpus_inspector_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "raw"
            raw.mkdir()
            metadata = Path(directory) / "case_metadata.json"
            metadata.write_text("[]", encoding="utf-8")
            report = inspect_cases(raw, metadata)
        self.assertEqual(report["case_file_count"], 0)
        self.assertEqual(report["metadata_count"], 0)
        self.assertEqual(report["duplicate_case_ids"], [])

    def test_inspector_cli_handles_empty_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "raw"
            raw.mkdir()
            metadata = Path(directory) / "case_metadata.json"
            metadata.write_text("[]", encoding="utf-8")
            completed = subprocess.run([sys.executable, str(ROOT / "scripts/inspect_cases.py"), "--raw-dir", str(raw), "--metadata", str(metadata)], capture_output=True, text=True, check=True)
            report = json.loads(completed.stdout)
        self.assertEqual(report["case_file_count"], 0)

    def test_laws_and_formal_products_are_read_only(self):
        protected = ["data/processed/legal.db", "data/processed/laws.jsonl", "data/processed/embeddings.npy", "data/processed/embedding_index.json"]
        for path in protected:
            self.assertEqual(subprocess.run(["git", "diff", "--quiet", "--", path]).returncode, 0, path)


if __name__ == "__main__":
    unittest.main()
