"""CLI for BM25 + BGE semantic retrieval with RRF fusion."""

from __future__ import annotations

import argparse

from hybrid_utils import DEFAULT_RRF_K, HybridRetriever


def main() -> int:
    parser = argparse.ArgumentParser(description="BM25 + Semantic Hybrid RRF 检索")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--candidates", type=int, default=20)
    parser.add_argument("--rrf-k", type=int, default=DEFAULT_RRF_K)
    args = parser.parse_args()
    retriever = HybridRetriever()
    print(f"查询：{args.query}")
    print(f"RRF k={args.rrf_k}，BM25/Semantic candidates={args.candidates}")
    for result in retriever.search(args.query, args.candidates, args.limit, args.rrf_k):
        print(f"\n[{result['hybrid_rank']}] RRF score={result['rrf_score']:.8f}")
        print(f"BM25 rank={result['bm25_rank']} score={result['bm25_score']}")
        print(f"Semantic rank={result['semantic_rank']} similarity={result['semantic_similarity']}")
        print(f"Canonical ID：{result['canonical_id']}")
        print(result["law_name"])
        print(result["article_number"])
        print(f"章节：{result.get('chapter')}")
        print(f"正文：{result['article_content']}")
        print(f"来源文件：{result['source_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
