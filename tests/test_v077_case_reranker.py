"""V0.7.7 reranker integrity and fallback tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from backend.cases.search.models import CaseSearchResult
from backend.cases.search.reranker import DEFAULT_CANDIDATE_DEPTH, case_reranker_text, rerank
from backend.cases.search_service import UnifiedCaseSearchService

ROOT = Path(__file__).resolve().parents[1]


class FakeModel:
    def predict(self, pairs, **kwargs):
        return np.arange(len(pairs), dtype=float)


def candidate(case_id: str, rank: int) -> CaseSearchResult:
    return CaseSearchResult(case_id=case_id, title=case_id, source_name="人民法院案例库", source_url="https://rmfyalk.court.gov.cn/example", hybrid_score=1 / rank)


def test_validation_queries_are_frozen_and_valid() -> None:
    path = ROOT / "evaluation/v077_reranker_validation_queries.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    ids = {record["case_id"] for record in (json.loads(line) for line in (ROOT / "data/processed/cases/cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())}
    assert len(rows) == 12
    assert len({row["query_id"] for row in rows}) == 12
    assert {row["difficulty"] for row in rows} == {"easy", "medium", "hard"}
    assert all(set(row["relevant_case_ids"]).issubset(ids) for row in rows)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (ROOT / "evaluation/v077_reranker_validation_queries.sha256").read_text(encoding="utf-8").strip()


def test_reranker_text_excludes_provenance() -> None:
    text = case_reranker_text({"title": "标题", "keywords": ["关键词"], "basic_facts": "事实", "source_url": "SECRET_URL", "source_file": "file.pdf", "case_id": "id"})
    assert "标题" in text and "事实" in text
    assert "SECRET_URL" not in text and "file.pdf" not in text and "id" not in text


def test_reranker_scores_are_finite_sorted_and_preserve_provenance() -> None:
    results = rerank(FakeModel(), "问题", [candidate("a", 1), candidate("b", 2), candidate("c", 3)], 3)
    assert len(results) == DEFAULT_CANDIDATE_DEPTH
    assert [item.final_rank for item in results] == [1, 2, 3]
    assert [item.reranker_score for item in results] == sorted([item.reranker_score for item in results], reverse=True)
    assert np.isfinite([item.reranker_score for item in results]).all()
    assert all(item.source_url == "https://rmfyalk.court.gov.cn/example" for item in results)


def test_reranker_deduplicates_canonical_case_id() -> None:
    results = rerank(FakeModel(), "问题", [candidate("a", 1), candidate("a", 2), candidate("b", 3)], 3)
    assert len(results) == 2
    assert len({item.case_id for item in results}) == 2


def test_frozen_hybrid_config_and_formal_data_are_unchanged() -> None:
    config = json.loads((ROOT / "evaluation/v076_hybrid_config.json").read_text(encoding="utf-8"))
    assert config["method"] == "weighted" and config["semantic_weight"] == 0.8
    assert (ROOT / "data/processed/cases/cases.jsonl").is_file()
    assert (ROOT / "data/processed/cases/case_embeddings.npy").is_file()


def test_unified_service_default_mode_is_hybrid() -> None:
    service = UnifiedCaseSearchService()
    default_results = service.search("普通厨师签竞业限制", 3)
    explicit_results = service.search("普通厨师签竞业限制", 3, mode="hybrid")
    assert [item.case_id for item in default_results] == [item.case_id for item in explicit_results]
