"""Evaluate V0.1 keyword retrieval against V0.2 semantic retrieval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from search_laws import search as keyword_search
from search_semantic import search_semantic
from semantic_utils import load_model
from bm25_utils import BM25Retriever, load_records as load_bm25_records

ROOT = Path(__file__).resolve().parents[1]


def key(item: dict) -> tuple[str, str]:
    return item["source_file"], item["article_number"]


def reciprocal_rank(results: list[dict], relevant: set[tuple[str, str]]) -> float:
    for rank, item in enumerate(results, 1):
        if key(item) in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_5(results: list[dict], relevant: set[tuple[str, str]]) -> float:
    gains = [1.0 if key(item) in relevant else 0.0 for item in results[:5]]
    dcg = sum(gain / __import__("math").log2(rank + 1) for rank, gain in enumerate(gains, 1))
    ideal_count = min(len(relevant), 5)
    idcg = sum(1.0 / __import__("math").log2(rank + 1) for rank in range(1, ideal_count + 1))
    return dcg / idcg if idcg else 0.0


def evaluate(queries: list[dict], database: Path, data_dir: Path, limit: int = 10) -> dict:
    all_results = []
    model = load_model(local_files_only=True)
    bm25 = BM25Retriever(load_bm25_records(data_dir / "laws.jsonl"))
    for query in queries:
        relevant = {key(item) for item in query["relevant_articles"]}
        keyword = [dict(row) for row in keyword_search(database, query["query"], limit)]
        lexical = bm25.search(query["query"], limit)
        semantic = search_semantic(query["query"], limit, data_dir, model=model)
        for method, results in (("exact_keyword", keyword), ("bm25", lexical), ("semantic", semantic)):
            ranks = {1: 1, 3: 3, 5: 5}
            metrics = {f"recall_at_{k}": int(any(key(item) in relevant for item in results[:k])) for k in ranks.values()}
            metrics["mrr"] = reciprocal_rank(results, relevant)
            metrics["ndcg_at_5"] = ndcg_at_5(results, relevant)
            all_results.append({"query_id": query["query_id"], "query": query["query"],
                                "method": method, "relevant_articles": query["relevant_articles"],
                                "metrics": metrics, "results": results})
    summary = {}
    for method in ("exact_keyword", "bm25", "semantic"):
        rows = [row for row in all_results if row["method"] == method]
        summary[method] = {metric: sum(row["metrics"][metric] for row in rows) / len(rows)
                           for metric in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")}
    return {"model": "BAAI/bge-small-zh-v1.5", "query_count": len(queries),
            "summary": summary, "queries": all_results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", default=str(ROOT / "evaluation/retrieval_queries.json"))
    parser.add_argument("--database", default=str(ROOT / "data/processed/legal.db"))
    parser.add_argument("--data-dir", default=str(ROOT / "data/processed"))
    parser.add_argument("--output", default=str(ROOT / "evaluation/results/v0.2_retrieval_results.json"))
    args = parser.parse_args()
    queries = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    report = evaluate(queries, Path(args.database), Path(args.data_dir))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("method\tRecall@1\tRecall@3\tRecall@5\tMRR\tnDCG@5")
    for method, metrics in report["summary"].items():
        print(f"{method}\t{metrics['recall_at_1']:.4f}\t{metrics['recall_at_3']:.4f}\t{metrics['recall_at_5']:.4f}\t{metrics['mrr']:.4f}\t{metrics['ndcg_at_5']:.4f}")
    for focus_id in ("q01", "q19"):
        print(f"\nFOCUS {focus_id}")
        for row in [row for row in report["queries"] if row["query_id"] == focus_id]:
            print(row["method"], "relevant=", row["relevant_articles"])
            relevant = {key(item) for item in row["relevant_articles"]}
            first = next((item["rank"] for item in row["results"] if key(item) in relevant), None)
            print("first_relevant_rank=", first)
            print(" ".join(f"{item['rank']}:{item['article_number']}" for item in row["results"][:10]))
    summary_path = output.with_name("v0.2_retrieval_summary.md")
    lines = ["# V0.2 Retrieval Evaluation", "", f"Benchmark queries: {report['query_count']}", "", "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 |", "|---|---:|---:|---:|---:|---:|"]
    for method, metrics in report["summary"].items():
        lines.append(f"| {method} | {metrics['recall_at_1']:.4f} | {metrics['recall_at_3']:.4f} | {metrics['recall_at_5']:.4f} | {metrics['mrr']:.4f} | {metrics['ndcg_at_5']:.4f} |")
    lines += ["", "## Method notes", "", "- `exact_keyword` is the unchanged V0.1 FTS5 keyword search applied to the full natural-language query.", "- `bm25` tokenizes corpus and queries with jieba and uses rank-bm25; no query-specific mapping or hard-coded ranking rule is used.", "- `semantic` uses BAAI/bge-small-zh-v1.5 with cosine similarity."]
    for focus_id in ("q01", "q19"):
        lines += ["", f"## Focus query {focus_id}", ""]
        focus_rows = [row for row in report["queries"] if row["query_id"] == focus_id]
        if focus_rows: lines.append(f"Query: {focus_rows[0]['query']}")
        for row in focus_rows:
            relevant = {key(item) for item in row["relevant_articles"]}
            first = next((item["rank"] for item in row["results"] if key(item) in relevant), None)
            lines += ["", f"### {row['method']}", "", f"Relevant: {row['relevant_articles']}", f"First relevant rank: {first}", "", "| Rank | Article | Score |", "|---:|---|---:|"]
            for item in row["results"][:10]:
                score = item.get("bm25_score", item.get("similarity_score", ""))
                lines.append(f"| {item['rank']} | {item['law_name']} {item['article_number']} | {score:.6f} |")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写入 {output} 和 {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
