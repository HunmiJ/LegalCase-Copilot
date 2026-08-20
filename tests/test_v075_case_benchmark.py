"""Integrity and metric tests for the frozen V0.7.5 case benchmark."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluation.case_retrieval.metrics import metric_for_ranks


ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "evaluation/case_retrieval_queries.json"
CORPUS = ROOT / "data/processed/cases/cases.jsonl"


def test_frozen_benchmark_has_30_queries_and_valid_labels() -> None:
    rows = json.loads(QUERIES.read_text(encoding="utf-8"))
    records = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = {record["case_id"] for record in records}
    assert len(records) == 19
    assert len(rows) == 30
    assert len({row["query_id"] for row in rows}) == 30
    assert sum(row["difficulty"] == "easy" for row in rows) == 10
    assert sum(row["difficulty"] == "medium" for row in rows) == 12
    assert sum(row["difficulty"] == "hard" for row in rows) == 8
    assert all(set(row["relevant_case_ids"]).issubset(ids) for row in rows)
    assert all(row["primary_case_id"] in row["relevant_case_ids"] for row in rows)
    assert all("2014-18-1-232-001" not in row["relevant_case_ids"] for row in rows)


def test_frozen_benchmark_sha256_matches() -> None:
    digest = hashlib.sha256(QUERIES.read_bytes()).hexdigest()
    assert digest == (QUERIES.with_suffix(".sha256").read_text(encoding="utf-8").strip())


def test_metric_definition_and_recall_monotonicity() -> None:
    ranks = ["a", "b", "c", "d", "e"]
    relevant = {"c", "e"}
    metric = metric_for_ranks(ranks, relevant, 10)
    assert metric["first_relevant_rank"] == 3
    assert metric["mrr"] == 1 / 3
    assert 0 <= metric["ndcg"] <= 1
    first = metric_for_ranks(ranks, relevant, 1)["recall"]
    third = metric_for_ranks(ranks, relevant, 3)["recall"]
    fifth = metric_for_ranks(ranks, relevant, 5)["recall"]
    assert first <= third <= fifth


def test_benchmark_output_contains_both_methods_and_top10() -> None:
    results = json.loads((ROOT / "evaluation/case_retrieval_results.json").read_text(encoding="utf-8"))
    rows = results["results"]
    assert len(rows) == 30
    for row in rows:
        assert len(row["bm25"]["top10"]) == 10
        assert len(row["semantic"]["top10"]) == 10
        assert len({item["case_id"] for item in row["bm25"]["top10"]}) == 10
        assert len({item["case_id"] for item in row["semantic"]["top10"]}) == 10


def test_benchmark_does_not_include_auxiliary_case() -> None:
    results = json.loads((ROOT / "evaluation/case_retrieval_results.json").read_text(encoding="utf-8"))
    assert all(item["case_id"] != "2014-18-1-232-001" for row in results["results"] for method in ("bm25", "semantic") for item in row[method]["top10"])
