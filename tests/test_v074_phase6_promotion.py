from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from backend.cases.sources.local import LocalCuratedCaseProvider
from backend.cases.sources.semantic_local import LocalSemanticCaseProvider


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/cases"
CORPUS = ROOT / "data/processed/cases/cases.jsonl"
INDEX = ROOT / "data/processed/cases/case_embedding_index.json"


class V074Phase6PromotionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]
        cls.metadata = json.loads((ROOT / "data/case_metadata.json").read_text(encoding="utf-8"))
        cls.eligibility = json.loads((ROOT / "data/case_eligibility.json").read_text(encoding="utf-8"))

    def test_intake_and_not_found_numbers(self):
        self.assertEqual(len(list(RAW.glob("*.pdf"))), 16)
        plan = (RAW / "case_collection_plan.csv").read_text(encoding="utf-8-sig")
        self.assertIn("010", plan)
        self.assertIn("018", plan)
        self.assertEqual(sum(name.startswith("010_") or name.startswith("018_") for name in [p.name for p in RAW.glob("*.pdf")]), 0)

    def test_new_cases_are_main_and_auxiliary_is_excluded(self):
        status = {item["source_file"].split("/")[-1]: item["corpus_status"] for item in self.eligibility}
        self.assertTrue(all(status[next(p.name for p in RAW.glob(f"{n}_*.pdf"))] == "ELIGIBLE_MAIN_CORPUS" for n in ("014", "015", "016", "017")))
        self.assertEqual(status[next(p.name for p in RAW.glob("011_*.pdf"))], "AUXILIARY_ONLY")
        main_ids = {row["case_id"] for row in self.rows}
        self.assertNotIn("2014-18-1-232-001", main_ids)
        self.assertEqual(len(self.rows), 15)

    def test_metadata_has_actual_topics_for_new_cases(self):
        by_file = {Path(item["source_file"]).name: item for item in self.metadata}
        self.assertEqual(by_file[next(p.name for p in RAW.glob("014_*.pdf"))]["actual_topic"], "工资欠条追索劳动报酬及普通民事受案范围")
        self.assertIn("竞业限制", by_file[next(p.name for p in RAW.glob("015_*.pdf"))]["actual_topic"])
        self.assertIn("绩效末位", by_file[next(p.name for p in RAW.glob("016_*.pdf"))]["actual_topic"])
        self.assertIn("工伤保险", by_file[next(p.name for p in RAW.glob("017_*.pdf"))]["actual_topic"])

    def test_new_case_smoke_queries_rank_target_first(self):
        queries = {
            "俱乐部拖欠我的工资奖金，我拿着工资欠条能不能直接起诉": "2023-07-2-186-010",
            "公司给我竞业限制补偿后，我通过配偶投资了竞争公司，会不会要赔违约金": "2024-07-2-490-006",
            "绩效考核排名最后，公司能直接说我不能胜任工作然后辞退吗": "2013-18-2-186-001",
            "公司工伤保险没按实际工资缴，导致伤残补助金少了怎么办": "2023-16-2-490-007",
        }
        bm25 = LocalCuratedCaseProvider()
        semantic = LocalSemanticCaseProvider()
        for query, expected in queries.items():
            self.assertEqual(bm25.search(query, 1)[0].case_id, expected)
            self.assertEqual(semantic.search(query, 1)[0].case_id, expected)

    def test_main_artifact_counts_and_case_ids_match(self):
        index = json.loads(INDEX.read_text(encoding="utf-8"))
        main_ids = {row["case_id"] for row in self.rows}
        self.assertEqual(len(index), 15)
        self.assertEqual({item["case_id"] for item in index}, main_ids)
        self.assertNotIn("2014-18-1-232-001", {item["case_id"] for item in index})

    def test_formal_law_and_rag_products_are_clean(self):
        protected = ["data/raw/laws", "data/processed/legal.db", "data/processed/laws.jsonl", "data/processed/embeddings.npy", "data/processed/embedding_index.json", "evaluation/retrieval_queries.json", "evaluation/rag_queries.json"]
        for path in protected:
            self.assertEqual(subprocess.run(["git", "diff", "--quiet", "--", path]).returncode, 0, path)

    def test_raw_pdfs_are_read_only(self):
        self.assertTrue(all(path.stat().st_size > 0 for path in RAW.glob("*.pdf")))


if __name__ == "__main__":
    unittest.main()
