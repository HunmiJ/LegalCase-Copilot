"""V0.5 benchmark for query understanding and multi-query reranking."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from backend.llm import MockProvider, QueryUnderstandingService
from hybrid_utils import HybridRetriever, canonical_id
from query_expansion import expanded_queries
from reranker_utils import build_candidate_pool, document_text, load_reranker, rank_scored_candidates
from understood_utils import build_multi_query_candidates
from evaluate_retrieval import metrics, resolve_relevant, summary


def rank_for(results: list[dict], relevant: set[str]) -> dict[str, int | None]:
    return {key: next((index for index, item in enumerate(results, 1)
                       if canonical_id(item) == key), None) for key in relevant}


def rerank_groups(reranker, groups: dict[str, tuple[str, list[dict]]]) -> tuple[dict[str, list[dict]], float]:
    pairs = []
    offsets = {}
    for key, (query, candidates) in groups.items():
        offsets[key] = (len(pairs), len(candidates))
        pairs.extend((query, document_text(candidate)) for candidate in candidates)
    start = time.perf_counter()
    scores = reranker.predict(pairs, batch_size=64, max_length=256,
                              show_progress_bar=False, convert_to_numpy=True) if pairs else np.array([])
    elapsed = (time.perf_counter() - start) * 1000
    output = {}
    for key, (offset, length) in offsets.items():
        output[key] = rank_scored_candidates(groups[key][1], scores[offset:offset + length], 10)
    return output, elapsed


def main() -> int:
    parser = __import__("argparse").ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "evaluation/results/v0.5_query_understanding_results.json"))
    parser.add_argument("--query-record-dir", default=str(ROOT / "evaluation/query_understanding_results"))
    args = parser.parse_args()
    queries = json.loads((ROOT / "evaluation/retrieval_queries.json").read_text(encoding="utf-8"))
    retriever = HybridRetriever()
    reranker = load_reranker(local_files_only=True)
    service = QueryUnderstandingService(MockProvider(), cache_path=ROOT / ".cache/query_understanding.json")
    understandings = []
    for query in queries:
        start = time.perf_counter()
        structured = service.understand(query["query"])
        understandings.append((structured, (time.perf_counter() - start) * 1000))

    groups: dict[str, tuple[str, list[dict]]] = {}
    v04_candidates = {}
    semantic_candidates = {}
    v05_candidates_20 = {}
    v05_candidates_50 = {}
    records = {}
    candidate_stats = {"20": [], "50": []}
    query_understanding_ms = []
    retrieval_ms = []
    for query, (structured, understanding_ms) in zip(queries, understandings):
        qid, text = query["query_id"], query["query"]
        relevant = resolve_relevant(query, retriever.records)
        query_understanding_ms.append(understanding_ms)
        expanded = expanded_queries(structured, text, 3)
        semantic = retriever.semantic_search(text, 50)
        v04 = build_candidate_pool(retriever, text, 50)
        multi20, stats20 = build_multi_query_candidates(retriever, expanded, 20, 150)
        retrieval_start = time.perf_counter()
        multi50, stats50 = build_multi_query_candidates(retriever, expanded, 50, 150)
        retrieval_ms.append((time.perf_counter() - retrieval_start) * 1000)
        semantic_candidates[qid] = semantic
        v04_candidates[qid] = v04
        v05_candidates_20[qid] = multi20
        v05_candidates_50[qid] = multi50
        groups[f"semantic:{qid}"] = (text, semantic)
        groups[f"v04:{qid}"] = (text, v04)
        groups[f"v05:{qid}"] = (text, multi50)
        candidate_stats["20"].append(stats20)
        candidate_stats["50"].append(stats50)
        records[qid] = {
            "original_query": text,
            "structured_understanding": structured,
            "expanded_queries": expanded,
            "relevant_articles": query["relevant_articles"],
            "relevant_canonical_ids": sorted(relevant),
            "original_retrieval": {
                "semantic_rank": rank_for(semantic, relevant),
                "candidate_recall_at_20": len(set(canonical_id(x) for x in semantic[:20]) & relevant) / len(relevant),
                "candidate_recall_at_50": len(set(canonical_id(x) for x in semantic[:50]) & relevant) / len(relevant),
            },
            "multi_query_candidates": {
                "at_20": {**stats20, "candidate_recall": len(set(canonical_id(x) for x in multi20) & relevant) / len(relevant)},
                "at_50": {**stats50, "candidate_recall": len(set(canonical_id(x) for x in multi50) & relevant) / len(relevant)},
                "candidate_rank_at_50": rank_for(multi50, relevant),
            },
            "query_understanding_latency_ms": understanding_ms,
            "multi_query_retrieval_latency_ms": retrieval_ms[-1],
        }
    reranked = {}
    rerank_elapsed_by_method = {}
    for prefix in ("semantic", "v04", "v05"):
        subset = {key: value for key, value in groups.items() if key.startswith(prefix + ":")}
        ranked_subset, elapsed = rerank_groups(reranker, subset)
        reranked.update(ranked_subset)
        rerank_elapsed_by_method[prefix] = elapsed

    method_rows = {"semantic_reranked": [], "v04_reranked": [], "v05_multi_query_reranked": []}
    for query in queries:
        qid, text = query["query_id"], query["query"]
        relevant = resolve_relevant(query, retriever.records)
        for method, key, candidates in (
            ("semantic_reranked", f"semantic:{qid}", semantic_candidates[qid]),
            ("v04_reranked", f"v04:{qid}", v04_candidates[qid]),
            ("v05_multi_query_reranked", f"v05:{qid}", v05_candidates_50[qid]),
        ):
            results = reranked[key]
            method_rows[method].append({"query_id": qid, "query": text,
                                        "method": method, "relevant_canonical_ids": sorted(relevant),
                                        "metrics": metrics(results, relevant), "results": results})
        records[qid]["final_retrieval_ranking"] = {
            "semantic_reranked": reranked[f"semantic:{qid}"],
            "v04_reranked": reranked[f"v04:{qid}"],
            "v05_multi_query_reranked": reranked[f"v05:{qid}"],
        }
        records[qid]["final_relevant_ranks"] = {
            method: rank_for(reranked[key], relevant)
            for method, key in (("semantic_reranked", f"semantic:{qid}"),
                                ("v04_reranked", f"v04:{qid}"),
                                ("v05_multi_query_reranked", f"v05:{qid}"))
        }

    for qid, record in records.items():
        path = Path(args.query_record_dir) / f"{qid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summaries = {method: summary(rows, [method])[method] for method, rows in method_rows.items()}
    v05_candidate_summary = {}
    for depth in ("20", "50"):
        stats = candidate_stats[depth]
        v05_candidate_summary[depth] = {
            "candidate_recall": sum(item["candidate_recall"] for qid, item in
                                     ((qid, records[qid]["multi_query_candidates"][f"at_{depth}"]) for qid in records)) / len(records),
            "average_query_count": sum(item["query_count"] for item in stats) / len(stats),
            "average_raw_candidates": sum(item["raw_candidate_count"] for item in stats) / len(stats),
            "average_unique_candidates": sum(item["unique_candidate_count"] for item in stats) / len(stats),
            "average_reranking_candidates": sum(item["reranking_candidate_count"] for item in stats) / len(stats),
        }
    comparison = {
        "semantic": json.loads((ROOT / "evaluation/results/v0.4_reranker_results.json").read_text(encoding="utf-8"))["baseline_summary"]["semantic"],
        "v04_reranked": summaries["v04_reranked"],
        "v05_multi_query_reranked": summaries["v05_multi_query_reranked"],
    }
    average_retrieval = sum(retrieval_ms) / len(retrieval_ms)
    result = {
        "benchmark_provider": "mock",
        "benchmark_is_real_llm": False,
        "model": "BAAI/bge-reranker-base",
        "query_count": len(queries),
        "frozen_queries": str(ROOT / "evaluation/retrieval_queries.json"),
        "v04_reference": json.loads((ROOT / "evaluation/results/v0.4_reranker_results.json").read_text(encoding="utf-8"))["selected_reranked_summary"],
        "comparison_summary": comparison,
        "ablation_summaries": summaries,
        "v05_candidate_summary": v05_candidate_summary,
        "average_query_understanding_latency_ms": sum(query_understanding_ms) / len(query_understanding_ms),
        "average_retrieval_latency_ms": average_retrieval,
        "average_reranker_batch_latency_ms": rerank_elapsed_by_method["v05"] / len(queries),
        "average_all_ablation_reranker_latency_ms": sum(rerank_elapsed_by_method.values()) / len(queries),
        "average_total_latency_ms": sum(query_understanding_ms) / len(query_understanding_ms) + average_retrieval + rerank_elapsed_by_method["v05"] / len(queries),
        "average_api_calls": 0,
        "query_records": records,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# V0.5 Query Understanding + Reranker Evaluation", "", "Provider: `deterministic mock` (not real LLM benchmark data)", f"Queries: {len(queries)}", "", "## Main comparison", "", "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 |", "|---|---:|---:|---:|---:|---:|"]
    for method, values in comparison.items():
        lines.append(f"| {method} | {values['recall_at_1']:.4f} | {values['recall_at_3']:.4f} | {values['recall_at_5']:.4f} | {values['mrr']:.4f} | {values['ndcg_at_5']:.4f} |")
    lines += ["", "## Ablation comparison", "", "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 |", "|---|---:|---:|---:|---:|---:|"]
    for method, values in summaries.items():
        lines.append(f"| {method} | {values['recall_at_1']:.4f} | {values['recall_at_3']:.4f} | {values['recall_at_5']:.4f} | {values['mrr']:.4f} | {values['ndcg_at_5']:.4f} |")
    lines += ["", "## Candidate recall", "", "| Multi-query depth | Candidate Recall | Avg queries | Avg raw candidates | Avg unique candidates | Avg reranking candidates |", "|---:|---:|---:|---:|---:|---:|"]
    for depth, values in v05_candidate_summary.items():
        lines.append(f"| @{depth} | {values['candidate_recall']:.4f} | {values['average_query_count']:.2f} | {values['average_raw_candidates']:.2f} | {values['average_unique_candidates']:.2f} | {values['average_reranking_candidates']:.2f} |")
    lines += ["", "## Latency", "", f"- Average query-understanding latency: {result['average_query_understanding_latency_ms']:.3f} ms (mock)", f"- Average multi-query retrieval latency: {result['average_retrieval_latency_ms']:.3f} ms", f"- Average V0.5 reranker latency per query: {result['average_reranker_batch_latency_ms']:.3f} ms", f"- Combined latency for V0.5: {result['average_total_latency_ms']:.3f} ms", f"- All-ablation reranker work per query: {result['average_all_ablation_reranker_latency_ms']:.3f} ms", "- Real provider API calls: 0", "", "## Focus queries", ""]
    for qid in ("q01", "q19", "q27"):
        record = records[qid]
        lines += [f"### {qid}: {record['original_query']}", "", "```json", json.dumps({"issue": record["structured_understanding"]["issue"], "legal_concepts": record["structured_understanding"]["legal_concepts"], "search_queries": record["expanded_queries"]}, ensure_ascii=False, indent=2), "```", f"- Multi-query candidate recall@50: {record['multi_query_candidates']['at_50']['candidate_recall']:.4f}", f"- Final relevant ranks: {record['final_relevant_ranks']}", ""]
    summary_path = output.with_name("v0.5_query_understanding_summary.md")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("method\tRecall@1\tRecall@3\tRecall@5\tMRR\tnDCG@5")
    for method, values in summaries.items():
        print(f"{method}\t{values['recall_at_1']:.4f}\t{values['recall_at_3']:.4f}\t{values['recall_at_5']:.4f}\t{values['mrr']:.4f}\t{values['ndcg_at_5']:.4f}")
    for depth, values in v05_candidate_summary.items():
        print(f"candidate_recall@{depth}\t{values['candidate_recall']:.4f}\tavg_unique={values['average_unique_candidates']:.2f}")
    print(f"Wrote {output} and {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
