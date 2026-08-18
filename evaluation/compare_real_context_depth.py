"""Compare real V0.6 RAG behavior with reranker Top-5 and Top-8 context.

This is an experiment runner only. It does not change the default pipeline,
the retrieval benchmark, citation validation, or source data.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import OpenAICompatibleProvider
from backend.rag import LegalRAGPipeline


def load_dotenv() -> None:
    for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in {"LEGALCASE_LLM_BASE_URL", "LEGALCASE_LLM_API_KEY", "LEGALCASE_LLM_MODEL"}:
            os.environ[key] = value.strip().strip('"').strip("'")
    missing = [key for key in ("LEGALCASE_LLM_BASE_URL", "LEGALCASE_LLM_API_KEY", "LEGALCASE_LLM_MODEL") if not os.environ.get(key)]
    if missing:
        raise RuntimeError("missing real provider configuration: " + ", ".join(missing))


# Diagnostic labels only; these do not alter retrieval or benchmark annotations.
QUERIES = [
    {"query_id": "in01", "query": "公司工作两年突然把我辞退了，没有提前通知，也不给补偿怎么办？", "relevant_articles": ["第四十七条", "第四十八条", "第八十七条"]},
    {"query_id": "in02", "query": "公司一直让我加班但是不给加班费怎么办？", "relevant_articles": ["第三十一条", "第四十四条", "第八十五条"]},
    {"query_id": "in03", "query": "公司工作半年一直没有跟我签劳动合同怎么办？", "relevant_articles": ["第十条", "第八十二条"]},
    {"query_id": "in04", "query": "试用期公司可以没有理由直接辞退我吗？", "relevant_articles": ["第二十一条", "第三十九条", "第四十条"]},
    {"query_id": "in05", "query": "签了竞业限制协议，但是离职以后公司不给补偿怎么办？", "relevant_articles": ["第二十三条", "第二十四条"]},
    {"query_id": "in06", "query": "劳动仲裁是不是超过一年就不能申请了？", "relevant_articles": ["第二十七条"]},
]


def summarize_row(result: dict, expected: list[str], elapsed_ms: float) -> dict:
    context = result["context"]
    context_articles = [item.get("article_number", "") for item in context.get("items", [])]
    present = [article for article in expected if article in context_articles]
    validation = result["generation_meta"].get("validation", {})
    response = result["response"]
    claims = response.get("legal_analysis", [])
    grounded = sum(bool(item.get("citations")) for item in claims)
    errors = validation.get("errors", [])
    unsupported = sum("unsupported citation" in error or "outside context" in error for error in errors)
    breakdown = result.get("latency_breakdown_ms", {})
    return {
        "context_expected_articles": expected,
        "context_present_expected_articles": present,
        "context_coverage": bool(present),
        "context_article_count": context.get("article_count", 0),
        "context_char_count": context.get("char_count", 0),
        "generation_status": response.get("generation_status"),
        "generation_success": response.get("generation_status") == "success",
        "retry_count": result["generation_meta"].get("retry_count", 0),
        "fallback": result["generation_meta"].get("fallback", False),
        "citation_validation": validation,
        "citation_valid": bool(validation.get("valid", False)),
        "grounded_claim_rate": grounded / len(claims) if claims else 1.0,
        "unsupported_citation_count": unsupported,
        "generation_latency_ms": breakdown.get("generation", 0.0),
        "total_latency_ms": breakdown.get("total", elapsed_ms),
        "latency_breakdown_ms": breakdown,
        "response": response,
        "context": context,
    }


def run_depth(provider: OpenAICompatibleProvider, depth: int) -> list[dict]:
    pipeline = LegalRAGPipeline(provider, context_top_k=depth)
    rows = []
    for item in QUERIES:
        start = time.perf_counter()
        try:
            result = pipeline.ask(item["query"])
            row = {"query_id": item["query_id"], "query": item["query"], **summarize_row(result, item["relevant_articles"], (time.perf_counter() - start) * 1000)}
        except Exception:
            row = {"query_id": item["query_id"], "query": item["query"], "status": "pipeline_error", "error_type": "provider_or_pipeline_error"}
        rows.append(row)
        print(f"Top{depth} {item['query_id']}: {row.get('generation_status', row.get('status'))} retry={row.get('retry_count', 0)} fallback={row.get('fallback', False)}")
    return rows


def aggregate(rows: list[dict]) -> dict:
    completed = [row for row in rows if "generation_success" in row]
    if not completed:
        return {"query_count": len(rows)}
    return {
        "query_count": len(completed),
        "retrieval_coverage": sum(row["context_coverage"] for row in completed) / len(completed),
        "generation_success_rate": sum(row["generation_success"] for row in completed) / len(completed),
        "retry_rate": sum(row["retry_count"] > 0 for row in completed) / len(completed),
        "fallback_rate": sum(row["fallback"] for row in completed) / len(completed),
        "citation_validity": sum(row["citation_valid"] for row in completed) / len(completed),
        "grounded_claim_rate": statistics.mean(row["grounded_claim_rate"] for row in completed),
        "unsupported_citation_rate": sum(row["unsupported_citation_count"] > 0 for row in completed) / len(completed),
        "average_generation_latency_ms": statistics.mean(row["generation_latency_ms"] for row in completed),
        "average_total_latency_ms": statistics.mean(row["total_latency_ms"] for row in completed),
        "average_context_articles": statistics.mean(row["context_article_count"] for row in completed),
        "average_context_chars": statistics.mean(row["context_char_count"] for row in completed),
    }


def main() -> int:
    load_dotenv()
    provider = OpenAICompatibleProvider()
    print(f"Real provider: {provider.name}; model: {provider.model}")
    results = {"provider": provider.name, "model": provider.model, "query_count": len(QUERIES), "depths": {}}
    for depth in (5, 8):
        results["depths"][str(depth)] = {"summary": None, "rows": run_depth(provider, depth)}
        results["depths"][str(depth)]["summary"] = aggregate(results["depths"][str(depth)]["rows"])
    output = ROOT / "evaluation/results/v0.6_real_context_depth_comparison.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {output}")
    for depth in (5, 8):
        print(f"Top{depth} summary: {json.dumps(results['depths'][str(depth)]['summary'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
