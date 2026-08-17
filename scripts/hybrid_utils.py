"""BM25 + BGE semantic retrieval fused with Reciprocal Rank Fusion."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from bm25_utils import BM25Retriever, load_records
from semantic_utils import cosine_scores, encode_query, load_model

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RRF_K = 60


def canonical_id(record: dict) -> str:
    """Return the stable laws.jsonl identity, with a safe legacy fallback."""
    if record.get("id"):
        return str(record["id"])
    return f"{record['source_file']}::{record['article_number']}"


def record_key(record: dict) -> str:
    return canonical_id(record)


def fuse_ranked_results(bm25_results: list[dict], semantic_results: list[dict],
                        rrf_k: int = DEFAULT_RRF_K, limit: int = 10) -> list[dict]:
    """Fuse two ranked result lists. Documents present in either list participate."""
    candidates = {}
    for result in bm25_results:
        item = candidates.setdefault(record_key(result), dict(result))
        item["canonical_id"] = record_key(result)
        item["bm25_rank"] = int(result["rank"])
        item["bm25_score"] = float(result["bm25_score"])
    for result in semantic_results:
        item = candidates.setdefault(record_key(result), dict(result))
        item["canonical_id"] = record_key(result)
        item["semantic_rank"] = int(result["rank"])
        item["semantic_similarity"] = float(result["similarity_score"])
        for field in ("id", "canonical_id", "law_name", "article_number", "article_content", "chapter", "source_file"):
            if field in result:
                item[field] = result[field]
    for item in candidates.values():
        score = 0.0
        if item.get("bm25_rank") is not None:
            score += 1.0 / (rrf_k + item["bm25_rank"])
        if item.get("semantic_rank") is not None:
            score += 1.0 / (rrf_k + item["semantic_rank"])
        item["rrf_score"] = score
        item.setdefault("bm25_rank", None)
        item.setdefault("bm25_score", None)
        item.setdefault("semantic_rank", None)
        item.setdefault("semantic_similarity", None)
    ranked = sorted(candidates.values(), key=lambda item: (-item["rrf_score"], record_key(item)))[:limit]
    for rank, item in enumerate(ranked, 1):
        item["hybrid_rank"] = rank
        item["rank"] = rank
    return ranked


class HybridRetriever:
    def __init__(self, data_dir: Path | None = None, model=None):
        self.data_dir = data_dir or ROOT / "data/processed"
        self.records = load_records(self.data_dir / "laws.jsonl")
        self.bm25 = BM25Retriever(self.records)
        self.embeddings = np.load(self.data_dir / "embeddings.npy")
        if len(self.records) != len(self.embeddings):
            raise ValueError("laws.jsonl and embeddings.npy have different row counts")
        self.model = model or load_model(local_files_only=True)

    def semantic_search(self, query: str, limit: int = 20) -> list[dict]:
        scores = cosine_scores(encode_query(self.model, query), self.embeddings)
        positions = np.argsort(-scores)[:limit]
        results = []
        for rank, position in enumerate(positions, 1):
            result = dict(self.records[int(position)])
            result["canonical_id"] = canonical_id(result)
            result["rank"] = rank
            result["similarity_score"] = float(scores[int(position)])
            results.append(result)
        return results

    def search(self, query: str, candidate_limit: int = 20, limit: int = 10,
               rrf_k: int = DEFAULT_RRF_K) -> list[dict]:
        bm25_results = self.bm25.search(query, candidate_limit)
        semantic_results = self.semantic_search(query, candidate_limit)
        return fuse_ranked_results(bm25_results, semantic_results, rrf_k, limit)
