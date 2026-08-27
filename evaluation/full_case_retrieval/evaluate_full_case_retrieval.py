"""Compare retrieval over the benchmark and full case corpora."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from backend.cases.search.models import CaseSearchResult
from backend.cases.sources.hybrid_local import LocalHybridCaseProvider
from backend.cases.sources.local import LocalCuratedCaseProvider
from backend.cases.sources.reranked_local import LocalRerankedCaseProvider
from backend.cases.sources.semantic_local import LocalSemanticCaseProvider


ROOT = Path(__file__).resolve().parents[2]
QUERIES_PATH = ROOT / "evaluation/case_retrieval_queries.json"
RESULT_PATH = ROOT / "evaluation/results/full_case_retrieval_comparison.json"
REPORT_PATH = ROOT / "docs/full_case_retrieval_evaluation.md"
CORPORA = {
    "benchmark": ROOT / "data/processed/cases",
    "full_cases": ROOT / "data/processed/full_cases",
}
METHODS = ("BM25", "Semantic", "Hybrid", "Reranker")
KS = (1, 3, 5)


def first_relevant_rank(results: list[CaseSearchResult], relevant: set[str]) -> int | None:
    return next((rank for rank, result in enumerate(results, 1) if result.case_id in relevant), None)


def recall_metrics(ranks: list[int | None], total: int) -> dict[str, float | None]:
    if not total:
        return {f"Recall@{k}": None for k in KS}
    return {
        f"Recall@{k}": sum(rank is not None and rank <= k for rank in ranks) / total
        for k in KS
    }


def make_provider_set() -> dict[str, object]:
    hybrid = LocalHybridCaseProvider()
    return {
        "BM25": LocalCuratedCaseProvider(),
        "Semantic": LocalSemanticCaseProvider(),
        "Hybrid": hybrid,
        "Reranker": LocalRerankedCaseProvider(hybrid_provider=hybrid),
    }


def evaluate_corpus(name: str, corpus_path: Path, queries: list[dict]) -> dict:
    previous = os.environ.get("CASE_CORPUS_PATH")
    os.environ["CASE_CORPUS_PATH"] = str(corpus_path)
    try:
        providers = make_provider_set()
        corpus_ids = {record["case_id"] for record in providers["BM25"].index.records}
        rows = []
        for query in queries:
            relevant = set(query["relevant_case_ids"])
            covered_relevant = relevant & corpus_ids
            item = {
                "query_id": query["query_id"],
                "query": query["query"],
                "relevant_case_ids": query["relevant_case_ids"],
                "covered_relevant_case_ids": sorted(covered_relevant),
                "label_covered": bool(covered_relevant),
                "methods": {},
            }
            for method, provider in providers.items():
                start = time.perf_counter()
                results = provider.search(query["query"], 10)
                elapsed_ms = (time.perf_counter() - start) * 1000
                rank = first_relevant_rank(results, covered_relevant) if covered_relevant else None
                item["methods"][method] = {
                    "case_ids": [result.case_id for result in results],
                    "candidate_count": len(results),
                    "first_relevant_rank": rank,
                    "latency_ms": elapsed_ms,
                }
            rows.append(item)

        metrics = {}
        eligible = [row for row in rows if row["label_covered"]]
        for method in METHODS:
            ranks = [row["methods"][method]["first_relevant_rank"] for row in eligible]
            latencies = [row["methods"][method]["latency_ms"] for row in rows]
            candidates = [row["methods"][method]["candidate_count"] for row in rows]
            metrics[method] = {
                **recall_metrics(ranks, len(eligible)),
                "eligible_query_count": len(eligible),
                "total_query_count": len(rows),
                "average_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
                "average_candidate_count": sum(candidates) / len(candidates) if candidates else 0.0,
            }
        return {
            "corpus_path": str(corpus_path),
            "corpus_case_count": len(corpus_ids),
            "query_count": len(rows),
            "label_covered_query_count": len(eligible),
            "label_coverage": len(eligible) / len(rows) if rows else 0.0,
            "metrics": metrics,
            "results": rows,
        }
    finally:
        if previous is None:
            os.environ.pop("CASE_CORPUS_PATH", None)
        else:
            os.environ["CASE_CORPUS_PATH"] = previous


def render_report(comparison: dict) -> str:
    lines = [
        "# Full Case Corpus Retrieval Evaluation",
        "",
        "## 评测设置",
        "",
        "- 测试集：`evaluation/case_retrieval_queries.json`",
        f"- 测试问题数量：{comparison['query_count']}",
        "- 每种方法返回 top-10 候选，再统计 Recall@1/3/5。",
        "- 两种 corpus 通过 `CASE_CORPUS_PATH` 自动切换。",
        "",
        "## 指标对比",
        "",
        "Recall 只在测试集相关 case_id 出现在当前 corpus 的 query 上计算；同时报告标注覆盖率。",
        "",
        "| Corpus | Method | Label coverage | Recall@1 | Recall@3 | Recall@5 | Avg latency (ms) | Avg candidates |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for corpus_name in ("benchmark", "full_cases"):
        corpus = comparison["corpora"][corpus_name]
        coverage = f"{corpus['label_coverage'] * 100:.2f}%"
        for method in METHODS:
            metric = corpus["metrics"][method]
            values = [
                "—" if metric[f"Recall@{k}"] is None else f"{metric[f'Recall@{k}']:.4f}"
                for k in KS
            ]
            lines.append(
                f"| {corpus_name} | {method} | {coverage} | "
                f"{values[0]} | {values[1]} | {values[2]} | "
                f"{metric['average_latency_ms']:.2f} | {metric['average_candidate_count']:.2f} |"
            )
    lines.extend([
        "",
        "## 结果解释",
        "",
        "benchmark corpus 的 30 条 query 使用现有 19 条案例标注，Recall 可直接计算。",
        "full corpus 与这 19 条 benchmark 案例没有共享标注 case_id 时，Recall 显示为 `—`，这表示当前测试集无法对 full corpus 做有效召回判断，不表示召回率为 0。应在后续建立 full corpus 对应的 relevance judgment 后再进行正式效果比较。",
        "",
        "平均检索耗时和平均候选数量仍对全部 query 统计。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    comparison = {
        "query_file": str(QUERIES_PATH),
        "query_count": len(queries),
        "top_k": 10,
        "corpora": {
            name: evaluate_corpus(name, path, queries)
            for name, path in CORPORA.items()
        },
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(render_report(comparison), encoding="utf-8")
    print(json.dumps({
        name: {"case_count": corpus["corpus_case_count"], "label_coverage": corpus["label_coverage"], "metrics": corpus["metrics"]}
        for name, corpus in comparison["corpora"].items()
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
