from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

import numpy as np

from backend.cases.search.semantic import case_embedding_text
from backend.cases.search_service import UnifiedCaseSearchService
from backend.cases.sources.semantic_local import LocalSemanticCaseProvider


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/processed/cases/cases.jsonl"
EMBEDDINGS = ROOT / "data/processed/cases/case_embeddings.npy"
INDEX = ROOT / "data/processed/cases/case_embedding_index.json"


class V073CaseSemanticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]
        cls.embeddings = np.load(EMBEDDINGS)
        cls.index = json.loads(INDEX.read_text(encoding="utf-8"))
        cls.provider = LocalSemanticCaseProvider()

    def test_model_and_embedding_artifacts_are_valid(self):
        self.assertIsNotNone(self.provider.index.model)
        self.assertEqual(len(self.records), 19)
        self.assertEqual(self.embeddings.shape[0], 19)
        self.assertEqual(self.embeddings.shape[1], 512)
        self.assertTrue(np.isfinite(self.embeddings).all())

    def test_index_matches_case_ids_and_source_files(self):
        self.assertEqual({item["case_id"] for item in self.index}, {record["case_id"] for record in self.records})
        by_id = {record["case_id"]: record for record in self.records}
        for item in self.index:
            self.assertEqual(item["source_file"], by_id[item["case_id"]]["source_file"])
            self.assertTrue((ROOT / item["source_file"]).is_file())

    def test_embedding_text_excludes_provenance(self):
        record = dict(self.records[0])
        text = case_embedding_text(record)
        self.assertIn(record["title"], text)
        self.assertNotIn(record["source_file"], text)
        self.assertNotIn(record["source_url"] or "https://", text)
        self.assertNotIn("retrieved_at", text)

    def test_semantic_search_returns_sorted_valid_top_k_with_provenance(self):
        results = self.provider.search("老板下班后总让我在微信继续处理工作", 3)
        self.assertEqual(len(results), 3)
        self.assertEqual([result.case_id for result in results[:1]], ["2024-18-2-490-002"])
        scores = [result.semantic_score for result in results]
        self.assertTrue(all(score is not None and -1.0 <= score <= 1.0 for score in scores))
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(results[0].source_name, "人民法院案例库")
        self.assertTrue(results[0].source_url.startswith("https://rmfyalk.court.gov.cn/"))

    def test_three_core_queries_rank_expected_case_first(self):
        queries = {
            "老板下班后总让我在微信继续处理工作": "2024-18-2-490-002",
            "幼儿园因为老师收了小朋友一点零食就解除劳动合同": "2024-18-2-490-003",
            "普通厨师签了竞业限制，离职后去了另一家餐厅": "2025-07-2-186-002",
        }
        for query, expected in queries.items():
            self.assertEqual(self.provider.search(query, 3)[0].case_id, expected)

    def test_unified_semantic_and_bm25_modes_work(self):
        service = UnifiedCaseSearchService()
        semantic = service.search("普通员工不知道商业秘密却被要求竞业", 3, mode="semantic")
        bm25 = service.search("普通员工不知道商业秘密却被要求竞业", 3, mode="bm25")
        self.assertEqual(semantic[0].case_id, "2025-07-2-186-002")
        self.assertEqual(len(bm25), 3)
        hybrid = service.search("竞业限制", 3, mode="hybrid")
        self.assertEqual(len(hybrid), 3)
        self.assertEqual(len({result.case_id for result in hybrid}), 3)

    def test_case_corpus_and_raw_pdfs_are_read_only(self):
        self.assertEqual(CORPUS.read_bytes(), CORPUS.read_bytes())
        changed = subprocess.run(["git", "diff", "--name-only", "--", "data/raw/cases"], cwd=ROOT, capture_output=True, text=True)
        self.assertNotIn(".pdf", changed.stdout)


if __name__ == "__main__":
    unittest.main()
