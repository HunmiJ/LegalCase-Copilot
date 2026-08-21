"""Offline evaluation of baseline versus case-augmented RAG retrieval/context."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.cases.retrieval import RuntimeCaseRetriever
from backend.rag.citation_validator import validate_citations
from backend.rag.context_builder import build_context
from backend.rag.generator import GroundedGenerator, MockRAGProvider
from scripts.hybrid_utils import HybridRetriever


def law_recall(results: list[dict[str, Any]], expected: list[str]) -> float:
    if not expected:
        return 1.0
    found = {str(item.get("law_name") or item.get("law_title") or "") for item in results}
    return sum(any(term in name for name in found) for term in expected) / len(expected)


def case_recall(results: list[dict[str, Any]], expected: list[str]) -> float:
    if not expected:
        return 1.0
    found = {item.get("case_id") for item in results}
    return len(found.intersection(expected)) / len(expected)


def make_law_context(law_results: list[dict[str, Any]], case_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    context = build_context(law_results, max_articles=5)
    if case_results:
        case_text = "\n".join(f"{item.get('title')}；争点：{item.get('dispute_focus') or ''}；裁判结果：{item.get('judgment_result') or ''}" for item in case_results)
        context["context_text"] += "\n\nCASE_SOURCES:\n" + case_text
    return context


def generation_metrics(query: str, context: dict[str, Any], generator: GroundedGenerator) -> dict[str, float | bool]:
    response, _ = generator.generate(query, context)
    validation = validate_citations(response, context)
    success = bool(validation["valid"]) and bool(context.get("items"))
    return {
        "citation_validity": validation["citation_validity"],
        "grounded_claim_rate": validation["grounded_claim_rate"],
        "unsupported_claim_rate": validation["unsupported_citation_rate"],
        "answer_success_rate": 1.0 if success else 0.0,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    keys = ("law_recall_at_k", "case_recall_at_k", "citation_validity", "grounded_claim_rate", "unsupported_claim_rate", "answer_success_rate")
    return {key: round(statistics.mean(float(row[key]) for row in rows), 4) if rows else 0.0 for key in keys}


def evaluate_benchmark(benchmark: list[dict[str, Any]], law_retriever, case_retriever, top_k: int = 5) -> dict[str, Any]:
    baseline_rows: list[dict[str, Any]] = []
    enhanced_rows: list[dict[str, Any]] = []
    for item in benchmark:
        query = item["query"]
        laws = law_retriever.search(query, limit=top_k)
        cases = case_retriever.search(query, top_k=top_k, mode="keyword")
        baseline_context = make_law_context(laws)
        enhanced_context = make_law_context(laws, cases)
        baseline_generation = generation_metrics(query, baseline_context, GroundedGenerator(MockRAGProvider(), max_retries=0))
        enhanced_generation = generation_metrics(query, enhanced_context, GroundedGenerator(MockRAGProvider(), max_retries=0))
        baseline_rows.append({"id": item["id"], "query": query, "law_recall_at_k": law_recall(laws, item.get("expected_law_terms", [])), "case_recall_at_k": 0.0, **baseline_generation})
        enhanced_rows.append({"id": item["id"], "query": query, "law_recall_at_k": law_recall(laws, item.get("expected_law_terms", [])), "case_recall_at_k": case_recall(cases, item.get("expected_case_ids", [])), **enhanced_generation})
    return {
        "generation_mode": "deterministic MockRAGProvider with existing citation validator",
        "top_k": top_k,
        "baseline": {"per_query": baseline_rows, "aggregate": aggregate(baseline_rows)},
        "enhanced": {"per_query": enhanced_rows, "aggregate": aggregate(enhanced_rows)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, default=Path(__file__).with_name("benchmark_cases.json"))
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/case_augmented_rag/results.json")
    parser.add_argument("--summary", type=Path, default=ROOT / "evaluation/case_augmented_rag/summary.md")
    args = parser.parse_args()
    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    result = evaluate_benchmark(benchmark, HybridRetriever(), RuntimeCaseRetriever())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    b, e = result["baseline"]["aggregate"], result["enhanced"]["aggregate"]
    args.summary.write_text("# Case-Augmented RAG Evaluation\n\n" +
                            "Deterministic offline comparison using the existing law retriever, runtime case retriever, MockRAGProvider, and citation validator.\n\n" +
                            f"- Queries: {len(benchmark)}\n- Baseline law Recall@K: {b['law_recall_at_k']}\n- Enhanced case Recall@K: {e['case_recall_at_k']}\n- Baseline answer success: {b['answer_success_rate']}\n- Enhanced answer success: {e['answer_success_rate']}\n", encoding="utf-8")
    print(json.dumps({"baseline": b, "enhanced": e}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
