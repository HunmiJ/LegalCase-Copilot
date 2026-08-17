"""CLI for V0.5 query understanding, multi-query retrieval and reranking."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from backend.llm import MockProvider, OpenAICompatibleProvider, QueryUnderstandingService
from reranker_utils import DEFAULT_CANDIDATE_DEPTH, load_reranker
from understood_utils import multi_query_search
from hybrid_utils import HybridRetriever


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--candidate-depth", type=int, default=DEFAULT_CANDIDATE_DEPTH)
    parser.add_argument("--max-candidates", type=int, default=150)
    parser.add_argument("--provider", choices=("mock", "real"), default="mock")
    args = parser.parse_args()
    provider = MockProvider() if args.provider == "mock" else OpenAICompatibleProvider()
    service = QueryUnderstandingService(provider, cache_path=ROOT / ".cache/query_understanding.json")
    structured = service.understand(args.query)
    retriever = HybridRetriever()
    reranker = load_reranker(local_files_only=True)
    report = multi_query_search(retriever, reranker, args.query, structured,
                                args.candidate_depth, args.max_candidates, args.limit)
    print("Query Understanding:")
    print(json.dumps(structured, ensure_ascii=False, indent=2))
    print("\nRetrieval stats:")
    for key in ("query_count", "raw_candidate_count", "unique_candidate_count", "reranking_candidate_count", "expanded_queries"):
        print(f"{key}: {report[key]}")
    for result in report["results"]:
        print(f"\n[{result['rank']}] reranker score={result['reranker_score']:.6f}")
        print(f"Canonical ID: {result['canonical_id']}")
        print(f"Matched queries: {result.get('matched_queries', [])}")
        print(f"BM25 ranks: {result.get('bm25_ranks', [])}")
        print(f"Semantic ranks: {result.get('semantic_ranks', [])}")
        print(f"{result['law_name']} {result['article_number']}")
        print(f"章节：{result.get('chapter')}")
        print(f"正文：{result['article_content']}")
        print(f"来源文件：{result['source_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
