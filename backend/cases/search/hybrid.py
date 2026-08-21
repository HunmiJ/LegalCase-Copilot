"""Deterministic local hybrid case retrieval and rank fusion."""

from __future__ import annotations

from dataclasses import replace

from .models import CaseSearchResult


def _rank_normalized(rank: int | None, depth: int) -> float:
    if rank is None:
        return 0.0
    if depth <= 1:
        return 1.0
    return 1.0 - (rank - 1) / (depth - 1)


def fuse_ranked_results(
    bm25_results: list[CaseSearchResult],
    semantic_results: list[CaseSearchResult],
    *,
    method: str = "rrf",
    rrf_k: int = 60,
    semantic_weight: float = 0.8,
) -> list[CaseSearchResult]:
    """Merge candidates by canonical case_id; never merge different cases."""
    if method not in {"rrf", "weighted"}:
        raise ValueError("method must be rrf or weighted")
    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")
    if not 0.0 <= semantic_weight <= 1.0:
        raise ValueError("semantic_weight must be between 0 and 1")

    by_id: dict[str, CaseSearchResult] = {}
    bm25_rank: dict[str, int] = {}
    semantic_rank: dict[str, int] = {}
    order: list[str] = []
    for rank, result in enumerate(bm25_results, 1):
        by_id.setdefault(result.case_id, result)
        bm25_rank[result.case_id] = rank
        if result.case_id not in order:
            order.append(result.case_id)
    for rank, result in enumerate(semantic_results, 1):
        by_id.setdefault(result.case_id, result)
        semantic_rank[result.case_id] = rank
        if result.case_id not in order:
            order.append(result.case_id)

    bm25_depth = len(bm25_results)
    semantic_depth = len(semantic_results)
    scored: list[CaseSearchResult] = []
    for position, case_id in enumerate(order):
        result = by_id[case_id]
        br = bm25_rank.get(case_id)
        sr = semantic_rank.get(case_id)
        if method == "rrf":
            score = (1.0 / (rrf_k + br) if br else 0.0) + (1.0 / (rrf_k + sr) if sr else 0.0)
        else:
            score = ((1.0 - semantic_weight) * _rank_normalized(br, bm25_depth)
                     + semantic_weight * _rank_normalized(sr, semantic_depth))
        matched = list(dict.fromkeys((result.matched_sources or []) + (["bm25"] if br else []) + (["semantic"] if sr else [])))
        scored.append(replace(result, score=float(score), hybrid_score=float(score),
                              bm25_rank=br, bm25_score=(float(result.score) if br else None),
                              semantic_rank=sr, matched_sources=matched))
    scored.sort(key=lambda item: (-float(item.hybrid_score or 0.0), order.index(item.case_id)))
    return scored


class CaseHybridIndex:
    def __init__(self, bm25_index, semantic_index, *, method: str = "rrf", rrf_k: int = 60, semantic_weight: float = 0.8,
                 candidate_top_k: int = 10) -> None:
        self.bm25_index = bm25_index
        self.semantic_index = semantic_index
        self.method = method
        self.rrf_k = rrf_k
        self.semantic_weight = semantic_weight
        self.candidate_top_k = candidate_top_k

    def search(self, query: str, top_k: int = 10) -> list[CaseSearchResult]:
        bm25_results = self.bm25_index.search(query, self.candidate_top_k)
        semantic_results = self.semantic_index.search(query, self.candidate_top_k)
        return fuse_ranked_results(bm25_results, semantic_results, method=self.method,
                                   rrf_k=self.rrf_k, semantic_weight=self.semantic_weight)[:top_k]
