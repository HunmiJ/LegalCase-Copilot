"""V0.7.7 blind case reranker validation and descriptive full benchmark."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.cases.search.reranker import DEFAULT_CANDIDATE_DEPTH, load_case_reranker, rerank
from backend.cases.sources.hybrid_local import LocalHybridCaseProvider
from evaluation.case_retrieval.metrics import percentile

QUERIES = ROOT / "evaluation/v077_reranker_validation_queries.json"
QUERY_HASH = ROOT / "evaluation/v077_reranker_validation_queries.sha256"
CORPUS = ROOT / "data/processed/cases/cases.jsonl"
RESULTS = ROOT / "evaluation/v077_reranker_results.json"
METRICS = ROOT / "evaluation/v077_reranker_metrics.json"
SUMMARY = ROOT / "evaluation/v077_reranker_summary.md"


def metric_at(ranks: list[str], relevant: set[str], k: int) -> dict:
    visible = ranks[:k]
    first = next((i + 1 for i, case_id in enumerate(visible) if case_id in relevant), None)
    ideal = min(len(relevant), k)
    dcg = sum(1 / __import__("math").log2(i + 2) for i, case_id in enumerate(visible) if case_id in relevant)
    idcg = sum(1 / __import__("math").log2(i + 2) for i in range(ideal))
    return {"first_relevant_rank": first, "recall": float(first is not None), "mrr": 1 / first if first else 0.0,
            "ndcg": dcg / idcg if idcg else 0.0}


def aggregate(rows: list[dict], k: int) -> dict[str, float]:
    return {
        "Recall@1": sum(row["first_relevant_rank"] == 1 for row in rows) / len(rows),
        "Recall@3": sum(row["first_relevant_rank"] is not None and row["first_relevant_rank"] <= 3 for row in rows) / len(rows),
        "Recall@5": sum(row["first_relevant_rank"] is not None and row["first_relevant_rank"] <= 5 for row in rows) / len(rows),
        "MRR": sum(row["mrr"] for row in rows) / len(rows),
        f"nDCG@{k}": sum(row["ndcg"] for row in rows) / len(rows),
    }


def rank_payload(results: list, relevant: set[str], primary: str, depth: int) -> dict:
    ids = [item.case_id for item in results]
    metric = metric_at(ids, relevant, depth)
    return {"top": [{"rank": i + 1, "case_id": item.case_id, "title": item.title,
                      "reranker_score": item.reranker_score, "original_hybrid_rank": item.original_hybrid_rank,
                      "hybrid_score": item.hybrid_score, "source_name": item.source_name,
                      "source_url": item.source_url, "source_file": item.source_file}
                     for i, item in enumerate(results)],
            "primary_rank": next((i + 1 for i, case_id in enumerate(ids) if case_id == primary), None),
            "first_relevant_rank": metric["first_relevant_rank"], "metrics": metric}


def latency_summary(values: list[float]) -> dict[str, float]:
    return {"average": sum(values) / len(values), "p50": percentile(values, .5), "p95": percentile(values, .95)}


def main() -> None:
    records = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]
    queries = json.loads(QUERIES.read_text(encoding="utf-8"))
    if len(records) != 19 or len(queries) != 12 or len({row["query_id"] for row in queries}) != 12:
        raise ValueError("reranker validation requires 19 cases and 12 unique queries")
    corpus_ids = {record["case_id"] for record in records}
    for row in queries:
        if row["primary_case_id"] not in corpus_ids or not set(row["relevant_case_ids"]).issubset(corpus_ids):
            raise ValueError(f"invalid case label in {row['query_id']}")
        if row["primary_case_id"] not in row["relevant_case_ids"]:
            raise ValueError(f"primary case is not relevant in {row['query_id']}")
    query_digest = hashlib.sha256(QUERIES.read_bytes()).hexdigest()
    if query_digest != QUERY_HASH.read_text(encoding="utf-8").strip():
        raise ValueError("reranker validation query hash mismatch")

    hybrid = LocalHybridCaseProvider()
    load_start = time.perf_counter(); model = load_case_reranker(local_files_only=True); model_load_ms = (time.perf_counter() - load_start) * 1000
    validation_rows = []
    for query in queries:
        relevant = set(query["relevant_case_ids"])
        start = time.perf_counter(); hybrid_top10 = hybrid.search(query["query"], 10); hybrid_ms = (time.perf_counter() - start) * 1000
        candidates = hybrid_top10[:DEFAULT_CANDIDATE_DEPTH]
        candidate_payload = [{"rank": i + 1, "case_id": item.case_id, "title": item.title,
                              "hybrid_score": item.hybrid_score, "bm25_rank": item.bm25_rank,
                              "semantic_rank": item.semantic_rank, "source_name": item.source_name,
                              "source_url": item.source_url, "source_file": item.source_file}
                             for i, item in enumerate(candidates)]
        start = time.perf_counter(); reranked = rerank(model, query["query"], candidates, DEFAULT_CANDIDATE_DEPTH); rerank_ms = (time.perf_counter() - start) * 1000
        validation_rows.append({**{key: query[key] for key in ("query_id", "query", "primary_case_id", "relevant_case_ids", "topic", "difficulty")},
                                "candidate_depth": DEFAULT_CANDIDATE_DEPTH, "hybrid": {"top": candidate_payload, "primary_rank": next((i + 1 for i, item in enumerate(candidates) if item.case_id == query["primary_case_id"]), None), "metrics": metric_at([item.case_id for item in candidates], relevant, 3)},
                                "reranked": rank_payload(reranked, relevant, query["primary_case_id"], 3),
                                "latency_ms": {"hybrid": hybrid_ms, "reranker": rerank_ms, "total": hybrid_ms + rerank_ms}})

    def method_stats(rows: list[dict], method: str, k: int, latency_key: str | None = None) -> dict:
        metric_rows = [row[method]["metrics"] for row in rows]
        latencies = [row["latency_ms"][latency_key or method] for row in rows]
        return {"count": len(rows), "metrics": aggregate(metric_rows, k), "latency_ms": latency_summary(latencies)}

    fixed = [row["query_id"] for row in validation_rows if row["hybrid"]["primary_rank"] != 1 and row["reranked"]["primary_rank"] == 1]
    broken = [row["query_id"] for row in validation_rows if row["hybrid"]["primary_rank"] == 1 and row["reranked"]["primary_rank"] != 1]
    unchanged = [row["query_id"] for row in validation_rows if row["query_id"] not in fixed and row["query_id"] not in broken]

    # Full-30 is explicitly descriptive: it runs only after the blind validation.
    frozen_full = json.loads((ROOT / "evaluation/case_retrieval_queries.json").read_text(encoding="utf-8"))
    full_rows = []
    for query in frozen_full:
        relevant = set(query["relevant_case_ids"])
        start = time.perf_counter(); hybrid_top10 = hybrid.search(query["query"], 10); hybrid_ms = (time.perf_counter() - start) * 1000
        candidates = hybrid_top10[:DEFAULT_CANDIDATE_DEPTH]
        start = time.perf_counter(); reranked = rerank(model, query["query"], candidates, DEFAULT_CANDIDATE_DEPTH); rerank_ms = (time.perf_counter() - start) * 1000
        full_rows.append({"query_id": query["query_id"], "query": query["query"], "primary_case_id": query["primary_case_id"], "relevant_case_ids": query["relevant_case_ids"],
                          "hybrid": rank_payload(hybrid_top10, relevant, query["primary_case_id"], 5),
                          "reranked": rank_payload(reranked, relevant, query["primary_case_id"], 5),
                          "latency_ms": {"hybrid": hybrid_ms, "reranker": rerank_ms, "total": hybrid_ms + rerank_ms}})

    metrics = {"model": "BAAI/bge-reranker-base", "candidate_depth": 3, "validation_query_count": 12,
               "validation_query_sha256": query_digest, "model_load_ms": model_load_ms,
               "validation": {"hybrid": method_stats(validation_rows, "hybrid", 3), "reranked": method_stats(validation_rows, "reranked", 3, "reranker"),
                              "fixed_queries": fixed, "broken_queries": broken, "unchanged_queries": unchanged,
                              "net_top1_gain": len(fixed) - len(broken)},
               "full_30_descriptive": {"hybrid": method_stats(full_rows, "hybrid", 5), "reranked": method_stats(full_rows, "reranked", 5, "reranker")},
               "limitations": ["Full-30 was used during earlier retrieval development and is descriptive, not a new independent test.", "Reranker sees only the frozen Hybrid Top3."]}
    RESULTS.write_text(json.dumps({"validation": validation_rows, "full_30_descriptive": full_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    METRICS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# V0.7.7 Cross-Encoder Case Reranker", "", "Model: `BAAI/bge-reranker-base`; candidate depth: 3; validation queries: 12.", "", "## Blind validation", "", "| Method | Recall@1 | Recall@3 | MRR | nDCG@3 | Avg ms | P50 ms | P95 ms |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for method in ("hybrid", "reranked"):
        value = metrics["validation"][method]; m, l = value["metrics"], value["latency_ms"]
        lines.append(f"| {method} | {m['Recall@1']:.4f} | {m['Recall@3']:.4f} | {m['MRR']:.4f} | {m['nDCG@3']:.4f} | {l['average']:.2f} | {l['p50']:.2f} | {l['p95']:.2f} |")
    lines += ["", f"Fixed: {len(fixed)}; broken: {len(broken)}; unchanged: {len(unchanged)}; net Top1 gain: {len(fixed)-len(broken)}.", "", "## Full-30 descriptive comparison", "", "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 | Avg total ms |", "|---|---:|---:|---:|---:|---:|---:|"]
    for method in ("hybrid", "reranked"):
        value = metrics["full_30_descriptive"][method]; m, l = value["metrics"], value["latency_ms"]
        lines.append(f"| {method} | {m['Recall@1']:.4f} | {m['Recall@3']:.4f} | {m['Recall@5']:.4f} | {m['MRR']:.4f} | {m['nDCG@5']:.4f} | {l['average']:.2f} |")
    lines += ["", "The V0.7.6 held-out Test is not relabeled as a new V0.7.7 independent test. No query-specific rule, label change, or corpus change was used."]
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"validation": metrics["validation"], "full_30_descriptive": metrics["full_30_descriptive"], "model_load_ms": model_load_ms}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
