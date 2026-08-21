"""V0.7.6 hybrid, split, freeze, and regression tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.cases.search.hybrid import fuse_ranked_results
from backend.cases.search.models import CaseSearchResult

ROOT = Path(__file__).resolve().parents[1]


def result(case_id: str, score: float = 1.0, source: str = "local") -> CaseSearchResult:
    return CaseSearchResult(case_id=case_id, title=case_id, score=score, retrieval_source=source)


def test_rrf_formula_and_canonical_deduplication() -> None:
    merged = fuse_ranked_results([result("a", 8), result("b", 2)], [result("b", .8), result("c", .7)], method="rrf", rrf_k=20)
    assert [item.case_id for item in merged] == ["b", "a", "c"]
    assert len({item.case_id for item in merged}) == 3
    assert merged[0].hybrid_score == 1 / 22 + 1 / 21
    assert merged[0].bm25_rank == 2 and merged[0].semantic_rank == 1


def test_weighted_fusion_uses_rank_normalization() -> None:
    merged = fuse_ranked_results([result("a"), result("b")], [result("b"), result("c")], method="weighted", semantic_weight=.8)
    assert len(merged) == 3
    assert merged[0].case_id == "b"
    assert all(0 <= float(item.hybrid_score) <= 1 for item in merged)


def test_frozen_split_and_hash_are_valid() -> None:
    split = json.loads((ROOT / "evaluation/case_retrieval_split.json").read_text(encoding="utf-8"))
    assert len(split["dev_query_ids"]) == 20
    assert len(split["test_query_ids"]) == 10
    assert not set(split["dev_query_ids"]) & set(split["test_query_ids"])
    assert set(split["dev_query_ids"]) | set(split["test_query_ids"]) == {f"cq{i:02d}" for i in range(1, 31)}
    digest = hashlib.sha256((ROOT / "evaluation/case_retrieval_split.json").read_bytes()).hexdigest()
    assert digest == (ROOT / "evaluation/case_retrieval_split.sha256").read_text(encoding="utf-8").strip()


def test_frozen_config_exists_and_hybrid_results_cover_all_queries() -> None:
    config = json.loads((ROOT / "evaluation/v076_hybrid_config.json").read_text(encoding="utf-8"))
    assert config["method"] in {"rrf", "weighted"}
    results = json.loads((ROOT / "evaluation/v076_hybrid_results.json").read_text(encoding="utf-8"))["results"]
    assert len(results) == 30
    for row in results:
        assert len(row["hybrid"]["top10"]) == 10
        assert len({item["case_id"] for item in row["hybrid"]["top10"]}) == 10


def test_frozen_query_and_corpus_integrity() -> None:
    query_hash = hashlib.sha256((ROOT / "evaluation/case_retrieval_queries.json").read_bytes()).hexdigest()
    assert query_hash == "f577de865360e923266ea9975de8ee0b7ef429630be8225a774ba4f797673305"
    assert len([line for line in (ROOT / "data/processed/cases/cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]) == 19
