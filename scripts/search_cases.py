"""CLI for unified local-first case search."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.cases.search_service import UnifiedCaseSearchService
from backend.cases.sources.people_court_library import PeopleCourtCaseLibraryProvider
from backend.cases.sources.supreme_court import SupremeCourtOfficialProvider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--mode", choices=("bm25", "semantic", "hybrid", "reranked"), default="hybrid")
    args = parser.parse_args()
    service = UnifiedCaseSearchService(official_providers=[PeopleCourtCaseLibraryProvider(), SupremeCourtOfficialProvider()])
    results = service.search(args.query, args.top_k, mode=args.mode)
    print(f"查询：{args.query}")
    for rank, result in enumerate(results, 1):
        print(f"\n[{rank}] {result.title}")
        print(f"case_id：{result.case_id}")
        print(f"入库编号：{result.database_case_number or 'null'}")
        print(f"案号：{result.case_number or 'null'}")
        print(f"关键词：{'、'.join(result.keywords) if result.keywords else 'null'}")
        print(f"争议焦点：{result.dispute_focus or 'null'}")
        print(f"裁判要旨：{result.case_gist or 'null'}")
        print(f"来源：{result.source_name}")
        print(f"source URL：{result.source_url or 'null'}")
        if args.mode == "hybrid":
            print(f"hybrid score：{result.hybrid_score:.6f}")
            print(f"BM25 score：{result.bm25_score if result.bm25_score is not None else 'null'}")
            print(f"BM25 rank：{result.bm25_rank or 'null'}")
            print(f"Semantic rank：{result.semantic_rank or 'null'}")
        elif args.mode == "reranked":
            print(f"reranker score：{result.reranker_score:.6f}")
            print(f"original hybrid rank：{result.original_hybrid_rank or 'null'}")
            print(f"hybrid score：{result.hybrid_score:.6f}")
            print(f"reranker status：{service.last_reranker_status}")
        else:
            print(f"BM25 score：{result.score:.6f}")
        print(f"retrieval_source：{result.retrieval_source}")


if __name__ == "__main__":
    main()
