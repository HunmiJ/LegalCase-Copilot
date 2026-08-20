from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.parse_cases import load_source_urls, parse_all


ROOT = Path(__file__).resolve().parents[1]
RAW_CASES = ROOT / "data/raw/cases"
JSONL = ROOT / "data/processed/cases/cases.jsonl"


class V072ProvenanceTest(unittest.TestCase):
    def test_source_urls_match_pdf_filenames(self):
        urls = load_source_urls()
        self.assertEqual(set(urls), {path.name for path in RAW_CASES.glob("*.pdf")})
        for url in urls.values():
            self.assertTrue(url and url.startswith("https://rmfyalk.court.gov.cn/"))
            self.assertNotIn("<", url)
            self.assertNotIn(">", url)

    def test_parser_merges_confirmed_urls_without_guessing(self):
        records = {record["source_file"]: record for record in parse_all()}
        urls = load_source_urls()
        for record in records.values():
            self.assertEqual(record["source_url"], urls[Path(record["source_file"]).name])

    def test_regenerated_jsonl_has_main_records_and_stable_ids(self):
        before = [json.loads(line) for line in JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
        result = subprocess.run([sys.executable, "scripts/parse_cases.py"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = [json.loads(line) for line in JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(after), 15)
        self.assertEqual([item["case_id"] for item in before], [item["case_id"] for item in after])
        by_file = {item["source_file"]: item for item in after}
        urls = load_source_urls()
        for record in after:
            self.assertEqual(record["source_url"], urls[Path(record["source_file"]).name])

    def test_local_and_unified_search_preserve_provenance(self):
        from backend.cases.search_service import UnifiedCaseSearchService
        from backend.cases.sources.local import LocalCuratedCaseProvider

        local = LocalCuratedCaseProvider().search("竞业限制", 3)
        urls = load_source_urls()
        self.assertTrue(any(item.source_url == urls["003_南京旭某餐饮管理有限公司诉刘某亮竞业限制纠纷案.pdf"] for item in local))
        unified = UnifiedCaseSearchService().search("竞业限制", 3)
        self.assertTrue(any(item.source_url == urls["003_南京旭某餐饮管理有限公司诉刘某亮竞业限制纠纷案.pdf"] for item in unified))

    def test_original_pdfs_are_not_changed(self):
        changed = subprocess.run(["git", "diff", "--name-only", "--", "data/raw/cases/*.pdf"], cwd=ROOT, capture_output=True, text=True, shell=False)
        self.assertEqual(changed.stdout.strip(), "")
