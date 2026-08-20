"""CLI for local semantic case retrieval."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.cases.sources.semantic_local import LocalSemanticCaseProvider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    results = LocalSemanticCaseProvider().search(args.query, args.top_k)
    print(f"查询：{args.query}")
    for rank, result in enumerate(results, 1):
        print(f"\n[{rank}] semantic_score={result.semantic_score:.6f}")
        print(result.title)
        print(f"case_id：{result.case_id}")
        print(f"入库编号：{result.database_case_number or 'null'}")
        print(f"关键词：{'、'.join(result.keywords) if result.keywords else 'null'}")
        print(f"争议焦点：{result.dispute_focus or 'null'}")
        print(f"裁判要旨：{result.case_gist or 'null'}")
        print(f"来源：{result.source_name}")
        print(f"source URL：{result.source_url or 'null'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
