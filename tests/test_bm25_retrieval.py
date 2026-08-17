import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from bm25_utils import BM25Retriever, load_records, tokenize


class BM25RetrievalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_records(ROOT / "data/processed/laws.jsonl")
        cls.retriever = BM25Retriever(cls.records)

    def test_all_372_records_are_in_bm25_corpus(self):
        self.assertEqual(len(self.records), 372)
        self.assertEqual(len(self.retriever.tokenized_corpus), 372)
        self.assertEqual(len(self.retriever.bm25.doc_freqs), 372)

    def test_chinese_tokenization_and_search(self):
        tokens = tokenize("老板突然把我开了，我应该怎么办")
        self.assertTrue(tokens)
        self.assertIn("老板", tokens)
        results = self.retriever.search("公司不给我加班费", 5)
        self.assertEqual(len(results), 5)
        self.assertEqual([r["rank"] for r in results], [1, 2, 3, 4, 5])

    def test_results_correspond_to_laws_jsonl(self):
        keys = {(r["source_file"], r["article_number"]) for r in self.records}
        for result in self.retriever.search("试用期被辞退", 10):
            self.assertIn((result["source_file"], result["article_number"]), keys)
            self.assertTrue((ROOT / result["source_file"]).is_file())

    def test_raw_docx_unchanged(self):
        completed = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "data/raw/laws"], cwd=ROOT)
        self.assertEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
