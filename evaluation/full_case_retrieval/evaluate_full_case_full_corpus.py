"""Evaluate all retrieval modes against the full-corpus ground truth."""

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
CORPUS = ROOT / "data/processed/full_cases"
QUERIES = ROOT / "evaluation/full_case_retrieval/full_case_queries.json"
RESULTS = ROOT / "evaluation/results/full_case_retrieval_full_corpus_metrics.json"
REPORT = ROOT / "docs/full_case_retrieval_evaluation.md"
PREVIOUS = ROOT / "evaluation/results/full_case_retrieval_comparison.json"
METHODS = ("BM25", "Semantic", "Hybrid", "Reranker")
KS = (1, 3, 5)


def rank_of_relevant(results: list[CaseSearchResult], relevant: set[str]) -> int | None:
    return next((rank for rank, result in enumerate(results, 1) if result.case_id in relevant), None)


def metrics(ranks: list[int | None], latencies: list[float], candidates: list[int]) -> dict:
    total = len(ranks)
    return {
        **{
            f"Recall@{k}": sum(rank is not None and rank <= k for rank in ranks) / total
            for k in KS
        },
        "query_count": total,
        "average_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
        "average_candidate_count": sum(candidates) / len(candidates) if candidates else 0.0,
    }


def evaluate() -> dict:
    queries = json.loads(QUERIES.read_text(encoding="utf-8"))
    previous_env = os.environ.get("CASE_CORPUS_PATH")
    os.environ["CASE_CORPUS_PATH"] = str(CORPUS)
    try:
        hybrid = LocalHybridCaseProvider()
        providers = {
            "BM25": LocalCuratedCaseProvider(),
            "Semantic": LocalSemanticCaseProvider(),
            "Hybrid": hybrid,
            "Reranker": LocalRerankedCaseProvider(hybrid_provider=hybrid),
        }
        corpus_ids = {record["case_id"] for record in providers["BM25"].index.records}
        unknown = sorted({case_id for row in queries for case_id in row["relevant_case_ids"]} - corpus_ids)
        if unknown:
            raise ValueError(f"ground-truth case_ids missing from full corpus: {unknown[:5]}")

        rows = []
        for query in queries:
            relevant = set(query["relevant_case_ids"])
            row = {"query": query["query"], "relevant_case_ids": query["relevant_case_ids"], "methods": {}}
            for method, provider in providers.items():
                start = time.perf_counter()
                results = provider.search(query["query"], 10)
                elapsed_ms = (time.perf_counter() - start) * 1000
                row["methods"][method] = {
                    "case_ids": [result.case_id for result in results],
                    "first_relevant_rank": rank_of_relevant(results, relevant),
                    "candidate_count": len(results),
                    "latency_ms": elapsed_ms,
                }
            rows.append(row)

        output = {
            "corpus": {"path": str(CORPUS), "case_count": len(corpus_ids)},
            "ground_truth": {"path": str(QUERIES), "query_count": len(queries), "all_labels_in_corpus": True},
            "metrics": {},
            "query_results": rows,
        }
        for method in METHODS:
            output["metrics"][method] = metrics(
                [row["methods"][method]["first_relevant_rank"] for row in rows],
                [row["methods"][method]["latency_ms"] for row in rows],
                [row["methods"][method]["candidate_count"] for row in rows],
            )
        return output
    finally:
        if previous_env is None:
            os.environ.pop("CASE_CORPUS_PATH", None)
        else:
            os.environ["CASE_CORPUS_PATH"] = previous_env


def render_report(result: dict, previous: dict | None) -> str:
    lines = [
        "# Full Case Corpus Retrieval Evaluation",
        "",
        "## 评测设置",
        "",
        "- full corpus：`data/processed/full_cases/cases.jsonl`",
        "- corpus 数量：**6492**",
        "- ground truth：`evaluation/full_case_retrieval/full_case_queries.json`",
        "- query 数量：**30**",
        "- 每种方法返回 top-10 候选。",
        "- 所有 ground-truth case_id 均存在于 full corpus，Recall 为真实计算结果。",
        "",
        "## Full Corpus 指标",
        "",
        "| Method | Recall@1 | Recall@3 | Recall@5 | 平均检索耗时（ms） | 平均候选数量 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method in METHODS:
        item = result["metrics"][method]
        lines.append(
            f"| {method} | {item['Recall@1']:.4f} | {item['Recall@3']:.4f} | "
            f"{item['Recall@5']:.4f} | {item['average_latency_ms']:.2f} | "
            f"{item['average_candidate_count']:.2f} |"
        )

    lines.extend(["", "## 与 19 条 Benchmark Corpus 对比", ""])
    if previous and "corpora" in previous and "benchmark" in previous["corpora"]:
        lines.extend([
            "以下 benchmark 数值来自上一阶段同一 30 条 benchmark 测试集；full corpus 使用本阶段独立 ground truth，因此两者用于结果参考，不能视为同一标注集上的严格因果对比。",
            "",
            "| Corpus | Method | Recall@1 | Recall@3 | Recall@5 | 平均耗时（ms） | 平均候选数量 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ])
        for method in METHODS:
            old = previous["corpora"]["benchmark"]["metrics"][method]
            new = result["metrics"][method]
            lines.append(f"| benchmark-19 | {method} | {old['Recall@1']:.4f} | {old['Recall@3']:.4f} | {old['Recall@5']:.4f} | {old['average_latency_ms']:.2f} | {old['average_candidate_count']:.2f} |")
            lines.append(f"| full-6492 | {method} | {new['Recall@1']:.4f} | {new['Recall@3']:.4f} | {new['Recall@5']:.4f} | {new['average_latency_ms']:.2f} | {new['average_candidate_count']:.2f} |")
    else:
        lines.append("未找到上一阶段 benchmark 结果文件。")
    lines.extend([
        "",
        "## 说明",
        "",
        "本阶段使用独立 full corpus ground truth，所有无法召回的情况均保留为真实未命中并计入分母，没有将其过滤或改写为不可评估。",
        "未修改 retrieval、embedding、RAG pipeline、19 条 benchmark 数据或 6492 条 corpus 数据。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    result = evaluate()
    previous = json.loads(PREVIOUS.read_text(encoding="utf-8")) if PREVIOUS.is_file() else None
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(render_report(result, previous), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
