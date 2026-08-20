from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

import numpy as np

from backend.cases.sources.local import LocalCuratedCaseProvider
from backend.cases.sources.semantic_local import LocalSemanticCaseProvider


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/cases"


class V074Phase10FreezeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [json.loads(line) for line in (ROOT / "data/processed/cases/cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        cls.index = json.loads((ROOT / "data/processed/cases/case_embedding_index.json").read_text(encoding="utf-8"))
        cls.metadata = json.loads((ROOT / "data/case_metadata.json").read_text(encoding="utf-8"))

    def test_frozen_counts_and_identity(self):
        self.assertEqual(len(list(RAW.glob("*.pdf"))), 20)
        self.assertEqual(len(self.rows), 19)
        self.assertEqual(np.load(ROOT / "data/processed/cases/case_embeddings.npy").shape, (19, 512))
        self.assertEqual(len(self.index), 19)
        self.assertEqual({r["case_id"] for r in self.rows}, {r["case_id"] for r in self.index})

    def test_auxiliary_and_not_found_statuses(self):
        self.assertNotIn("2014-18-1-232-001", {r["case_id"] for r in self.index})
        with (RAW / "case_collection_plan.csv").open(encoding="utf-8-sig", newline="") as handle:
            plan = {r["planned_number"]: r for r in csv.DictReader(handle)}
        for n in ("010", "018", "021"):
            self.assertEqual(plan[n]["status"], "not_found")
        self.assertEqual(sum(plan[n]["status"] == "pending_retry" for n in plan), 0)

    def test_022_023_provenance_and_main_metadata(self):
        with (RAW / "source_urls.csv").open(encoding="utf-8-sig", newline="") as handle:
            urls = {r["filename"]: r["source_url"] for r in csv.DictReader(handle)}
        metadata = {Path(r["source_file"]).name: r for r in self.metadata}
        for path in list(RAW.glob("022_*.pdf")) + list(RAW.glob("023_*.pdf")):
            self.assertTrue(urls[path.name].startswith("https://rmfyalk.court.gov.cn/"))
            self.assertEqual(metadata[path.name]["corpus_status"], "ELIGIBLE_MAIN_CORPUS")
            self.assertTrue(metadata[path.name]["actual_topic"])

    def test_022_023_smoke_targets_rank_first(self):
        queries = {
            "公司在我怀孕期间把我辞退了，还停了社保，导致生育津贴也领不到怎么办": "2026-07-2-533-003",
            "公司一直少发工资，我因此提出解除劳动合同，还能要求经济补偿吗": "2023-16-2-186-002",
        }
        bm25 = LocalCuratedCaseProvider()
        semantic = LocalSemanticCaseProvider()
        for query, expected in queries.items():
            self.assertEqual(bm25.search(query, 1)[0].case_id, expected)
            self.assertEqual(semantic.search(query, 1)[0].case_id, expected)


if __name__ == "__main__":
    unittest.main()
