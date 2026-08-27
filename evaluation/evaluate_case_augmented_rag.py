"""Evaluate the law-only and case-augmented RAG modes on integrated queries."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from backend.rag.pipeline import LegalRAGPipeline


QUERIES = ROOT / "evaluation/case_augmented_rag/integrated_queries.json"
OUTPUT = ROOT / "evaluation/results/case_augmented_rag_metrics.json"
CONTEXT_RE = re.compile(r"\[(LAW-\d+|CASE-\d+)\]")


class DeterministicEvaluationProvider:
    """Evaluation-only provider; it makes no network or model calls."""

    def complete(self, messages, response_format=None, temperature=0):
        context = messages[-1]["content"].split("本次唯一可用 context：", 1)[-1]
        citations = list(dict.fromkeys(CONTEXT_RE.findall(context)))
        legal_analysis = [{"claim": "检索上下文包含与该问题相关的依据。", "citations": [citation]}
                          for citation in citations[:2]]
        return json.dumps({
            "issue_summary": ["问题涉及劳动争议法律与类案依据。"],
            "legal_analysis": legal_analysis,
            "relevant_laws": [],
            "missing_information": ["仍需结合完整事实和证据判断。"],
            "next_steps": ["核对检索到的法规和案例来源。"],
            "disclaimer": "仅供法律信息检索参考，不构成确定性法律意见。",
        }, ensure_ascii=False)


def _recall(found: set[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    return sum(any(term in candidate for candidate in found) for term in expected) / len(expected)


def evaluate_mode(queries: list[dict[str, Any]], include_cases: bool) -> dict[str, Any]:
    pipeline = LegalRAGPipeline(DeterministicEvaluationProvider(), include_cases=include_cases)
    rows = []
    for item in queries:
        started = time.perf_counter()
        result = pipeline.ask(item["query"])
        context = result["context"]
        laws = {str(row.get("law_name") or "") for row in context.get("law_items", [])}
        cases = {str(row.get("case_id") or "") for row in context.get("case_items", [])}
        validation = result["generation_meta"]["validation"]
        rows.append({
            "query": item["query"],
            "law_recall": _recall(laws, item.get("expected_laws", [])),
            "case_recall": _recall(cases, item.get("expected_cases", [])) if include_cases else 0.0,
            "citation_validity": validation["citation_validity"],
            "grounded_claim_rate": validation["grounded_claim_rate"],
            "unsupported_claim_rate": validation["unsupported_citation_rate"],
            "context": context,
            "latency_ms": (time.perf_counter() - started) * 1000,
        })

    def average(name: str) -> float:
        return round(sum(float(row[name]) for row in rows) / len(rows), 4) if rows else 0.0

    return {
        "mode": "law_plus_case" if include_cases else "law_only",
        "query_count": len(rows),
        "metrics": {name: average(name) for name in (
            "law_recall", "case_recall", "citation_validity",
            "grounded_claim_rate", "unsupported_claim_rate",
        )},
        "average_latency_ms": round(sum(row["latency_ms"] for row in rows) / len(rows), 2) if rows else 0.0,
        "rows": rows,
    }


def main() -> int:
    queries = json.loads(QUERIES.read_text(encoding="utf-8"))
    if len(queries) < 20:
        raise ValueError("integrated query set must contain at least 20 queries")
    law_only = evaluate_mode(queries, include_cases=False)
    augmented = evaluate_mode(queries, include_cases=True)
    comparison = {
        name: round(augmented["metrics"][name] - law_only["metrics"][name], 4)
        for name in augmented["metrics"]
    }
    output = {
        "query_count": len(queries),
        "law_only": law_only,
        "law_plus_case": augmented,
        "delta_law_plus_case_minus_law_only": comparison,
        "case_augmented_improved": (
            augmented["metrics"]["case_recall"] > law_only["metrics"]["case_recall"]
            and augmented["metrics"]["law_recall"] >= law_only["metrics"]["law_recall"]
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "query_count": len(queries),
        "law_only": law_only["metrics"],
        "law_plus_case": augmented["metrics"],
        "improved": output["case_augmented_improved"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
