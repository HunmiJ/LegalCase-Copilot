import json
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hybrid_utils import HybridRetriever, canonical_id
from reranker_utils import build_candidate_pool, load_reranker, rerank_candidates


class V04RerankerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = HybridRetriever(ROOT / "data/processed")
        cls.reranker = load_reranker(local_files_only=True)
        cls.query = "劳动仲裁是不是过一年就不能申请了"

    def test_reranker_model_loads_locally(self):
        self.assertIsNotNone(self.reranker)

    def test_candidate_ids_are_unique_and_reranker_returns_top_k(self):
        candidates = build_candidate_pool(self.retriever, self.query, 20)
        self.assertEqual(len({canonical_id(item) for item in candidates}), len(candidates))
        results = rerank_candidates(self.reranker, self.query, candidates, limit=10)
        self.assertEqual(len(results), 10)
        self.assertEqual([item["final_rank"] for item in results], list(range(1, 11)))
        self.assertEqual(len({item["canonical_id"] for item in results}), 10)

    def test_scores_are_finite_and_sorted_descending(self):
        candidates = build_candidate_pool(self.retriever, self.query, 20)
        results = rerank_candidates(self.reranker, self.query, candidates, limit=10)
        scores = [item["reranker_score"] for item in results]
        self.assertTrue(np.isfinite(scores).all())
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_bm25_only_and_semantic_only_candidates_participate(self):
        candidates = build_candidate_pool(self.retriever, self.query, 20)
        self.assertTrue(any(item.get("bm25_rank") is None for item in candidates))
        self.assertTrue(any(item.get("semantic_rank") is None for item in candidates))
        results = rerank_candidates(self.reranker, self.query, candidates, limit=len(candidates))
        result_ids = {item["canonical_id"] for item in results}
        self.assertEqual(result_ids, {canonical_id(item) for item in candidates})

    def test_benchmark_and_formal_data_are_read_only(self):
        report = json.loads((ROOT / "evaluation/results/v0.4_reranker_results.json").read_text(encoding="utf-8"))
        self.assertEqual(report["query_count"], 30)
        self.assertTrue((ROOT / "data/processed/laws.jsonl").is_file())
        self.assertTrue((ROOT / "data/processed/embeddings.npy").is_file())
        self.assertTrue((ROOT / "data/processed/embedding_index.json").is_file())
        self.assertEqual(subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "data/raw/laws"], cwd=ROOT).returncode, 0)
        self.assertEqual(subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "data/processed/legal.db", "data/processed/laws.jsonl", "data/processed/embeddings.npy", "data/processed/embedding_index.json"], cwd=ROOT).returncode, 0)


if __name__ == "__main__":
    unittest.main()
