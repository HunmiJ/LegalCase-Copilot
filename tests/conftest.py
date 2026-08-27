from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_DATA_TESTS = {
    "test_bm25_retrieval.py": "processed law corpus",
    "test_v02_retrieval.py": "processed law embeddings",
    "test_v03_hybrid.py": "processed law corpus",
    "test_v04_reranker.py": "processed law corpus",
    "test_full_case_retrieval_config.py": "curated/full case corpus",
    "test_v072_case_search.py": "curated case corpus",
    "test_v073_case_semantic.py": "curated case embeddings",
    "test_v074_corpus_promotion.py": "curated case corpus",
    "test_v074_phase6_promotion.py": "curated case corpus",
    "test_v074_phase10_freeze.py": "curated case corpus",
    "test_v074_phase8_promotion.py": "curated raw case inputs",
    "test_v075_case_benchmark.py": "curated case corpus",
    "test_v076_hybrid.py": "curated case corpus",
    "test_v077_case_reranker.py": "curated case corpus",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        reason = EXTERNAL_DATA_TESTS.get(Path(str(item.fspath)).name)
        if reason:
            item.add_marker(pytest.mark.skip(reason=f"external data not distributed: {reason}"))
