"""Evaluate full-corpus augmented evidence without fabricating LLM quality metrics.

This evaluator measures retrieval and context integrity for the same 32 queries.
It deliberately does not call an LLM: generation quality needs real provider
responses plus human/reference answer labels, which this repository does not
contain.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.cases.sources.hybrid_local import LocalHybridCaseProvider
from backend.rag.case_context_adapter import adapt_case_results
from backend.rag.context_builder import build_context
from hybrid_utils import HybridRetriever

QUERY_FILE = ROOT / "evaluation/full_case_augmented_rag/full_case_rag_queries.json"
OUTPUT_FILE = ROOT / "evaluation/full_case_augmented_rag/full_case_rag_metrics.json"
REPORT_FILE = ROOT / "docs/full_case_augmented_rag_comparison.md"


def _read_cases(path: Path) -> set[str]:
    return {
        json.loads(line).get("case_id", "")
        for line in (path / "cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _law_match(expected: str, actual: list[str]) -> bool:
    expected = expected.strip()
    return bool(expected) and any(expected in value or value in expected for value in actual)


def _evaluate(corpus_path: Path, queries: list[dict], laws: HybridRetriever) -> dict:
    provider = LocalHybridCaseProvider(corpus_path=corpus_path)
    corpus_ids = _read_cases(corpus_path)
    law_scores: list[float] = []
    case_scores: list[float] = []
    citation_scores: list[float] = []
    grounded_scores: list[float] = []
    unsupported_scores: list[float] = []
    latency: list[float] = []
    candidates: list[int] = []
    case_covered = 0

    for item in queries:
        start = time.perf_counter()
        law_results = laws.search(item["query"], candidate_limit=50, limit=8)
        case_results = provider.search(item["query"], top_k=5)
        case_items = adapt_case_results(case_results)
        context = build_context(law_items=law_results, case_items=case_items,
                                max_articles=8, max_cases=5)
        latency.append((time.perf_counter() - start) * 1000)
        candidates.append(len(law_results) + len(case_results))

        actual_laws = [str(result.get("law_name") or "") for result in law_results]
        expected_laws = item.get("expected_laws", [])
        law_scores.append(sum(_law_match(law, actual_laws) for law in expected_laws) / len(expected_laws)
                          if expected_laws else 1.0)

        expected_cases = set(item.get("expected_cases", []))
        eligible_cases = expected_cases & corpus_ids
        if eligible_cases:
            case_covered += 1
            actual_cases = {result.case_id for result in case_results}
            case_scores.append(len(eligible_cases & actual_cases) / len(eligible_cases))

        all_items = context["items"]
        ids = [str(value.get("citation_id", "")) for value in all_items]
        law_ids = [value for value in ids if value.startswith("LAW-")]
        case_ids = [value for value in ids if value.startswith("CASE-")]
        valid_namespace = (len(ids) == len(set(ids)) and
                           all(value.startswith("LAW-") for value in law_ids) and
                           all(value.startswith("CASE-") for value in case_ids))
        citation_scores.append(1.0 if valid_namespace else 0.0)
        evidence_items = [value for value in all_items if value.get("text", "").strip()]
        grounded = len(evidence_items) / len(all_items) if all_items else 0.0
        grounded_scores.append(grounded)
        unsupported_scores.append(1.0 - grounded)

    def avg(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    return {
        "corpus_path": str(corpus_path.relative_to(ROOT)),
        "corpus_size": len(corpus_ids),
        "query_count": len(queries),
        "law_recall": avg(law_scores),
        "case_recall": avg(case_scores),
        "case_label_covered_query_count": case_covered,
        "citation_validity": avg(citation_scores),
        "grounded_claim_rate": avg(grounded_scores),
        "unsupported_claim_rate": avg(unsupported_scores),
        "generation_success_rate": None,
        "average_latency_ms": round(sum(latency) / len(latency), 2) if latency else None,
        "average_candidate_count": round(sum(candidates) / len(candidates), 2) if candidates else None,
    }


def _display(value):
    return "—" if value is None else str(value)


def main() -> None:
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    laws = HybridRetriever()
    benchmark = ROOT / "data/processed/cases"
    full = ROOT / "data/processed/full_cases"
    os.environ.pop("CASE_SEMANTIC_WEIGHT", None)
    before = _evaluate(benchmark, queries, laws)
    os.environ["CASE_SEMANTIC_WEIGHT"] = "0.2"
    after = _evaluate(full, queries, laws)
    output = {"before_19_cases": before, "after_6492_cases": after,
              "generation_note": "Not measured: no real LLM provider/reference answers were invoked."}
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = [
        ("law_recall", before["law_recall"], after["law_recall"]),
        ("case_recall", before["case_recall"], after["case_recall"]),
        ("citation_validity", before["citation_validity"], after["citation_validity"]),
        ("grounded_claim_rate*", before["grounded_claim_rate"], after["grounded_claim_rate"]),
        ("unsupported_claim_rate*", before["unsupported_claim_rate"], after["unsupported_claim_rate"]),
        ("generation_success_rate", before["generation_success_rate"], after["generation_success_rate"]),
    ]
    table = "\n".join(f"| {name} | {_display(left)} | {_display(right)} |" for name, left, right in rows)
    report = f"""# V1.4.1 Full Corpus Augmented RAG Evaluation

## 实验设置

- 评测问题：{len(queries)} 条，来自 `full_case_rag_queries.json`，覆盖八类劳动争议，每类4条。
- A：19条 benchmark cases；B：6492条 full cases。
- 两种模式使用相同问题、法规检索器和案例检索配置；full corpus 使用已生成的优化向量配置（`CASE_SEMANTIC_WEIGHT=0.2`）。

## 指标对比

| 指标 | 19 cases | 6492 cases |
|---|---:|---:|
{table}

`*` `grounded_claim_rate` 和 `unsupported_claim_rate` 是证据上下文覆盖率代理指标：统计构建出的 context item 是否有非空证据文本，**不是**对最终 LLM 句子逐条核验。

## 公平性与限制

本次 query 的 `expected_cases` 来自 full corpus 的真实 `case_id`。因此 19-case benchmark 对这些标签没有覆盖，A 的 `case_recall` 显示为 `—`（而不是伪造为0）；A/B 的案例召回不能直接比较。full corpus 的案例标签覆盖数为 {after['case_label_covered_query_count']}/{after['query_count']}，benchmark 为 {before['case_label_covered_query_count']}/{before['query_count']}。

`generation_success_rate` 显示为 `—`。本评测没有调用真实 LLM provider，也没有人工/标准参考答案；用 mock 或规则拼接会掩盖真实生成失败，不能代表最终回答质量。因此本报告只报告法规召回、案例标签覆盖下的案例召回和 context/citation 完整性。要完成最终 RAG 质量比较，需要固定 provider/model、记录真实结构化响应，并为每条问题建立参考答案或人工标注。

## 结果解读

法规检索两组共享同一法规检索器，理论上法规指标应基本一致；案例库扩大后只能在有 full-corpus 标注覆盖的问题上评估 case recall。citation validity 反映 LAW/CASE namespace 是否隔离，不等同于法律结论正确性。任何“6492案例提升了最终回答质量”的结论，需在补齐真实生成和人工标注后再下结论。

原始指标 JSON：`evaluation/full_case_augmented_rag/full_case_rag_metrics.json`。
"""
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
