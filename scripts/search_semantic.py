"""Semantic search over article embeddings."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from semantic_utils import ROOT, cosine_scores, encode_query, load_model, load_records


def search_semantic(query: str, limit: int = 10, database_dir: Path | None = None, model=None) -> list[dict]:
    base = database_dir or ROOT / "data/processed"
    records = load_records(base / "laws.jsonl")
    embeddings = np.load(base / "embeddings.npy")
    if len(records) != len(embeddings):
        raise ValueError("laws.jsonl and embeddings.npy have different row counts")
    model = model or load_model(local_files_only=True)
    scores = cosine_scores(encode_query(model, query), embeddings)
    positions = np.argsort(-scores)[:limit]
    results = []
    for position in positions:
        record = dict(records[int(position)])
        record["similarity_score"] = float(scores[int(position)])
        record["rank"] = len(results) + 1
        results.append(record)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="中文法律语义检索")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    print(f"查询：{args.query}")
    for result in search_semantic(args.query, args.limit):
        print(f"\n[{result['rank']}] similarity={result['similarity_score']:.6f}")
        print(result["law_name"])
        print(result["article_number"])
        print(f"章节：{result.get('chapter')}")
        print(f"正文：{result['article_content']}")
        print(f"来源文件：{result['source_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
