from __future__ import annotations

import os
import unittest
from pathlib import Path

from backend.cases.search.models import CaseSearchResult
from backend.cases.search_service import UnifiedCaseSearchService


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data/processed/cases"
FULL = ROOT / "data/processed/full_cases"


class FullCaseRetrievalConfigTest(unittest.TestCase):
    def setUp(self):
        self.previous = os.environ.get("CASE_CORPUS_PATH")

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("CASE_CORPUS_PATH", None)
        else:
            os.environ["CASE_CORPUS_PATH"] = self.previous

    def test_benchmark_corpus_is_default_and_loads(self):
        os.environ.pop("CASE_CORPUS_PATH", None)
        service = UnifiedCaseSearchService()
        results = service.search("竞业限制", 3, mode="bm25")
        self.assertEqual(service.corpus_config.directory, BENCHMARK.resolve())
        self.assertEqual(len(results), 3)
        self.assertTrue(all(isinstance(result, CaseSearchResult) for result in results))

    def test_full_corpus_can_be_selected_from_environment(self):
        os.environ["CASE_CORPUS_PATH"] = str(FULL)
        service = UnifiedCaseSearchService()
        results = service.search("违法解除劳动合同", 5, mode="bm25")
        self.assertEqual(service.corpus_config.directory, FULL.resolve())
        self.assertEqual(len(service.local_provider.index.records), 6492)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(isinstance(result, CaseSearchResult) for result in results))

    def test_full_corpus_semantic_and_hybrid_use_shared_artifacts(self):
        service = UnifiedCaseSearchService(corpus_path=FULL)
        semantic = service.search("加班工资争议", 3, mode="semantic")
        hybrid = service.search("加班工资争议", 3, mode="hybrid")
        self.assertEqual(len(semantic), 3)
        self.assertEqual(len(hybrid), 3)
        self.assertTrue(all(isinstance(result, CaseSearchResult) for result in semantic + hybrid))
        self.assertEqual(service.corpus_config.embeddings_path, FULL / "case_embeddings.npy")
        self.assertEqual(service.corpus_config.index_path, FULL / "case_embedding_index.json")

    def test_full_corpus_case_ids_are_unique(self):
        service = UnifiedCaseSearchService(corpus_path=FULL)
        ids = [record["case_id"] for record in service.local_provider.index.records]
        self.assertEqual(len(ids), 6492)
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
