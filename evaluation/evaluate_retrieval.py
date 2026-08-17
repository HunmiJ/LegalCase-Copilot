"""V0.4 benchmark: baseline retrieval plus Cross-Encoder reranking."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hybrid_utils import DEFAULT_RRF_K, HybridRetriever, fuse_ranked_results, record_key
from reranker_utils import build_candidate_pool, document_text, load_reranker, rank_scored_candidates
from search_laws import search as exact_search

ROOT = Path(__file__).resolve().parents[1]
DEPTHS = (20, 50, 100)


def metrics(results, relevant):
    gains = [1.0 if record_key(item) in relevant else 0.0 for item in results[:5]]
    dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
    ideal_count = min(len(relevant), 5)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return {
        "recall_at_1": int(any(record_key(item) in relevant for item in results[:1])),
        "recall_at_3": int(any(record_key(item) in relevant for item in results[:3])),
        "recall_at_5": int(any(record_key(item) in relevant for item in results[:5])),
        "mrr": next((1.0 / rank for rank, item in enumerate(results, 1) if record_key(item) in relevant), 0.0),
        "ndcg_at_5": dcg / idcg if idcg else 0.0,
    }


def summary(rows, methods):
    output = {}
    for method in methods:
        selected = [row for row in rows if row["method"] == method]
        output[method] = {metric: sum(row["metrics"][metric] for row in selected) / len(selected)
                          for metric in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")}
    return output


def resolve_relevant(query, records):
    lookup = {(record["source_file"], record["article_number"]): record for record in records}
    return {record_key(lookup[(item["source_file"], item["article_number"])])
            for item in query["relevant_articles"]}


def first_rank(results, relevant):
    return next((item.get("final_rank", item.get("rank")) for item in results if record_key(item) in relevant), None)


def run_baselines(queries, database, retriever, depth=20):
    rows = []
    for query in queries:
        relevant = resolve_relevant(query, retriever.records)
        exact = [dict(row) for row in exact_search(database, query["query"], 10)]
        bm25 = retriever.bm25.search(query["query"], depth)[:10]
        semantic = retriever.semantic_search(query["query"], depth)[:10]
        hybrid = fuse_ranked_results(retriever.bm25.search(query["query"], depth),
                                     retriever.semantic_search(query["query"], depth), DEFAULT_RRF_K, 10)
        for method, results in (("exact_keyword", exact), ("bm25", bm25), ("semantic", semantic), ("hybrid", hybrid)):
            rows.append({"query_id": query["query_id"], "query": query["query"], "method": method,
                         "relevant_articles": query["relevant_articles"],
                         "relevant_canonical_ids": sorted(relevant), "metrics": metrics(results, relevant),
                         "results": results})
    return rows


def run_reranker_depth(queries, retriever, reranker, depth):
    rows = []
    prepared = []
    total_candidates = 0
    candidate_article_hits = 0
    candidate_article_total = 0
    retrieval_ms = []
    rerank_ms = []
    total_ms = []
    errors = {"candidate_miss": [], "reranking_miss": [], "success": []}
    for query in queries:
        relevant = resolve_relevant(query, retriever.records)
        retrieval_start = time.perf_counter()
        candidates = build_candidate_pool(retriever, query["query"], depth, DEFAULT_RRF_K)
        retrieval_elapsed = (time.perf_counter() - retrieval_start) * 1000
        retrieval_ms.append(retrieval_elapsed)
        total_candidates += len(candidates)
        candidate_hits = len({record_key(item) for item in candidates} & relevant)
        candidate_article_hits += candidate_hits
        candidate_article_total += len(relevant)
        prepared.append((query, relevant, candidates, retrieval_elapsed, candidate_hits))
    all_pairs = [(query["query"], document_text(candidate)) for query, _, candidates, _, _ in prepared for candidate in candidates]
    rerank_start = time.perf_counter()
    all_scores = reranker.predict(all_pairs, batch_size=64, max_length=256,
                                  show_progress_bar=False, convert_to_numpy=True) if all_pairs else []
    total_rerank_elapsed = (time.perf_counter() - rerank_start) * 1000
    average_rerank_elapsed = total_rerank_elapsed / len(queries)
    score_offset = 0
    for query, relevant, candidates, retrieval_elapsed, candidate_hits in prepared:
        candidate_scores = all_scores[score_offset:score_offset + len(candidates)]
        score_offset += len(candidates)
        reranked = rank_scored_candidates(candidates, candidate_scores, 10)
        total_elapsed = retrieval_elapsed + average_rerank_elapsed
        rerank_ms.append(average_rerank_elapsed)
        total_ms.append(total_elapsed)
        if candidate_hits == 0:
            errors["candidate_miss"].append(query["query_id"])
        elif not any(record_key(item) in relevant for item in reranked[:5]):
            errors["reranking_miss"].append(query["query_id"])
        else:
            errors["success"].append(query["query_id"])
        rows.append({"query_id": query["query_id"], "query": query["query"], "method": "reranked",
                     "candidate_depth": depth, "relevant_articles": query["relevant_articles"],
                     "relevant_canonical_ids": sorted(relevant), "candidate_count": len(candidates),
                     "candidate_recall": candidate_hits / len(relevant),
                     "retrieval_latency_ms": retrieval_elapsed, "reranking_latency_ms": average_rerank_elapsed,
                     "total_latency_ms": total_elapsed, "metrics": metrics(reranked, relevant),
                     "results": reranked})
    values = summary(rows, ["reranked"])["reranked"]
    values.update({"average_candidate_count": total_candidates / len(queries),
                   "average_candidate_recall": candidate_article_hits / candidate_article_total,
                   "average_retrieval_latency_ms": sum(retrieval_ms) / len(retrieval_ms),
                   "average_reranking_latency_ms": sum(rerank_ms) / len(rerank_ms),
                   "average_total_latency_ms": sum(total_ms) / len(total_ms),
                   "errors": errors})
    return rows, values


def choose_depth(experiments):
    return max(experiments, key=lambda depth: (experiments[depth]["recall_at_5"],
                                                experiments[depth]["mrr"],
                                                experiments[depth]["ndcg_at_5"],
                                                -experiments[depth]["average_total_latency_ms"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", default=str(ROOT / "evaluation/retrieval_queries.json"))
    parser.add_argument("--database", default=str(ROOT / "data/processed/legal.db"))
    parser.add_argument("--data-dir", default=str(ROOT / "data/processed"))
    parser.add_argument("--output", default=str(ROOT / "evaluation/results/v0.4_reranker_results.json"))
    args = parser.parse_args()
    queries = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    retriever = HybridRetriever(Path(args.data_dir))
    reranker = load_reranker(local_files_only=True)
    baseline_rows = run_baselines(queries, Path(args.database), retriever)
    experiments = {}
    reranked_rows = {}
    for depth in DEPTHS:
        rows, values = run_reranker_depth(queries, retriever, reranker, depth)
        experiments[str(depth)] = values
        reranked_rows[str(depth)] = rows
    selected_depth = int(choose_depth(experiments))
    selected_rows = reranked_rows[str(selected_depth)]
    report = {"model": "BAAI/bge-reranker-base", "query_count": len(queries),
              "default_rrf_k": DEFAULT_RRF_K, "selected_candidate_depth": selected_depth,
              "baseline_summary": summary(baseline_rows, ["exact_keyword", "bm25", "semantic", "hybrid"]),
              "candidate_depth_experiments": experiments, "selected_reranked_summary": experiments[str(selected_depth)],
              "baseline_queries": baseline_rows, "reranked_queries": selected_rows,
              "all_reranked_queries_by_depth": reranked_rows}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("method\tRecall@1\tRecall@3\tRecall@5\tMRR\tnDCG@5")
    for method, values in report["baseline_summary"].items():
        print(f"{method}\t{values['recall_at_1']:.4f}\t{values['recall_at_3']:.4f}\t{values['recall_at_5']:.4f}\t{values['mrr']:.4f}\t{values['ndcg_at_5']:.4f}")
    values = report["selected_reranked_summary"]
    print(f"reranked@{selected_depth}\t{values['recall_at_1']:.4f}\t{values['recall_at_3']:.4f}\t{values['recall_at_5']:.4f}\t{values['mrr']:.4f}\t{values['ndcg_at_5']:.4f}")
    print("\nCandidate depth experiments:")
    for depth, values in experiments.items():
        print(f"{depth}+{depth}\tRecall@5={values['recall_at_5']:.4f}\tMRR={values['mrr']:.4f}\tCandidates={values['average_candidate_count']:.2f}\tRerank ms={values['average_reranking_latency_ms']:.2f}")
    for focus_id in ("q01", "q19", "q27"):
        print(f"\nFOCUS {focus_id} selected depth={selected_depth}")
        row = next(item for item in selected_rows if item["query_id"] == focus_id)
        relevant = set(row["relevant_canonical_ids"])
        print("relevant=", row["relevant_articles"])
        print("candidate_count=", row["candidate_count"], "candidate_recall=", row["candidate_recall"])
        print("reranker ranks=", [(x["final_rank"], x["article_number"], x["canonical_id"], x["reranker_score"], x.get("bm25_rank"), x.get("semantic_rank")) for x in row["results"][:10]])
        print("first_relevant_rank=", first_rank(row["results"], relevant))
    summary_path = output.with_name("v0.4_reranker_summary.md")
    lines = ["# V0.4 Reranker Evaluation", "", f"Model: `BAAI/bge-reranker-base`", f"Benchmark queries: {len(queries)}", f"Selected candidate depth: {selected_depth}+{selected_depth}", "", "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 |", "|---|---:|---:|---:|---:|---:|"]
    for method, values in report["baseline_summary"].items():
        lines.append(f"| {method} | {values['recall_at_1']:.4f} | {values['recall_at_3']:.4f} | {values['recall_at_5']:.4f} | {values['mrr']:.4f} | {values['ndcg_at_5']:.4f} |")
    selected_values = report["selected_reranked_summary"]
    lines.append(f"| reranked@{selected_depth} | {selected_values['recall_at_1']:.4f} | {selected_values['recall_at_3']:.4f} | {selected_values['recall_at_5']:.4f} | {selected_values['mrr']:.4f} | {selected_values['ndcg_at_5']:.4f} |")
    lines += ["", "## Candidate depth experiments", "", "| Depth | Recall@5 | MRR | nDCG@5 | Avg candidates | Avg rerank ms | Avg total ms |", "|---:|---:|---:|---:|---:|---:|---:|"]
    for depth, values in experiments.items():
        lines.append(f"| {depth}+{depth} | {values['recall_at_5']:.4f} | {values['mrr']:.4f} | {values['ndcg_at_5']:.4f} | {values['average_candidate_count']:.2f} | {values['average_reranking_latency_ms']:.2f} | {values['average_total_latency_ms']:.2f} |")
    lines += ["", "## Selected-depth error classification", "", "```json", json.dumps(selected_values["errors"], ensure_ascii=False, indent=2), "```"]
    for focus_id in ("q01", "q19", "q27"):
        row = next(item for item in selected_rows if item["query_id"] == focus_id)
        relevant = set(row["relevant_canonical_ids"])
        lines += ["", f"## Focus query {focus_id}", "", f"Query: {row['query']}", f"Relevant: {row['relevant_articles']}", f"Candidate count: {row['candidate_count']}", f"Candidate recall: {row['candidate_recall']}", f"First reranker relevant rank: {first_rank(row['results'], relevant)}", "", "| Rank | Article | Canonical ID | Reranker score | BM25 rank | Semantic rank |", "|---:|---|---|---:|---:|---:|"]
        for item in row["results"][:10]:
            lines.append(f"| {item['final_rank']} | {item['law_name']} {item['article_number']} | {item['canonical_id']} | {item['reranker_score']:.6f} | {item.get('bm25_rank', '')} | {item.get('semantic_rank', '')} |")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写入 {output} 和 {summary_path}")


if __name__ == "__main__":
    raise SystemExit(main())
