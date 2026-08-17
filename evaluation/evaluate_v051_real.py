"""V0.5.1 real-LLM validation runner.

This script intentionally uses a separate real cache and output directory.
It never stores raw provider responses or credentials.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from backend.llm import OpenAICompatibleProvider
from backend.llm.schema import SchemaValidationError, parse_and_validate
from hybrid_utils import HybridRetriever, canonical_id
from query_expansion import expanded_queries
from reranker_utils import document_text, load_reranker, rank_scored_candidates
from understood_utils import build_multi_query_candidates
from evaluate_retrieval import metrics, resolve_relevant


REAL_MODEL = "deepseek-v4-flash"
REAL_CACHE = ROOT / ".cache/query_understanding_real.json"
REAL_RECORD_DIR = ROOT / "evaluation/query_understanding_results_real"
RESULT_PATH = ROOT / "evaluation/results/v0.5_real_llm_results.json"
SUMMARY_PATH = ROOT / "evaluation/results/v0.5_real_llm_summary.md"


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        raise RuntimeError("root .env is missing")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in {"LEGALCASE_LLM_BASE_URL", "LEGALCASE_LLM_API_KEY", "LEGALCASE_LLM_MODEL"}:
            os.environ[key] = value
    missing = [key for key in ("LEGALCASE_LLM_BASE_URL", "LEGALCASE_LLM_API_KEY", "LEGALCASE_LLM_MODEL")
               if not os.environ.get(key)]
    if missing:
        raise RuntimeError("missing required .env variables: " + ", ".join(missing))
    if os.environ["LEGALCASE_LLM_MODEL"] != REAL_MODEL:
        raise RuntimeError("configured model is not the validated V0.5.1 model")


def load_real_cache() -> dict:
    if not REAL_CACHE.exists():
        return {}
    try:
        value = json.loads(REAL_CACHE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_real_cache(cache: dict) -> None:
    REAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    REAL_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fallback_result(query: str, reason: str) -> dict:
    return {
        "original_query": query,
        "domain": "劳动争议",
        "issue": "劳动争议法律检索",
        "user_intent": "查找适用的劳动争议法律规则",
        "legal_concepts": [],
        "search_queries": [query],
        "provider_status": "fallback",
        "fallback_reason_type": reason,
    }


def understand_real(provider, query: str, cache: dict, max_retries: int = 2) -> tuple[dict, dict]:
    cached = cache.get(query)
    if (cached and cached.get("model") == provider.model and
            cached.get("provider_status") == "real_llm"):
        result = dict(cached["structured_result"])
        return result, {
            "cache_hit": True,
            "schema_valid": True,
            "schema_success_on_first_attempt": cached.get("attempts", 1) == 1,
            "retry_count": cached.get("retry_count", 0),
            "fallback": False,
            "latency_ms": 0.0,
        }
    start = time.perf_counter()
    last_error_type = "unknown"
    for attempt in range(max_retries + 1):
        try:
            raw = provider.generate(query)
            result = parse_and_validate(raw, query)
            result["provider_status"] = "real_llm"
            retry_count = attempt
            cache[query] = {
                "query": query,
                "model": provider.model,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "provider_status": "real_llm",
                "attempts": attempt + 1,
                "retry_count": retry_count,
                "structured_result": result,
            }
            save_real_cache(cache)
            return result, {
                "cache_hit": False,
                "schema_valid": True,
                "schema_success_on_first_attempt": attempt == 0,
                "retry_count": retry_count,
                "fallback": False,
                "latency_ms": (time.perf_counter() - start) * 1000,
            }
        except SchemaValidationError:
            last_error_type = "schema_validation"
        except Exception:
            # Do not persist or print provider exception text; it may contain request details.
            last_error_type = "provider_error"
    return fallback_result(query, last_error_type), {
        "cache_hit": False,
        "schema_valid": False,
        "schema_success_on_first_attempt": False,
        "retry_count": max_retries,
        "fallback": True,
        "latency_ms": (time.perf_counter() - start) * 1000,
    }


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


def p95(values: list[float]) -> float:
    return float(np.percentile(values, 95)) if values else 0.0


def average_metrics(rows: list[dict]) -> dict:
    names = ("recall_at_1", "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")
    return {name: sum(row["metrics"][name] for row in rows) / len(rows) for name in names}


def main() -> int:
    load_dotenv()
    provider = OpenAICompatibleProvider()
    if provider.model != REAL_MODEL:
        raise RuntimeError("real provider model mismatch")
    queries = json.loads((ROOT / "evaluation/retrieval_queries.json").read_text(encoding="utf-8"))
    if len(queries) != 30:
        raise RuntimeError("frozen benchmark must contain exactly 30 queries")
    cache = load_real_cache()
    understandings = {}
    reliability = {}
    for query in queries:
        result, meta = understand_real(provider, query["query"], cache)
        understandings[query["query_id"]] = result
        reliability[query["query_id"]] = meta
        print(f"UNDERSTANDING {query['query_id']} status={result.get('provider_status')} cache_hit={meta['cache_hit']} retries={meta['retry_count']}")

    retriever = HybridRetriever()
    reranker = load_reranker(local_files_only=True)
    groups = {}
    per_query = {}
    retrieval_latencies = []
    candidate_stats_20 = []
    candidate_stats_50 = []
    for query in queries:
        qid, original = query["query_id"], query["query"]
        structured = understandings[qid]
        searches = expanded_queries(structured, original, 3)
        retrieval_start = time.perf_counter()
        candidates_20, stats_20 = build_multi_query_candidates(retriever, searches, 20, 150)
        candidates_50, stats_50 = build_multi_query_candidates(retriever, searches, 50, 150)
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000
        retrieval_latencies.append(retrieval_ms)
        relevant = resolve_relevant(query, retriever.records)
        candidate_stats_20.append((stats_20, len(set(canonical_id(x) for x in candidates_20) & relevant) / len(relevant)))
        candidate_stats_50.append((stats_50, len(set(canonical_id(x) for x in candidates_50) & relevant) / len(relevant)))
        groups[qid] = (original, candidates_50)
        per_query[qid] = {
            "original_query": original,
            "structured_understanding": structured,
            "expanded_queries": searches,
            "understanding_meta": reliability[qid],
            "relevant_articles": query["relevant_articles"],
            "relevant_canonical_ids": sorted(relevant),
            "candidate_coverage": {
                "at_20": {**stats_20, "candidate_recall": candidate_stats_20[-1][1]},
                "at_50": {**stats_50, "candidate_recall": candidate_stats_50[-1][1]},
            },
            "retrieval_latency_ms": retrieval_ms,
        }
    reranked, total_rerank_ms = rerank_groups(reranker, groups)
    average_rerank_ms = total_rerank_ms / len(queries)
    rerank_latencies = [average_rerank_ms] * len(queries)
    rows = []
    error_types = {"SUCCESS": [], "RERANKING_MISS": [], "CANDIDATE_MISS": [], "LLM_FALLBACK": []}
    for query in queries:
        qid = query["query_id"]
        relevant = set(per_query[qid]["relevant_canonical_ids"])
        results = reranked[qid]
        candidate_recall = per_query[qid]["candidate_coverage"]["at_50"]["candidate_recall"]
        if reliability[qid]["fallback"]:
            error_types["LLM_FALLBACK"].append(qid)
        elif candidate_recall == 0:
            error_types["CANDIDATE_MISS"].append(qid)
        elif not any(canonical_id(item) in relevant for item in results[:5]):
            error_types["RERANKING_MISS"].append(qid)
        else:
            error_types["SUCCESS"].append(qid)
        total_ms = reliability[qid]["latency_ms"] + per_query[qid]["retrieval_latency_ms"] + average_rerank_ms
        per_query[qid]["reranker_latency_ms"] = average_rerank_ms
        per_query[qid]["total_latency_ms"] = total_ms
        per_query[qid]["final_retrieval_ranking"] = results
        per_query[qid]["final_relevant_ranks"] = {
            key: next((index for index, item in enumerate(results, 1) if canonical_id(item) == key), None)
            for key in relevant
        }
        rows.append({"query_id": qid, "query": query["query"], "metrics": metrics(results, relevant), "results": results})

    REAL_RECORD_DIR.mkdir(parents=True, exist_ok=True)
    for qid, record in per_query.items():
        (REAL_RECORD_DIR / f"{qid}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    v04 = json.loads((ROOT / "evaluation/results/v0.4_reranker_results.json").read_text(encoding="utf-8"))["selected_reranked_summary"]
    understanding_latencies = [reliability[qid]["latency_ms"] for qid in reliability]
    total_latencies = [per_query[qid]["total_latency_ms"] for qid in per_query]
    schema_first = sum(meta["schema_success_on_first_attempt"] for meta in reliability.values())
    retry_queries = sum(meta["retry_count"] > 0 for meta in reliability.values())
    fallback_count = sum(meta["fallback"] for meta in reliability.values())
    candidate_summary = {
        "20": {"candidate_recall": sum(item[1] for item in candidate_stats_20) / len(queries),
               "average_query_count": sum(item[0]["query_count"] for item in candidate_stats_20) / len(queries),
               "average_unique_candidates": sum(item[0]["unique_candidate_count"] for item in candidate_stats_20) / len(queries)},
        "50": {"candidate_recall": sum(item[1] for item in candidate_stats_50) / len(queries),
               "average_query_count": sum(item[0]["query_count"] for item in candidate_stats_50) / len(queries),
               "average_unique_candidates": sum(item[0]["unique_candidate_count"] for item in candidate_stats_50) / len(queries)},
    }
    report = {
        "provider": "OpenAI-compatible real provider",
        "model": provider.model,
        "prompt_schema_version": "v0.5-query-understanding-schema-v1",
        "benchmark_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "benchmark_is_real_llm": True,
        "query_count": len(queries),
        "v04_reranker_metrics": {key: v04[key] for key in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")},
        "v05_real_llm_metrics": average_metrics(rows),
        "candidate_recall": candidate_summary,
        "reliability": {"api_success_count": len(queries) - fallback_count,
                         "schema_success_on_first_attempt": schema_first,
                         "retry_query_count": retry_queries,
                         "fallback_count": fallback_count,
                         "schema_success_rate": schema_first / len(queries),
                         "retry_rate": retry_queries / len(queries),
                         "fallback_rate": fallback_count / len(queries),
                         "average_expanded_query_count": sum(len(per_query[qid]["expanded_queries"]) for qid in per_query) / len(queries)},
        "latency_ms": {"query_understanding_average": statistics.mean(understanding_latencies),
                       "query_understanding_p50": statistics.median(understanding_latencies),
                       "query_understanding_p95": p95(understanding_latencies),
                       "retrieval_average": statistics.mean(retrieval_latencies),
                       "reranker_average": average_rerank_ms,
                       "total_average": statistics.mean(total_latencies),
                       "total_p50": statistics.median(total_latencies),
                       "total_p95": p95(total_latencies)},
        "error_types": error_types,
        "query_records": per_query,
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# V0.5.1 Real LLM Validation", "", f"Provider: `{report['provider']}`", f"Model: `{provider.model}`", f"Benchmark timestamp UTC: `{report['benchmark_timestamp_utc']}`", f"Queries: {len(queries)}", "", "## Metrics", "", "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 |", "|---|---:|---:|---:|---:|---:|", f"| V0.4 Reranker | {v04['recall_at_1']:.4f} | {v04['recall_at_3']:.4f} | {v04['recall_at_5']:.4f} | {v04['mrr']:.4f} | {v04['ndcg_at_5']:.4f} |"]
    values = report["v05_real_llm_metrics"]
    lines.append(f"| V0.5 Real LLM | {values['recall_at_1']:.4f} | {values['recall_at_3']:.4f} | {values['recall_at_5']:.4f} | {values['mrr']:.4f} | {values['ndcg_at_5']:.4f} |")
    lines += ["", "## Candidate recall", "", f"- @20: {candidate_summary['20']['candidate_recall']:.4f}", f"- @50: {candidate_summary['50']['candidate_recall']:.4f}", f"- Average expanded query count: {report['reliability']['average_expanded_query_count']:.2f}", "", "## Reliability", f"- API success: {report['reliability']['api_success_count']}/{len(queries)}", f"- Schema success on first attempt: {schema_first}/{len(queries)} ({report['reliability']['schema_success_rate']:.4f})", f"- Queries with retry: {retry_queries} ({report['reliability']['retry_rate']:.4f})", f"- Fallback: {fallback_count} ({report['reliability']['fallback_rate']:.4f})", "", "## Latency (ms)", f"- Query Understanding average / P50 / P95: {report['latency_ms']['query_understanding_average']:.2f} / {report['latency_ms']['query_understanding_p50']:.2f} / {report['latency_ms']['query_understanding_p95']:.2f}", f"- Retrieval average: {report['latency_ms']['retrieval_average']:.2f}", f"- Reranker average: {report['latency_ms']['reranker_average']:.2f}", f"- Total average / P50 / P95: {report['latency_ms']['total_average']:.2f} / {report['latency_ms']['total_p50']:.2f} / {report['latency_ms']['total_p95']:.2f}", "", "## Error classification"]
    for name, ids in error_types.items():
        lines.append(f"- {name}: {len(ids)} — {', '.join(ids) if ids else 'none'}")
    for qid in ("q01", "q19", "q27"):
        record = per_query[qid]
        lines += ["", f"## {qid}", "", f"Query: {record['original_query']}", "", "```json", json.dumps({"structured_understanding": record["structured_understanding"], "expanded_queries": record["expanded_queries"], "candidate_coverage": record["candidate_coverage"], "final_relevant_ranks": record["final_relevant_ranks"]}, ensure_ascii=False, indent=2), "```"]
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("RESULT_PATH=" + str(RESULT_PATH))
    print("SUMMARY_PATH=" + str(SUMMARY_PATH))
    print("METRICS=" + json.dumps(report["v05_real_llm_metrics"], ensure_ascii=False))
    print("CANDIDATE_RECALL=" + json.dumps(candidate_summary, ensure_ascii=False))
    print("ERROR_TYPES=" + json.dumps({key: len(value) for key, value in error_types.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
