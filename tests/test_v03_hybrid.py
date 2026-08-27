import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hybrid_utils import HybridRetriever, canonical_id, fuse_ranked_results


class HybridRetrievalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = HybridRetriever(ROOT / "data/processed")
        cls.records = [json.loads(line) for line in (ROOT / "data/processed/laws.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_hybrid_returns_top_k_with_valid_scores(self):
        results = self.retriever.search("劳动仲裁是不是过一年就不能申请了", candidate_limit=20, limit=10, rrf_k=60)
        self.assertEqual(len(results), 10)
        self.assertEqual([result["hybrid_rank"] for result in results], list(range(1, 11)))
        self.assertTrue(all(result["rrf_score"] > 0 for result in results))
        self.assertEqual(len({result["canonical_id"] for result in results}), 10)
        self.assertTrue(all(result["source_file"].startswith("data/raw/laws/") for result in results))

    def test_hybrid_top20_has_unique_canonical_ids(self):
        results = self.retriever.search("劳动仲裁是不是过一年就不能申请了", candidate_limit=20, limit=20, rrf_k=60)
        self.assertEqual(len(results), 20)
        self.assertEqual(len({result["canonical_id"] for result in results}), 20)

    def test_bm25_only_and_semantic_only_candidates_participate(self):
        bm25 = [{"source_file": "a", "article_number": "第一条", "rank": 1, "bm25_score": 2.0, "law_name": "A", "article_content": "a"}]
        semantic = [{"source_file": "b", "article_number": "第二条", "rank": 1, "similarity_score": 0.9, "law_name": "B", "article_content": "b"}]
        fused = fuse_ranked_results(bm25, semantic, 60, 10)
        self.assertEqual(len(fused), 2)
        self.assertIsNone(next(item for item in fused if item["source_file"] == "a")["semantic_rank"])
        self.assertIsNone(next(item for item in fused if item["source_file"] == "b")["bm25_rank"])

    def test_shared_candidate_accumulates_both_rrf_terms(self):
        base = {"id": "doc-a", "source_file": "a", "article_number": "第一条", "law_name": "A", "article_content": "a"}
        bm25 = [dict(base, rank=1, bm25_score=4.0)]
        semantic = [dict(base, rank=2, similarity_score=0.8)]
        fused = fuse_ranked_results(bm25, semantic, 60, 1)[0]
        self.assertAlmostEqual(fused["rrf_score"], 1 / 61 + 1 / 62, places=10)
        self.assertEqual(fused["bm25_rank"], 1)
        self.assertEqual(fused["semantic_rank"], 2)

    def test_same_article_number_from_different_laws_stays_distinct(self):
        labor_law = next(record for record in self.records if record["law_name"] == "中华人民共和国劳动法" and record["article_number"] == "第十七条")
        contract_law = next(record for record in self.records if record["law_name"] == "中华人民共和国劳动合同法" and record["article_number"] == "第十七条")
        fused = fuse_ranked_results([dict(labor_law, rank=1, bm25_score=1.0)],
                                    [dict(contract_law, rank=1, similarity_score=0.9)], 60, 10)
        self.assertEqual(len(fused), 2)
        self.assertNotEqual(canonical_id(labor_law), canonical_id(contract_law))
        self.assertEqual({item["law_name"] for item in fused}, {"中华人民共和国劳动法", "中华人民共和国劳动合同法"})

    def test_benchmark_result_file_has_30_queries(self):
        result = ROOT / "evaluation/results/v0.3_retrieval_results.json"
        self.assertTrue(result.is_file())
        report = json.loads(result.read_text(encoding="utf-8"))
        self.assertEqual(report["query_count"], 30)
        self.assertIn("hybrid", report["summary"])

    def test_raw_docx_unchanged(self):
        self.assertTrue((ROOT / 'data/processed/laws.jsonl').is_file())


if __name__ == "__main__":
    unittest.main()
