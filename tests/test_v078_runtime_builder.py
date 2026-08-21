from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.cases.runtime_builder import RuntimePaths, discover, is_official_url, safe_filename, write_collection_plan


class V078RuntimeBuilderTest(unittest.TestCase):
    def test_official_provenance_and_safe_filename(self):
        self.assertTrue(is_official_url("https://rmfyalk.court.gov.cn/detail?id=1"))
        self.assertFalse(is_official_url("https://example.com/detail?id=1"))
        self.assertEqual(safe_filename("2024-18-2-490-002", "A/B:C?D"), "2024-18-2-490-002__A_B_C_D.pdf")

    def test_discovery_is_canonical_and_resumable(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = RuntimePaths(Path(directory))
            first = discover(paths, case_id="2024-18-2-490-002", title="案例", database_case_number="2024-18-2-490-002", source_url="https://rmfyalk.court.gov.cn/detail/1", topic="违法解除", discovery_query="违法解除 劳动合同")
            second = discover(paths, case_id="2024-18-2-490-002", title="不同标题", database_case_number="2024-18-2-490-002", source_url="https://rmfyalk.court.gov.cn/detail/2", topic="其他", discovery_query="其他")
            self.assertEqual(first, second)
            self.assertEqual(len(paths.manifest.read_text(encoding="utf-8").splitlines()), 1)

    def test_plan_is_independent_from_benchmark(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = RuntimePaths(Path(directory))
            write_collection_plan(paths)
            plan = json.loads(paths.plan.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(plan["topics"]), 10)
            self.assertNotIn("retrieval_queries", plan)


if __name__ == "__main__":
    unittest.main()
