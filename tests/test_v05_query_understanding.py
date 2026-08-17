from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import MockProvider, QueryUnderstandingService
from backend.llm.schema import SchemaValidationError, parse_and_validate
from query_expansion import expanded_queries
from reranker_utils import rank_scored_candidates
from understood_utils import build_multi_query_candidates


class FakeRetriever:
    def __init__(self):
        self.records = [
            {"id": "law-a-17", "law_name": "劳动法", "article_number": "第十七条", "article_content": "甲", "source_file": "a.docx"},
            {"id": "law-b-17", "law_name": "劳动合同法", "article_number": "第十七条", "article_content": "乙", "source_file": "b.docx"},
            {"id": "law-c-1", "law_name": "劳动争议法", "article_number": "第一条", "article_content": "丙", "source_file": "c.docx"},
        ]

        class Searcher:
            def __init__(self, records, semantic=False):
                self.records = records
                self.semantic = semantic

            def search(self, query, limit):
                rows = []
                for rank, record in enumerate(self.records[:limit], 1):
                    row = dict(record)
                    row["rank"] = rank
                    row["bm25_score"] = float(10 - rank)
                    rows.append(row)
                return rows

        self.bm25 = Searcher(self.records)

        class SemanticSearcher:
            def __init__(self, records):
                self.records = records

            def search(self, query, limit):
                rows = []
                for rank, record in enumerate(self.records[1:] + self.records[:1], 1):
                    row = dict(record)
                    row["rank"] = rank
                    row["similarity_score"] = 1.0 / rank
                    rows.append(row)
                return rows[:limit]

        self.semantic = SemanticSearcher(self.records)

    def semantic_search(self, query, limit):
        return self.semantic.search(query, limit)


class V05QueryUnderstandingTest(unittest.TestCase):
    def test_schema_validation_and_limits(self):
        result = parse_and_validate(MockProvider().generate("公司不给我加班费"), "公司不给我加班费")
        self.assertEqual(result["domain"], "劳动争议")
        self.assertLessEqual(len(result["search_queries"]), 3)
        self.assertLessEqual(len(result["legal_concepts"]), 8)
        with self.assertRaises(SchemaValidationError):
            parse_and_validate("{bad json", "问题")

    def test_invalid_json_retry_and_fallback(self):
        class BadProvider:
            name = "bad"
            model = "bad-v1"
            def __init__(self):
                self.calls = 0
            def generate(self, query):
                self.calls += 1
                return "not-json"

        provider = BadProvider()
        with tempfile.TemporaryDirectory() as directory:
            result = QueryUnderstandingService(provider, Path(directory) / "cache.json", max_retries=2).understand("测试")
        self.assertEqual(provider.calls, 3)
        self.assertEqual(result["provider_status"], "fallback")
        self.assertEqual(result["search_queries"], ["测试"])

    def test_cache_reuses_valid_result(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            service = QueryUnderstandingService(MockProvider(), cache)
            first = service.understand("试用期可以随便辞退吗")
            second = QueryUnderstandingService(MockProvider(), cache).understand("试用期可以随便辞退吗")
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])

    def test_expansion_is_bounded_and_keeps_original(self):
        queries = expanded_queries(MockProvider().generate("老板突然把我开了怎么办") and
                                   json.loads(MockProvider().generate("老板突然把我开了怎么办")),
                                   "老板突然把我开了怎么办")
        self.assertLessEqual(len(queries), 3)
        self.assertEqual(queries[0], "老板突然把我开了怎么办")

    def test_multi_query_fusion_deduplicates_canonical_ids(self):
        retriever = FakeRetriever()
        candidates, stats = build_multi_query_candidates(retriever, ["原始", "扩展"], 3, 10)
        ids = [item["canonical_id"] for item in candidates]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(stats["raw_candidate_count"], 12)
        self.assertEqual(stats["unique_candidate_count"], 3)
        self.assertTrue(all("matched_queries" in item for item in candidates))
        self.assertEqual({item["article_number"] for item in candidates}, {"第十七条", "第一条"})

    def test_bm25_and_semantic_only_candidates_are_retained(self):
        retriever = FakeRetriever()
        retriever.semantic.search = lambda query, limit: [dict(retriever.records[2], rank=1, similarity_score=0.8)]
        candidates, _ = build_multi_query_candidates(retriever, ["原始"], 3, 10)
        self.assertEqual({item["canonical_id"] for item in candidates}, {"law-a-17", "law-b-17", "law-c-1"})

    def test_reranker_scores_are_finite_and_ordered(self):
        candidates = [{"id": "a", "source_file": "a", "article_number": "1"},
                      {"id": "b", "source_file": "b", "article_number": "2"}]
        results = rank_scored_candidates(candidates, [0.2, 0.9], 2)
        self.assertEqual([item["canonical_id"] for item in results], ["b", "a"])
        self.assertTrue(all(isinstance(item["reranker_score"], float) for item in results))

    def test_env_ignored_and_no_api_key_literal_in_code(self):
        ignored = subprocess.run(["git", "check-ignore", ".env"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(ignored.returncode, 0)
        for path in (ROOT / "backend", ROOT / "scripts", ROOT / "tests"):
            for source in path.rglob("*.py"):
                self.assertNotIn("sk-" + "test-secret", source.read_text(encoding="utf-8"))

    def test_frozen_benchmark_and_formal_data_are_read_only(self):
        queries = json.loads((ROOT / "evaluation/retrieval_queries.json").read_text(encoding="utf-8"))
        self.assertEqual(len(queries), 30)
        raw = subprocess.run(["git", "diff", "--name-only", "--", "data/raw/laws", "data/processed/legal.db",
                              "data/processed/laws.jsonl", "data/processed/embeddings.npy", "data/processed/embedding_index.json"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(raw.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
