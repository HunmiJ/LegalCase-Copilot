import json
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from search_semantic import search_semantic


class V02RetrievalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = [json.loads(line) for line in (ROOT / "data/processed/laws.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        cls.embeddings = np.load(ROOT / "data/processed/embeddings.npy")
        cls.index = json.loads((ROOT / "data/processed/embedding_index.json").read_text(encoding="utf-8"))

    def test_all_records_have_embeddings_and_index(self):
        self.assertEqual(len(self.records), 372)
        self.assertEqual(len(self.embeddings), len(self.records))
        self.assertEqual(len(self.index), len(self.records))
        self.assertEqual(self.embeddings.ndim, 2)
        self.assertEqual(self.embeddings.shape, (len(self.records), 512))
        self.assertEqual(self.embeddings.shape[1], 512)
        self.assertTrue(np.isfinite(self.embeddings).all())

    def test_embedding_index_matches_jsonl_order(self):
        for position, (record, index) in enumerate(zip(self.records, self.index)):
            self.assertEqual(index["position"], position)
            self.assertEqual(index["id"], record["id"])
            self.assertEqual(index["source_file"], record["source_file"])
            self.assertTrue((ROOT / record["source_file"]).is_file())

    def test_semantic_search_returns_valid_top_k(self):
        results = search_semantic("公司不给我加班费", limit=5)
        self.assertEqual(len(results), 5)
        self.assertEqual([r["rank"] for r in results], [1, 2, 3, 4, 5])
        self.assertTrue(all(-1.0 <= r["similarity_score"] <= 1.0 for r in results))
        self.assertTrue(all((ROOT / r["source_file"]).is_file() for r in results))

    def test_raw_docx_unchanged_since_v01_commit(self):
        completed = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "data/raw/laws"], cwd=ROOT)
        self.assertEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
