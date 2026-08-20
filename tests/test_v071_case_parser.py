from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.cases.parser import parse_case_pdf
from backend.cases.schemas import CaseRecord, detect_duplicate_case_ids
from scripts.parse_cases import load_source_urls


RAW_DIR = ROOT / "data/raw/cases"
JSONL_PATH = ROOT / "data/processed/cases/cases.jsonl"


class V071CaseParserTest(unittest.TestCase):
    def test_all_case_pdfs_are_discovered_and_readable(self):
        pdfs = sorted(RAW_DIR.glob("*.pdf"))
        self.assertEqual(len(pdfs), 20)
        for path in pdfs:
            record, page_count = parse_case_pdf(path)
            self.assertGreater(page_count, 0)
            self.assertTrue(record.raw_text)

    def test_parser_generates_main_records_and_schema_validates(self):
        rows = [json.loads(line) for line in JSONL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 19)
        records = [CaseRecord.from_dict(row) for row in rows]
        self.assertEqual(len({record.case_id for record in records}), 19)
        self.assertEqual(detect_duplicate_case_ids(records), [])
        for record in records:
            self.assertTrue(record.title)
            self.assertTrue(record.raw_text)
            self.assertTrue((ROOT / record.source_file).is_file())

    def test_case_ids_are_stable_across_repeated_parsing(self):
        pdfs = sorted(RAW_DIR.glob("*.pdf"))
        first = [parse_case_pdf(path)[0].case_id for path in pdfs]
        second = [parse_case_pdf(path)[0].case_id for path in pdfs]
        self.assertEqual(first, second)

    def test_original_pdfs_are_unchanged_by_parser(self):
        before = {path: path.read_bytes() for path in RAW_DIR.glob("*.pdf")}
        for path in sorted(before):
            parse_case_pdf(path)
        after = {path: path.read_bytes() for path in RAW_DIR.glob("*.pdf")}
        self.assertEqual(before, after)

    def test_parser_preserves_official_extended_fields(self):
        rows = [json.loads(line) for line in JSONL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(all(row.get("database_case_number") for row in rows))
        self.assertTrue(all(row.get("case_gist") for row in rows))
        self.assertTrue(all(row.get("related_index") for row in rows[:3]))
        by_file = {row["source_file"].removeprefix("data/raw/cases/"): row for row in rows}
        urls = load_source_urls()
        for filename, row in by_file.items():
            self.assertEqual(row["source_url"], urls[filename])

    def test_formal_law_products_and_frozen_benchmark_are_clean(self):
        protected = ["data/raw/laws", "data/processed/legal.db", "data/processed/laws.jsonl", "data/processed/embeddings.npy", "data/processed/embedding_index.json", "evaluation/retrieval_queries.json"]
        for path in protected:
            self.assertEqual(subprocess.run(["git", "diff", "--quiet", "--", path]).returncode, 0, path)


if __name__ == "__main__":
    unittest.main()
