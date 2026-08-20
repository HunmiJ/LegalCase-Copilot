from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.cases.cache import CaseRuntimeCache
from backend.cases.search.models import CaseSearchResult, canonical_case_key, deduplicate_results
from backend.cases.search_service import UnifiedCaseSearchService
from backend.cases.sources.local import LocalCuratedCaseProvider
from backend.cases.sources.people_court_library import PeopleCourtCaseLibraryProvider
from backend.cases.sources.supreme_court import SupremeCourtOfficialProvider


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/processed/cases/cases.jsonl"


class V072CaseSearchTest(unittest.TestCase):
    def test_local_provider_loads_main_corpus_cases(self):
        provider = LocalCuratedCaseProvider(CORPUS)
        self.assertEqual(len(provider.index.records), 11)
        self.assertTrue(all(record["case_id"] for record in provider.index.records))

    def test_bm25_returns_top_k_for_three_typical_queries(self):
        provider = LocalCuratedCaseProvider(CORPUS)
        for query in ("下班以后还一直在微信处理工作", "签了竞业协议离职后去别的餐厅", "公司因送零食辞退我"):
            results = provider.search(query, 3)
            self.assertEqual(len(results), 3)
            self.assertTrue(all(result.score == result.score for result in results))

    def test_result_schema_and_provenance(self):
        result = LocalCuratedCaseProvider(CORPUS).search("竞业限制", 1)[0]
        self.assertIsInstance(result, CaseSearchResult)
        self.assertTrue(result.case_id and result.title)
        self.assertEqual(result.retrieval_source, "local")
        self.assertEqual(result.matched_sources, ["local"])
        self.assertTrue(result.source_file)
        self.assertTrue((ROOT / result.source_file).exists())

    def test_official_unavailable_falls_back_to_local(self):
        service = UnifiedCaseSearchService(
            local_provider=LocalCuratedCaseProvider(CORPUS),
            official_providers=[PeopleCourtCaseLibraryProvider(), SupremeCourtOfficialProvider()],
        )
        result = service.search("竞业限制", 3)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(item.retrieval_source == "local" for item in result))
        self.assertTrue(all(not status.search_available for status in service.provider_status))

    def test_duplicate_source_merges_by_database_case_number(self):
        first = CaseSearchResult(case_id="local-id", title="同一案例", database_case_number="db-1", source_name="local", source_file="a", matched_sources=["local"])
        second = CaseSearchResult(case_id="official-id", title="同一案例的官方版本", database_case_number="db-1", source_name="official", source_url="https://court.gov.cn/case", retrieval_source="official", matched_sources=["official"])
        merged = deduplicate_results([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(canonical_case_key(merged[0]), "database:db-1")
        self.assertEqual(set(merged[0].matched_sources), {"local", "official"})
        self.assertEqual(merged[0].source_url, "https://court.gov.cn/case")

    def test_runtime_cache_is_separate_and_does_not_change_corpus(self):
        before = CORPUS.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            cache = CaseRuntimeCache(Path(directory))
            cache.put("case-1", {
                "canonical_id": "db-1",
                "source_url": "https://court.gov.cn/case",
                "source_name": "Supreme Court",
                "retrieved_at": "2026-08-21T00:00:00+00:00",
                "normalized_data": {"title": "verified"},
                "cache_version": "v0.7.2",
            })
            self.assertEqual(cache.get("case-1")["canonical_id"], "db-1")
            self.assertFalse((ROOT / "data/cache").exists())
        self.assertEqual(CORPUS.read_bytes(), before)

    def test_queries_are_read_only_against_curated_jsonl(self):
        before = CORPUS.read_bytes()
        service = UnifiedCaseSearchService(local_provider=LocalCuratedCaseProvider(CORPUS))
        service.search("劳动争议", 10)
        self.assertEqual(CORPUS.read_bytes(), before)
