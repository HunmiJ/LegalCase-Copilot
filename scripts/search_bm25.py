"""Chinese BM25 lexical search over article-level law records."""

from __future__ import annotations

import argparse

from bm25_utils import ROOT, BM25Retriever, load_records, tokenize


def main() -> int:
    parser = argparse.ArgumentParser(description="中文法律 BM25 检索")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    retriever = BM25Retriever(load_records())
    print(f"查询：{args.query}")
    print(f"分词：{' / '.join(tokenize(args.query))}")
    for result in retriever.search(args.query, args.limit):
        print(f"\n[{result['rank']}] BM25 score={result['bm25_score']:.6f}")
        print(result["law_name"])
        print(result["article_number"])
        print(f"章节：{result.get('chapter')}")
        print(f"正文：{result['article_content']}")
        print(f"来源文件：{result['source_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
