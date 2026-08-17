"""CLI for Cross-Encoder reranked legal retrieval."""

from __future__ import annotations

import argparse

from hybrid_utils import HybridRetriever
from reranker_utils import DEFAULT_CANDIDATE_DEPTH, load_reranker, build_candidate_pool, rerank_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="BM25 + Semantic + Cross-Encoder 法律检索")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--candidate-depth", type=int, default=DEFAULT_CANDIDATE_DEPTH)
    args = parser.parse_args()
    retriever = HybridRetriever()
    model = load_reranker(local_files_only=True)
    candidates = build_candidate_pool(retriever, args.query, args.candidate_depth)
    for result in rerank_candidates(model, args.query, candidates, args.limit):
        print(f"\n[{result['final_rank']}] reranker score={result['reranker_score']:.6f}")
        print(f"Canonical ID：{result['canonical_id']}")
        print(f"BM25 rank={result.get('bm25_rank')} | Semantic rank={result.get('semantic_rank')}")
        print(result["law_name"])
        print(result["article_number"])
        print(f"章节：{result.get('chapter')}")
        print(f"正文：{result['article_content']}")
        print(f"来源文件：{result['source_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
