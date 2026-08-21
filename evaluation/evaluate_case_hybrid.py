"""V0.7.6 Dev/Test hybrid case retrieval evaluation."""

from __future__ import annotations

import hashlib
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.cases.search.bm25 import CaseBM25Index
from backend.cases.search.hybrid import fuse_ranked_results
from backend.cases.search.semantic import CaseSemanticIndex
from evaluation.case_retrieval.metrics import aggregate, metric_for_ranks, percentile

QUERY_PATH = ROOT / "evaluation/case_retrieval_queries.json"
QUERY_HASH_PATH = ROOT / "evaluation/case_retrieval_queries.sha256"
SPLIT_PATH = ROOT / "evaluation/case_retrieval_split.json"
SPLIT_HASH_PATH = ROOT / "evaluation/case_retrieval_split.sha256"
CONFIG_PATH = ROOT / "evaluation/v076_hybrid_config.json"
CONFIG_HASH_PATH = ROOT / "evaluation/v076_hybrid_config.sha256"
CORPUS = ROOT / "data/processed/cases/cases.jsonl"
RESULT_PATH = ROOT / "evaluation/v076_hybrid_results.json"
METRICS_PATH = ROOT / "evaluation/v076_hybrid_metrics.json"
SUMMARY_PATH = ROOT / "evaluation/v076_hybrid_summary.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def create_or_validate_split(queries: list[dict]) -> dict:
    if SPLIT_PATH.exists():
        split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    else:
        rng = random.Random(42)
        by_difficulty = {difficulty: [row for row in queries if row["difficulty"] == difficulty] for difficulty in ("easy", "medium", "hard")}
        test_ids: list[str] = []
        for difficulty, count in (("easy", 3), ("medium", 4), ("hard", 3)):
            rows = list(by_difficulty[difficulty])
            rng.shuffle(rows)
            test_ids.extend(row["query_id"] for row in rows[:count])
        split = {"dev_query_ids": [row["query_id"] for row in queries if row["query_id"] not in test_ids],
                 "test_query_ids": [row["query_id"] for row in queries if row["query_id"] in test_ids],
                 "seed": 42, "method": "deterministic stratified split by difficulty"}
        SPLIT_PATH.write_text(json.dumps(split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        SPLIT_HASH_PATH.write_text(sha256(SPLIT_PATH) + "\n", encoding="utf-8")
    if len(split["dev_query_ids"]) != 20 or len(split["test_query_ids"]) != 10:
        raise ValueError("split must contain Dev=20 and Test=10")
    if set(split["dev_query_ids"]) & set(split["test_query_ids"]):
        raise ValueError("Dev/Test overlap")
    if set(split["dev_query_ids"]) | set(split["test_query_ids"]) != {row["query_id"] for row in queries}:
        raise ValueError("Dev/Test union is not the frozen query set")
    if sha256(SPLIT_PATH) != SPLIT_HASH_PATH.read_text(encoding="utf-8").strip():
        raise ValueError("split hash mismatch")
    return split


def evaluate_ranked(rows: list[dict], method: str, query_ids: set[str]) -> dict:
    selected = [row for row in rows if row["query_id"] in query_ids]
    per_query = [row[method]["metrics"] for row in selected]
    return aggregate(per_query, len(selected))


def rank_record(results: list, relevant: set[str], primary: str, latency_ms: float) -> dict:
    ids = [result.case_id for result in results]
    metric = metric_for_ranks(ids, relevant, 10)
    return {"top10": [{"rank": i + 1, "case_id": result.case_id, "title": result.title,
                       "score": float(result.score), "hybrid_score": result.hybrid_score,
                       "bm25_rank": result.bm25_rank, "semantic_rank": result.semantic_rank,
                       "source_url": result.source_url, "source_file": result.source_file}
                      for i, result in enumerate(results)],
            "primary_rank": next((i + 1 for i, case_id in enumerate(ids) if case_id == primary), None),
            "first_relevant_rank": metric["first_relevant_rank"], "metrics": metric,
            "latency_ms": latency_ms}


def score_rows(base_rows: list[dict], method: str, *, rrf_k: int = 60, semantic_weight: float = 0.8,
               query_ids: set[str] | None = None) -> dict[str, dict]:
    output = {}
    for row in base_rows:
        if query_ids is not None and row["query_id"] not in query_ids:
            continue
        relevant = set(row["relevant_case_ids"])
        start = time.perf_counter()
        if method == "bm25":
            results = row["_bm25_results"]
        elif method == "semantic":
            results = row["_semantic_results"]
        else:
            results = fuse_ranked_results(row["_bm25_results"], row["_semantic_results"], method=method,
                                          rrf_k=rrf_k, semantic_weight=semantic_weight)
            results = results[:10]
        fusion_ms = (time.perf_counter() - start) * 1000 if method in {"rrf", "weighted"} else 0.0
        latency = row["bm25_latency_ms"] if method == "bm25" else row["semantic_latency_ms"] if method == "semantic" else row["bm25_latency_ms"] + row["semantic_latency_ms"] + fusion_ms
        output[row["query_id"]] = rank_record(results, relevant, row["primary_case_id"], latency)
    return output


def main() -> None:
    records = load_jsonl(CORPUS)
    queries = json.loads(QUERY_PATH.read_text(encoding="utf-8"))
    if len(records) != 19 or len(queries) != 30:
        raise ValueError("V0.7.6 requires frozen corpus=19 and queries=30")
    expected_query_hash = "f577de865360e923266ea9975de8ee0b7ef429630be8225a774ba4f797673305"
    if sha256(QUERY_PATH) != expected_query_hash or QUERY_HASH_PATH.read_text(encoding="utf-8").strip().lower() != expected_query_hash:
        raise ValueError("frozen benchmark query hash changed")
    split = create_or_validate_split(queries)
    dev_ids, test_ids = set(split["dev_query_ids"]), set(split["test_query_ids"])

    bm25 = CaseBM25Index.from_jsonl(CORPUS)
    semantic = CaseSemanticIndex.from_files(CORPUS, ROOT / "data/processed/cases/case_embeddings.npy",
                                            ROOT / "data/processed/cases/case_embedding_index.json")
    base_rows = []
    for query in queries:
        start = time.perf_counter(); bm25_results = bm25.search(query["query"], 10); bm25_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter(); semantic_results = semantic.search(query["query"], 10); semantic_ms = (time.perf_counter() - start) * 1000
        base_rows.append({**query, "_bm25_results": bm25_results, "_semantic_results": semantic_results,
                          "bm25_latency_ms": bm25_ms, "semantic_latency_ms": semantic_ms})

    # Failure/disagreement audit is descriptive and performed before selecting fusion.
    audit = []
    for row in base_rows:
        bm_ids = [item.case_id for item in row["_bm25_results"]]
        se_ids = [item.case_id for item in row["_semantic_results"]]
        bm_rank = next((i + 1 for i, value in enumerate(bm_ids) if value in row["relevant_case_ids"]), None)
        se_rank = next((i + 1 for i, value in enumerate(se_ids) if value in row["relevant_case_ids"]), None)
        if bm_ids[0] not in row["relevant_case_ids"] or se_ids[0] not in row["relevant_case_ids"] or bm_ids[0] != se_ids[0]:
            audit.append({"query_id": row["query_id"], "query": row["query"], "primary_case_id": row["primary_case_id"],
                          "bm25_top3": bm_ids[:3], "semantic_top3": se_ids[:3], "bm25_rank": bm_rank,
                          "semantic_rank": se_rank, "failure_reason": "Top1 disagreement or miss; relevant candidate remains in top10"})

    # Only Dev is used for all configuration selection.
    candidates = []
    for k in (20, 40, 60, 80):
        values = score_rows(base_rows, "rrf", rrf_k=k, query_ids=dev_ids)
        rows_for_method = [{"query_id": qid, "metrics": item["metrics"]} for qid, item in values.items()]
        candidates.append({"method": "rrf", "rrf_k": k, "semantic_weight": None,
                          "metrics": aggregate([x["metrics"] for x in rows_for_method], len(rows_for_method))})
    for alpha in (0.6, 0.7, 0.8, 0.9):
        values = score_rows(base_rows, "weighted", semantic_weight=alpha, query_ids=dev_ids)
        candidates.append({"method": "weighted", "rrf_k": None, "semantic_weight": alpha,
                          "metrics": aggregate([item["metrics"] for item in values.values()], len(values))})
    def key(item):
        metrics = item["metrics"]
        return (metrics["Recall@1"], metrics["MRR"], metrics["nDCG@5"], 1 if item["method"] == "rrf" else 0)
    selected = max(candidates, key=key)
    config = {"method": selected["method"], "rrf_k": selected["rrf_k"], "semantic_weight": selected["semantic_weight"],
              "bm25_top_k": 10, "semantic_top_k": 10, "selection_split": "dev", "selection_priority": ["Recall@1", "MRR", "nDCG@5", "prefer_rrf_on_tie"]}
    if CONFIG_PATH.exists():
        if json.loads(CONFIG_PATH.read_text(encoding="utf-8")) != config:
            raise ValueError("frozen hybrid config already exists and differs")
    else:
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        CONFIG_HASH_PATH.write_text(sha256(CONFIG_PATH) + "\n", encoding="utf-8")
    if sha256(CONFIG_PATH) != CONFIG_HASH_PATH.read_text(encoding="utf-8").strip():
        raise ValueError("hybrid config hash mismatch")

    all_methods = {"bm25": score_rows(base_rows, "bm25"), "semantic": score_rows(base_rows, "semantic")}
    final_method = "rrf" if config["method"] == "rrf" else "weighted"
    all_methods["hybrid"] = score_rows(base_rows, final_method, rrf_k=config.get("rrf_k") or 60,
                                        semantic_weight=config.get("semantic_weight") or 0.8)
    result_rows = []
    for row in base_rows:
        result_rows.append({key: row[key] for key in ("query_id", "query", "relevant_case_ids", "primary_case_id", "topic", "difficulty", "query_type")}
                           | {method: all_methods[method][row["query_id"]] for method in ("bm25", "semantic", "hybrid")}
                           | {"split": "dev" if row["query_id"] in dev_ids else "test"})

    def method_summary(method: str, ids: set[str]) -> dict:
        values = [all_methods[method][qid] for qid in ids]
        return {"metrics": aggregate([item["metrics"] for item in values], len(values)),
                "latency_ms": {"average": sum(item["latency_ms"] for item in values) / len(values),
                               "p50": percentile([item["latency_ms"] for item in values], .5),
                               "p95": percentile([item["latency_ms"] for item in values], .95)},
                "count": len(values)}

    metric_output = {"corpus_count": 19, "query_count": 30, "query_sha256": sha256(QUERY_PATH),
                     "split": split, "split_sha256": sha256(SPLIT_PATH), "config": config,
                     "config_sha256": sha256(CONFIG_PATH), "selection_candidates_dev": candidates,
                     "baseline_dev": {method: method_summary(method, dev_ids) for method in ("bm25", "semantic")},
                     "baseline_test": {method: method_summary(method, test_ids) for method in ("bm25", "semantic")},
                     "held_out_test": {method: method_summary(method, test_ids) for method in ("bm25", "semantic", "hybrid")},
                     "full_30_descriptive": {method: method_summary(method, set(row["query_id"] for row in queries)) for method in ("bm25", "semantic", "hybrid")},
                     "failure_disagreement_audit": audit}
    RESULT_PATH.write_text(json.dumps({"benchmark": {"corpus_count": 19, "query_count": 30, "split": split, "config": config}, "results": result_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    METRICS_PATH.write_text(json.dumps(metric_output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# V0.7.6 Hybrid Case Retrieval", "", "Selection uses Dev=20 only. Test=10 is evaluated only after configuration freeze.", "", "## Frozen configuration", "", "```json", json.dumps(config, ensure_ascii=False, indent=2), "```", ""]
    for section, label in (("baseline_dev", "Dev baseline"), ("baseline_test", "Test baseline"), ("held_out_test", "Held-out Test"), ("full_30_descriptive", "Full-30 descriptive result")):
        lines += [f"## {label}", "", "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 | Avg ms | P50 ms | P95 ms |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for method, value in metric_output[section].items():
            m, l = value["metrics"], value["latency_ms"]
            lines.append(f"| {method} | {m['Recall@1']:.4f} | {m['Recall@3']:.4f} | {m['Recall@5']:.4f} | {m['MRR']:.4f} | {m['nDCG@5']:.4f} | {l['average']:.2f} | {l['p50']:.2f} | {l['p95']:.2f} |")
        lines.append("")
    lines += ["## Limitations", "", "Semantic V0.7.5 already has Full-30 Recall@1=0.9333, so the improvement ceiling is small. This benchmark does not use query-specific rules, LLM expansion, reranking, or frozen-label changes. Full-30 is descriptive after Dev selection, not an independent held-out test.", "", "## Failure/disagreement audit", ""]
    lines += [f"- `{item['query_id']}` {item['query']}: BM25 rank {item['bm25_rank']}, Semantic rank {item['semantic_rank']}; {item['failure_reason']}" for item in audit]
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"config": config, "held_out_test": metric_output["held_out_test"], "full_30_descriptive": metric_output["full_30_descriptive"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
