"""Cross-Encoder reranking helpers for V0.4."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from sentence_transformers import CrossEncoder

from hybrid_utils import DEFAULT_RRF_K, HybridRetriever, canonical_id, fuse_ranked_results

ROOT = Path(__file__).resolve().parents[1]
MODEL_NAME = "BAAI/bge-reranker-base"
# Selected by the V0.4 depth experiment: 50+50 balanced retrieval quality
# and CPU reranking latency better than the 100+100 setting.
DEFAULT_CANDIDATE_DEPTH = 50


def load_reranker(local_files_only: bool = True) -> CrossEncoder:
    return CrossEncoder(MODEL_NAME, device="cpu", local_files_only=local_files_only)


def document_text(record: dict) -> str:
    return " ".join(filter(None, [record.get("law_name"), record.get("chapter"),
                                  record.get("article_number"), record.get("article_content")]))


def build_candidate_pool(retriever: HybridRetriever, query: str, candidate_depth: int,
                         rrf_k: int = DEFAULT_RRF_K) -> list[dict]:
    bm25_results = retriever.bm25.search(query, candidate_depth)
    semantic_results = retriever.semantic_search(query, candidate_depth)
    return fuse_ranked_results(bm25_results, semantic_results, rrf_k,
                               limit=len(bm25_results) + len(semantic_results))


def rerank_candidates(model: CrossEncoder, query: str, candidates: list[dict],
                      limit: int = 10, batch_size: int = 64, max_length: int = 256) -> list[dict]:
    unique = {}
    for candidate in candidates:
        unique[canonical_id(candidate)] = candidate
    candidates = list(unique.values())
    pairs = [(query, document_text(candidate)) for candidate in candidates]
    if pairs:
        scores = model.predict(pairs, batch_size=batch_size, max_length=max_length,
                               show_progress_bar=False, convert_to_numpy=True)
    else:
        scores = np.array([], dtype=float)
    return rank_scored_candidates(candidates, scores, limit)


def rank_scored_candidates(candidates: list[dict], scores, limit: int = 10) -> list[dict]:
    unique = {}
    for candidate in candidates:
        unique[canonical_id(candidate)] = candidate
    candidates = list(unique.values())
    ranked = []
    for candidate, score in zip(candidates, scores):
        result = dict(candidate)
        result["canonical_id"] = canonical_id(candidate)
        result["reranker_score"] = float(score)
        ranked.append(result)
    ranked.sort(key=lambda item: (-item["reranker_score"], item["canonical_id"]))
    for rank, result in enumerate(ranked[:limit], 1):
        result["final_rank"] = rank
        result["rank"] = rank
    return ranked[:limit]
