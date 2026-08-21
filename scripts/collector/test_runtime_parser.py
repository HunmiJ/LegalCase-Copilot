from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.cases.schemas import CaseRecord
from scripts.collector.runtime_parser import parse_runtime_cases


class RuntimeParserTest(unittest.TestCase):
    def test_parses_one_collected_runtime_pdf_without_touching_frozen_corpus(self):
        raw_pdf = next((ROOT / "data/runtime/cases/raw").glob("*.pdf"), None)
        if raw_pdf is None:
            self.skipTest("no collected runtime PDF available")
        before = (ROOT / "data/processed/cases/cases.jsonl").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = parse_runtime_cases(ROOT / "data/runtime/cases/raw", output, ROOT / "data/runtime/cases/case_manifest.json")
            self.assertGreaterEqual(result["parsed"], 1)
            records = [CaseRecord.from_dict(json.loads(line)) for line in (output / "runtime_cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertTrue(records[0].case_id)
            self.assertTrue(records[0].raw_text)
            self.assertTrue((output / "case_metadata.json").exists())
        self.assertEqual(before, (ROOT / "data/processed/cases/cases.jsonl").read_bytes())


if __name__ == "__main__":
    unittest.main()
