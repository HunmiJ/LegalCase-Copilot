"""Multi-query candidate fusion and V0.5 reranking utilities."""

from __future__ import annotations

import time

from hybrid_utils import DEFAULT_RRF_K, HybridRetriever, canonical_id
from query_expansion import expanded_queries
from reranker_utils import rerank_candidates


def build_multi_query_candidates(retriever: HybridRetriever, queries: list[str],
                                 candidate_depth: int = 50, max_candidates: int = 150,
                                 rrf_k: int = DEFAULT_RRF_K) -> tuple[list[dict], dict]:
    """Retrieve each bounded query and aggregate candidates by canonical id."""
    candidates: dict[str, dict] = {}
    raw_count = 0
    for query_index, query in enumerate(queries):
        query_label = "original" if query_index == 0 else "expanded"
        bm25 = retriever.bm25.search(query, candidate_depth)
        semantic = retriever.semantic_search(query, candidate_depth)
        raw_count += len(bm25) + len(semantic)
        for source, results, score_field in (
            ("bm25", bm25, "bm25_score"),
            ("semantic", semantic, "similarity_score"),
        ):
            for result in results:
                key = canonical_id(result)
                item = candidates.setdefault(key, dict(result))
                item["canonical_id"] = key
                item.setdefault("matched_queries", [])
                if query not in item["matched_queries"]:
                    item["matched_queries"].append(query)
                item["from_original_query"] = item.get("from_original_query", False) or query_index == 0
                item["from_expanded_query"] = item.get("from_expanded_query", False) or query_index > 0
                ranks_key = f"{source}_ranks"
                scores_key = f"{source}_scores"
                item.setdefault(ranks_key, []).append({"query": query, "rank": int(result["rank"])})
                item.setdefault(scores_key, []).append({"query": query, "score": float(result[score_field])})
    for item in candidates.values():
        item["pre_rerank_score"] = sum(
            1.0 / (rrf_k + entry["rank"])
            for key in ("bm25_ranks", "semantic_ranks")
            for entry in item.get(key, [])
        )
        item["bm25_rank"] = min((entry["rank"] for entry in item.get("bm25_ranks", [])), default=None)
        item["semantic_rank"] = min((entry["rank"] for entry in item.get("semantic_ranks", [])), default=None)
        item["bm25_score"] = next((entry["score"] for entry in item.get("bm25_scores", []) if entry["query"] == queries[0]), None)
        item["semantic_similarity"] = next((entry["score"] for entry in item.get("semantic_scores", []) if entry["query"] == queries[0]), None)
    ranked = sorted(candidates.values(), key=lambda item: (-item["pre_rerank_score"], item["canonical_id"]))
    ranked = ranked[:max_candidates]
    for rank, item in enumerate(ranked, 1):
        item["pre_rerank_rank"] = rank
    stats = {
        "query_count": len(queries),
        "raw_candidate_count": raw_count,
        "unique_candidate_count": len(candidates),
        "reranking_candidate_count": len(ranked),
    }
    return ranked, stats


def multi_query_search(retriever: HybridRetriever, reranker, original_query: str,
                       structured: dict, candidate_depth: int = 50,
                       max_candidates: int = 150, limit: int = 10) -> dict:
    queries = expanded_queries(structured, original_query, limit=3)
    retrieval_start = time.perf_counter()
    candidates, stats = build_multi_query_candidates(retriever, queries, candidate_depth, max_candidates)
    retrieval_ms = (time.perf_counter() - retrieval_start) * 1000
    rerank_start = time.perf_counter()
    results = rerank_candidates(reranker, original_query, candidates, limit)
    rerank_ms = (time.perf_counter() - rerank_start) * 1000
    stats.update({
        "expanded_queries": queries,
        "retrieval_latency_ms": retrieval_ms,
        "reranking_latency_ms": rerank_ms,
        "total_latency_ms": retrieval_ms + rerank_ms,
        "results": results,
    })
    return stats
