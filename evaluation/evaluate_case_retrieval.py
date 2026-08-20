"""Run the frozen V0.7.5 BM25 versus Semantic case benchmark."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.cases.search.bm25 import CaseBM25Index
from backend.cases.search.semantic import CaseSemanticIndex
from evaluation.case_retrieval.metrics import aggregate, metric_for_ranks, percentile

CORPUS = ROOT / "data/processed/cases/cases.jsonl"
EMBEDDINGS = ROOT / "data/processed/cases/case_embeddings.npy"
EMBED_INDEX = ROOT / "data/processed/cases/case_embedding_index.json"
QUERIES = ROOT / "evaluation/case_retrieval_queries.json"
HASH_FILE = ROOT / "evaluation/case_retrieval_queries.sha256"
RESULTS = ROOT / "evaluation/case_retrieval_results.json"
METRICS = ROOT / "evaluation/case_retrieval_metrics.json"
SUMMARY = ROOT / "evaluation/case_retrieval_summary.md"


def load_records() -> list[dict]:
    return [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_queries(records: list[dict], queries: list[dict]) -> None:
    ids = {record["case_id"] for record in records}
    if len(records) != 19:
        raise ValueError(f"frozen main corpus must contain 19 cases, got {len(records)}")
    if len(queries) != 30 or len({row["query_id"] for row in queries}) != 30:
        raise ValueError("benchmark must contain 30 unique queries")
    for row in queries:
        if not row.get("query") or not row.get("relevant_case_ids"):
            raise ValueError(f"invalid benchmark row: {row.get('query_id')}")
        if not set(row["relevant_case_ids"]).issubset(ids):
            raise ValueError(f"unknown relevant case in {row['query_id']}")
        if row["primary_case_id"] not in row["relevant_case_ids"]:
            raise ValueError(f"primary case is not relevant in {row['query_id']}")
        if "2014-18-1-232-001" in row["relevant_case_ids"]:
            raise ValueError("auxiliary case 011 must not be benchmark relevant")


def query_hash() -> str:
    return hashlib.sha256(QUERIES.read_bytes()).hexdigest()


def search_row(results: list, elapsed_ms: float, relevant: set[str], primary: str) -> dict:
    ranked = [result.case_id for result in results]
    metric10 = metric_for_ranks(ranked, relevant, 10)
    primary_rank = next((i + 1 for i, case_id in enumerate(ranked) if case_id == primary), None)
    return {
        "top10": [{"rank": i + 1, "case_id": result.case_id, "title": result.title,
                   "score": float(result.score), "source_file": result.source_file,
                   "source_url": result.source_url} for i, result in enumerate(results)],
        "primary_rank": primary_rank,
        "first_relevant_rank": metric10["first_relevant_rank"],
        "metrics": metric10,
        "latency_ms": elapsed_ms,
    }


def classify(row: dict) -> str:
    rank = row["first_relevant_rank"]
    if rank == 1:
        return "SUCCESS"
    if rank is not None and rank <= 5:
        return "RANKING_MISS"
    return "TOP5_MISS"


def main() -> None:
    records = load_records()
    queries = json.loads(QUERIES.read_text(encoding="utf-8"))
    validate_queries(records, queries)
    actual_hash = query_hash()
    expected_hash = HASH_FILE.read_text(encoding="utf-8").strip().split()[0]
    if actual_hash != expected_hash:
        raise ValueError("benchmark query hash does not match frozen hash file")

    bm25 = CaseBM25Index.from_jsonl(CORPUS)
    semantic = CaseSemanticIndex.from_files(CORPUS, EMBEDDINGS, EMBED_INDEX)
    results = []
    for row in queries:
        relevant = set(row["relevant_case_ids"])
        item = {key: row[key] for key in ("query_id", "query", "primary_case_id", "relevant_case_ids", "topic", "difficulty", "query_type")}
        start = time.perf_counter(); bm25_results = bm25.search(row["query"], top_k=10); bm25_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter(); semantic_results = semantic.search(row["query"], top_k=10); semantic_ms = (time.perf_counter() - start) * 1000
        item["bm25"] = {**search_row(bm25_results, bm25_ms, relevant, row["primary_case_id"]), "classification": classify(search_row(bm25_results, bm25_ms, relevant, row["primary_case_id"]))}
        item["semantic"] = {**search_row(semantic_results, semantic_ms, relevant, row["primary_case_id"]), "classification": classify(search_row(semantic_results, semantic_ms, relevant, row["primary_case_id"]))}
        results.append(item)

    def method_metrics(method: str) -> dict:
        rows = [row[method]["metrics"] for row in results]
        by_diff = {}
        for difficulty in ("easy", "medium", "hard"):
            subset = [row[method]["metrics"] for row in results if row["difficulty"] == difficulty]
            by_diff[difficulty] = aggregate(subset, len(subset))
        by_topic = defaultdict(list)
        for row in results:
            by_topic[row["topic"]].append(row[method]["metrics"])
        return {
            "overall": aggregate(rows, len(rows)),
            "by_difficulty": by_diff,
            "by_topic": {topic: aggregate(values, len(values)) for topic, values in by_topic.items()},
            "latency_ms": {"average": sum(row[method]["latency_ms"] for row in results) / len(results),
                           "p50": percentile([row[method]["latency_ms"] for row in results], .50),
                           "p95": percentile([row[method]["latency_ms"] for row in results], .95)},
            "classification_counts": {label: sum(row[method]["classification"] == label for row in results) for label in ("SUCCESS", "RANKING_MISS", "TOP5_MISS")},
        }

    failures = []
    for row in results:
        if row["bm25"]["classification"] != "SUCCESS" or row["semantic"]["classification"] != "SUCCESS":
            failures.append({"query_id": row["query_id"], "query": row["query"], "relevant_case_ids": row["relevant_case_ids"],
                             "bm25_classification": row["bm25"]["classification"], "bm25_primary_rank": row["bm25"]["primary_rank"], "bm25_first_relevant_rank": row["bm25"]["first_relevant_rank"],
                             "semantic_classification": row["semantic"]["classification"], "semantic_primary_rank": row["semantic"]["primary_rank"], "semantic_first_relevant_rank": row["semantic"]["first_relevant_rank"]})
    metrics = {"benchmark": {"corpus_count": len(records), "query_count": len(queries), "query_sha256": actual_hash, "top_k": 10},
               "BM25": method_metrics("bm25"), "Semantic": method_metrics("semantic"),
               "failure_and_disagreement_analysis": {"representative_count": min(5, len(failures)), "representative": failures[:5], "all_non_success": failures}}
    RESULTS.write_text(json.dumps({"benchmark": metrics["benchmark"], "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    METRICS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# V0.7.5 Case Retrieval Benchmark Summary", "", "Frozen corpus: 19 main curated cases; benchmark queries: 30; top-k: 10.", "", "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 | Avg ms | P50 ms | P95 ms |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for method in ("BM25", "Semantic"):
        m = metrics[method]; o = m["overall"]; l = m["latency_ms"]
        lines.append(f"| {method} | {o['Recall@1']:.4f} | {o['Recall@3']:.4f} | {o['Recall@5']:.4f} | {o['MRR']:.4f} | {o['nDCG@5']:.4f} | {l['average']:.2f} | {l['p50']:.2f} | {l['p95']:.2f} |")
    lines += ["", "Classification: SUCCESS means the first relevant case is rank 1; RANKING_MISS means relevant appears in ranks 2-5; TOP5_MISS means no relevant case appears in the top 5.", "", f"Frozen query SHA-256: `{actual_hash}`", "", "## Representative failures or disagreements", ""]
    for failure in failures[:5]:
        lines.append(f"- **{failure['query_id']}** {failure['query']} — BM25 `{failure['bm25_classification']}` (primary rank {failure['bm25_primary_rank']}), Semantic `{failure['semantic_classification']}` (primary rank {failure['semantic_primary_rank']}); relevant `{', '.join(failure['relevant_case_ids'])}`.")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"BM25": metrics["BM25"]["overall"], "Semantic": metrics["Semantic"]["overall"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
