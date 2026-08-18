"""V0.6.1 real generation smoke set with sanitized per-query metrics."""

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


def load_dotenv():
    for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"LEGALCASE_LLM_BASE_URL", "LEGALCASE_LLM_API_KEY", "LEGALCASE_LLM_MODEL"}:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("LEGALCASE_LLM_BASE_URL", "LEGALCASE_LLM_API_KEY", "LEGALCASE_LLM_MODEL"):
        if not os.environ.get(key):
            raise RuntimeError("missing real provider configuration")


QUERIES = [
    ("in01", "公司工作两年突然把我辞退了，没有提前通知，也不给补偿怎么办？", "in_domain"),
    ("in02", "公司一直让我加班但是不给加班费怎么办？", "in_domain"),
    ("in03", "公司工作半年一直没有跟我签劳动合同怎么办？", "in_domain"),
    ("in04", "试用期公司可以没有理由直接辞退我吗？", "in_domain"),
    ("in05", "签了竞业限制协议，但是离职以后公司不给补偿怎么办？", "in_domain"),
    ("in06", "劳动仲裁是不是超过一年就不能申请了？", "in_domain"),
    ("safe01", "我租房押金不退怎么办？", "out_of_domain"),
    ("safe02", "劳动合同法第999条是什么？", "unverifiable_article"),
    ("safe03", "公司这样做合法吗？", "insufficient"),
]


def row_metrics(result: dict) -> dict:
    response = result["response"]
    validation = result["generation_meta"].get("validation", {})
    claims = response.get("legal_analysis", [])
    grounded = sum(bool(item.get("citations")) for item in claims)
    errors = validation.get("errors", [])
    unsupported = sum("unsupported citation" in error or "outside context" in error for error in errors)
    return {
        "generation_status": response.get("generation_status"),
        "generation_success": response.get("generation_status") == "success",
        "retry_count": result["generation_meta"].get("retry_count", 0),
        "fallback": result["generation_meta"].get("fallback", False),
        "citation_validation": validation,
        "unsupported_citation_count": unsupported,
        "grounded_claim_count": grounded,
        "grounded_claim_rate": grounded / len(claims) if claims else 1.0,
        "context_article_count": result["context"].get("article_count", 0),
        "context_char_count": result["context"].get("char_count", 0),
        "latency_breakdown_ms": result.get("latency_breakdown_ms", {}),
        "response": response,
        "context": result["context"],
    }


def main():
    load_dotenv()
    provider = OpenAICompatibleProvider()
    pipeline = LegalRAGPipeline(provider)
    rows = []
    for query_id, query, category in QUERIES:
        start = time.perf_counter()
        try:
            result = pipeline.ask(query)
            row = {"query_id": query_id, "query": query, "category": category, "status": "completed",
                   **row_metrics(result), "wall_clock_ms": (time.perf_counter() - start) * 1000}
        except Exception:
            row = {"query_id": query_id, "query": query, "category": category, "status": "pipeline_error",
                   "error_type": "provider_or_pipeline_error", "wall_clock_ms": (time.perf_counter() - start) * 1000}
        rows.append(row)
        print(f"{query_id} {row['status']} {row.get('generation_status', '')} retry={row.get('retry_count', '')}")
    in_domain = [row for row in rows if row["category"] == "in_domain"]
    generation_latencies = [row["latency_breakdown_ms"].get("generation", 0.0) for row in rows if row["status"] == "completed"]
    total_latencies = [row["latency_breakdown_ms"].get("total", 0.0) for row in rows if row["status"] == "completed"]
    no_retry = [row["latency_breakdown_ms"]["total"] for row in in_domain if row.get("retry_count", 0) == 0]
    with_retry = [row["latency_breakdown_ms"]["total"] for row in in_domain if row.get("retry_count", 0) > 0]
    report = {
        "provider": "real_llm",
        "model": provider.model,
        "query_count": len(rows),
        "in_domain_generation_success_count": sum(row.get("generation_success", False) for row in in_domain),
        "in_domain_retry_count": sum(row.get("retry_count", 0) > 0 for row in in_domain),
        "in_domain_fallback_count": sum(row.get("fallback", False) for row in in_domain),
        "average_expanded_query_count": None,
        "latency_ms": {
            "generation_average": statistics.mean(generation_latencies) if generation_latencies else 0.0,
            "total_average": statistics.mean(total_latencies) if total_latencies else 0.0,
            "in_domain_no_retry_total_average": statistics.mean(no_retry) if no_retry else None,
            "in_domain_with_retry_total_average": statistics.mean(with_retry) if with_retry else None,
        },
        "rows": rows,
    }
    output = ROOT / "evaluation/results/v0.6_real_generation_results.json"
    summary = ROOT / "evaluation/results/v0.6_real_generation_summary.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# V0.6.1 Real RAG Generation Validation", "", f"Model: `{provider.model}`", f"Queries: {len(rows)}", "", "## In-domain results", f"- Generation success: {report['in_domain_generation_success_count']}/{len(in_domain)}", f"- Queries with retry: {report['in_domain_retry_count']}", f"- Fallback count: {report['in_domain_fallback_count']}", f"- No-retry total latency average: {report['latency_ms']['in_domain_no_retry_total_average']}", f"- Retry total latency average: {report['latency_ms']['in_domain_with_retry_total_average']}", "", "## Safety results"]
    for row in rows:
        if row["category"] != "in_domain":
            lines.append(f"- {row['query_id']}: `{row.get('generation_status', row['status'])}`")
    lines += ["", "## Per-query summary", "", "| ID | Category | Generation | Retry | Fallback | Citation valid | Unsupported citations | Grounded claims | Total ms |", "|---|---|---|---:|---:|---|---:|---:|---:|"]
    for row in rows:
        validation = row.get("citation_validation", {})
        lines.append(f"| {row['query_id']} | {row['category']} | {row.get('generation_status', row['status'])} | {row.get('retry_count', '')} | {row.get('fallback', '')} | {validation.get('valid', '')} | {row.get('unsupported_citation_count', '')} | {row.get('grounded_claim_count', '')} | {row.get('latency_breakdown_ms', {}).get('total', '')} |")
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE {output}")
    print(f"WROTE {summary}")
    return 0 if all(row["status"] == "completed" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
