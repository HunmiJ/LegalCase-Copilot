"""Evaluate Exact Keyword, BM25, Semantic, and RRF Hybrid retrieval."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hybrid_utils import DEFAULT_RRF_K, HybridRetriever, fuse_ranked_results, record_key
from search_laws import search as keyword_search

ROOT = Path(__file__).resolve().parents[1]
METHODS = ("exact_keyword", "bm25", "semantic", "hybrid")


def reciprocal_rank(results, relevant):
    for rank, item in enumerate(results, 1):
        if record_key(item) in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_5(results, relevant):
    gains = [1.0 if record_key(item) in relevant else 0.0 for item in results[:5]]
    dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
    ideal_count = min(len(relevant), 5)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return dcg / idcg if idcg else 0.0


def metrics(results, relevant):
    return {
        "recall_at_1": int(any(record_key(item) in relevant for item in results[:1])),
        "recall_at_3": int(any(record_key(item) in relevant for item in results[:3])),
        "recall_at_5": int(any(record_key(item) in relevant for item in results[:5])),
        "mrr": reciprocal_rank(results, relevant),
        "ndcg_at_5": ndcg_at_5(results, relevant),
    }


def summarize(rows):
    summary = {}
    for method in METHODS:
        method_rows = [row for row in rows if row["method"] == method]
        summary[method] = {metric: sum(row["metrics"][metric] for row in method_rows) / len(method_rows)
                           for metric in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")}
    return summary


def build_cache(queries, database, retriever, candidate_limit):
    record_lookup = {(record["source_file"], record["article_number"]): record for record in retriever.records}
    cache = []
    for query in queries:
        relevant_records = [record_lookup[(item["source_file"], item["article_number"])]
                            for item in query["relevant_articles"]]
        cache.append({
            "query": query,
            "relevant": {record_key(item) for item in relevant_records},
            "exact_keyword": [dict(row) for row in keyword_search(database, query["query"], candidate_limit)],
            "bm25": retriever.bm25.search(query["query"], candidate_limit),
            "semantic": retriever.semantic_search(query["query"], candidate_limit),
        })
    return cache


def evaluate_cached(cache, rrf_k, limit=10):
    rows = []
    for item in cache:
        query = item["query"]
        result_sets = {
            "exact_keyword": item["exact_keyword"][:limit],
            "bm25": item["bm25"][:limit],
            "semantic": item["semantic"][:limit],
            "hybrid": fuse_ranked_results(item["bm25"], item["semantic"], rrf_k, limit),
        }
        for method, results in result_sets.items():
            rows.append({"query_id": query["query_id"], "query": query["query"], "method": method,
                         "relevant_articles": query["relevant_articles"],
                         "relevant_canonical_ids": sorted(item["relevant"]),
                         "metrics": metrics(results, item["relevant"]),
                         "results": results})
    return rows, summarize(rows)


def first_relevant_rank(results, relevant):
    return next((item["rank"] for item in results if record_key(item) in relevant), None)


def complementarity(rows):
    by_query = {}
    for row in rows:
        by_query.setdefault(row["query_id"], {})[row["method"]] = row
    result = {"recall_at_5": {}, "recall_at_1": {}, "hybrid_new_rescues_at_5": [],
              "hybrid_new_rescues_at_1": [], "hybrid_degrades_at_5": [], "hybrid_degrades_at_1": []}
    for cutoff, metric_name in ((5, "recall_at_5"), (1, "recall_at_1")):
        categories = {"bm25_only": [], "semantic_only": [], "both_success": [], "both_fail": []}
        for query_id, methods in by_query.items():
            b = bool(methods["bm25"]["metrics"][metric_name])
            s = bool(methods["semantic"]["metrics"][metric_name])
            h = bool(methods["hybrid"]["metrics"][metric_name])
            if b and s: categories["both_success"].append(query_id)
            elif b: categories["bm25_only"].append(query_id)
            elif s: categories["semantic_only"].append(query_id)
            else: categories["both_fail"].append(query_id)
            if h and not b and not s: result[f"hybrid_new_rescues_at_{cutoff}"].append(query_id)
            if not h and (b or s): result[f"hybrid_degrades_at_{cutoff}"].append(query_id)
        result[metric_name] = categories
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", default=str(ROOT / "evaluation/retrieval_queries.json"))
    parser.add_argument("--database", default=str(ROOT / "data/processed/legal.db"))
    parser.add_argument("--data-dir", default=str(ROOT / "data/processed"))
    parser.add_argument("--output", default=str(ROOT / "evaluation/results/v0.3_retrieval_results.json"))
    parser.add_argument("--candidate-limit", type=int, default=20)
    parser.add_argument("--rrf-k", type=int, default=DEFAULT_RRF_K)
    args = parser.parse_args()
    queries = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    retriever = HybridRetriever(Path(args.data_dir))
    cache = build_cache(queries, Path(args.database), retriever, args.candidate_limit)
    rows, summary = evaluate_cached(cache, args.rrf_k)
    parameter_experiments = {}
    for rrf_k in (20, 60, 100):
        _, parameter_experiments[str(rrf_k)] = evaluate_cached(cache, rrf_k)
    report = {"model": "BAAI/bge-small-zh-v1.5", "query_count": len(queries),
              "candidate_limit": args.candidate_limit, "default_rrf_k": args.rrf_k,
              "summary": summary, "parameter_experiments": parameter_experiments,
              "complementarity": complementarity(rows), "queries": rows}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("method\tRecall@1\tRecall@3\tRecall@5\tMRR\tnDCG@5")
    for method, values in summary.items():
        print(f"{method}\t{values['recall_at_1']:.4f}\t{values['recall_at_3']:.4f}\t{values['recall_at_5']:.4f}\t{values['mrr']:.4f}\t{values['ndcg_at_5']:.4f}")
    print("\nRRF parameter experiments:")
    for rrf_k, values in parameter_experiments.items():
        print(f"k={rrf_k}\tRecall@5={values['hybrid']['recall_at_5']:.4f}\tMRR={values['hybrid']['mrr']:.4f}\tnDCG@5={values['hybrid']['ndcg_at_5']:.4f}")
    for focus_id in ("q01", "q19", "q27"):
        print(f"\nFOCUS {focus_id}")
        focus = [row for row in rows if row["query_id"] == focus_id]
        relevant = set(focus[0]["relevant_canonical_ids"])
        print("relevant=", focus[0]["relevant_articles"])
        for method in ("bm25", "semantic", "hybrid"):
            row = next(row for row in focus if row["method"] == method)
            print(method, "first_relevant_rank=", first_relevant_rank(row["results"], relevant),
                  "top10=", [(x["rank"], x["article_number"]) for x in row["results"][:10]])
    summary_path = output.with_name("v0.3_retrieval_summary.md")
    lines = ["# V0.3 Retrieval Evaluation", "", f"Benchmark queries: {len(queries)}", f"Candidate depth: {args.candidate_limit}", f"Default RRF k: {args.rrf_k}", "", "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 |", "|---|---:|---:|---:|---:|---:|"]
    for method, values in summary.items():
        lines.append(f"| {method} | {values['recall_at_1']:.4f} | {values['recall_at_3']:.4f} | {values['recall_at_5']:.4f} | {values['mrr']:.4f} | {values['ndcg_at_5']:.4f} |")
    lines += ["", "## RRF parameter experiments", "", "| k | Recall@5 | MRR | nDCG@5 |", "|---:|---:|---:|---:|"]
    for rrf_k, values in parameter_experiments.items():
        lines.append(f"| {rrf_k} | {values['hybrid']['recall_at_5']:.4f} | {values['hybrid']['mrr']:.4f} | {values['hybrid']['ndcg_at_5']:.4f} |")
    lines += ["", "## Complementarity", "", "```json", json.dumps(report["complementarity"], ensure_ascii=False, indent=2), "```"]
    for focus_id in ("q01", "q19", "q27"):
        lines += ["", f"## Focus query {focus_id}", ""]
        focus = [row for row in rows if row["query_id"] == focus_id]
        relevant = set(focus[0]["relevant_canonical_ids"])
        lines.append(f"Query: {focus[0]['query']}")
        lines.append(f"Relevant: {focus[0]['relevant_articles']}")
        for method in ("bm25", "semantic", "hybrid"):
            row = next(row for row in focus if row["method"] == method)
            lines += ["", f"### {method}", f"First relevant rank: {first_relevant_rank(row['results'], relevant)}", "", "| Rank | Article | Score | BM25 rank | Semantic rank |", "|---:|---|---:|---:|---:|"]
            for item in row["results"][:10]:
                score = item.get("rrf_score", item.get("bm25_score", item.get("similarity_score", 0.0)))
                lines.append(f"| {item['rank']} | {item['law_name']} {item['article_number']} | {score:.8f} | {item.get('bm25_rank', '')} | {item.get('semantic_rank', '')} |")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写入 {output} 和 {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
