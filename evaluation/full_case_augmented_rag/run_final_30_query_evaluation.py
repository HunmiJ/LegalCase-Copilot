"""Frozen 30-query real generation evaluation; stores metrics, not model text."""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import OpenAICompatibleProvider
from backend.rag.pipeline import LegalRAGPipeline
from scripts.hybrid_utils import HybridRetriever
from scripts.reranker_utils import load_reranker

QUERY_FILE = ROOT / "evaluation/full_case_augmented_rag/generation_queries.json"
OUTPUT_FILE = ROOT / "evaluation/full_case_augmented_rag/final_generation_metrics.json"
REPORT_FILE = ROOT / "docs/final_30_query_real_evaluation.md"


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower, upper = int(index), min(int(index) + 1, len(ordered) - 1)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower), 2)


def failure_taxonomy(response: dict, meta: dict) -> tuple[str | None, str | None]:
    if response.get("generation_status") == "success" and not meta.get("fallback", False):
        return None, None
    attempts = meta.get("attempts", [])
    details = []
    for attempt in attempts:
        if not attempt.get("provider_request_success") or attempt.get("exception_type") in {"ProviderError", "TimeoutError", "URLError"}:
            details.append("provider_failure")
        if attempt.get("json_parse_success") is False and attempt.get("response_empty") is not True:
            details.append("JSON_failure")
        error = str(attempt.get("error_detail") or "")
        citation_errors = " ".join(str(item) for item in attempt.get("citation_errors", []))
        text = (error + " " + citation_errors).lower()
        if "unsafe unsupported article" in text:
            details.append("unsafe_article_mention")
        elif "article mention" in text:
            details.append("unsupported_citation")
        elif "unsupported citation" in text:
            details.append("unsupported_citation")
        if "schema" in text or "generation contract" in text or "legal_analysis" in text or "claim" in text:
            details.append("schema_failure")
    detail = Counter(details).most_common(1)[0][0] if details else None
    final_reason = response.get("failure_reason") or response.get("generation_status")
    if final_reason == "generation_failed_after_retries":
        return "generation_failed_after_retries", detail
    return final_reason or "other", detail


def law_accuracy(response: dict, context: dict, expected: list[str]) -> float | None:
    if not expected:
        return None
    by_id = {item.get("citation_id"): item for item in context.get("items", [])}
    names = []
    for item in response.get("legal_basis", []):
        source = by_id.get(item.get("citation"))
        if source and source.get("type", "law") == "law":
            names.append(str(source.get("law_name") or ""))
    return round(sum(any(law in name or name in law for name in names) for law in expected) / len(expected), 4)


def case_accuracy(response: dict, expected_topics: list[str]) -> float | None:
    if not expected_topics:
        return None
    cited = response.get("related_cases", [])
    text = " ".join(str(item.get(key) or "") for item in cited for key in ("title", "reasoning", "dispute_focus"))
    return round(sum(topic in text for topic in expected_topics) / len(expected_topics), 4)


def run_mode(label: str, pipeline: LegalRAGPipeline, queries: list[dict]) -> dict:
    rows = []
    for index, item in enumerate(queries, 1):
        start = time.perf_counter()
        try:
            result = pipeline.ask(item["query"])
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            response = result.get("response") or {}
            meta = result.get("generation_meta") or {}
            validation = meta.get("validation") or {}
            success = response.get("generation_status") == "success" and not meta.get("fallback", False)
            final_failure, underlying_failure = failure_taxonomy(response, meta)
            rows.append({
                "query_id": index,
                "generation_success": success,
                "citation_validity": validation.get("citation_validity") if success else None,
                "legal_basis_accuracy": law_accuracy(response, result.get("context") or {}, item.get("expected_laws", [])) if success else None,
                "case_reference_accuracy": case_accuracy(response, item.get("expected_case_topics", [])) if success else None,
                "unsupported_claim_rate": validation.get("unsupported_citation_rate") if success else None,
                "sanitation_count": len(meta.get("sanitation_events") or []),
                "failure_taxonomy": final_failure,
                "underlying_failure_taxonomy": underlying_failure,
                "latency_ms": elapsed,
                "context_chars": (result.get("context") or {}).get("char_count"),
            })
        except Exception as exc:
            rows.append({
                "query_id": index, "generation_success": False,
                "citation_validity": None, "legal_basis_accuracy": None,
                "case_reference_accuracy": None, "unsupported_claim_rate": None,
                "sanitation_count": 0, "failure_taxonomy": "provider_failure",
                "underlying_failure_taxonomy": type(exc).__name__,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                "context_chars": None,
            })
    successful = [row for row in rows if row["generation_success"]]
    failure_counts = Counter(row["failure_taxonomy"] for row in rows if row["failure_taxonomy"])
    underlying_counts = Counter(row["underlying_failure_taxonomy"] for row in rows if row["underlying_failure_taxonomy"])
    latencies = [row["latency_ms"] for row in rows]
    def mean(field: str) -> float | None:
        values = [row[field] for row in successful if row[field] is not None]
        return round(sum(values) / len(values), 4) if values else None
    return {
        "query_count": len(queries),
        "generation_success_rate": round(len(successful) / len(rows), 4) if rows else None,
        "citation_validity": mean("citation_validity"),
        "legal_basis_accuracy": mean("legal_basis_accuracy"),
        "case_reference_accuracy": mean("case_reference_accuracy"),
        "unsupported_claim_rate": mean("unsupported_claim_rate"),
        "unsupported_citation_count": failure_counts.get("unsupported_citation", 0),
        "unsupported_citation_rate": round(failure_counts.get("unsupported_citation", 0) / len(rows), 4) if rows else None,
        # Schema failures are retained as an underlying retry cause even
        # when the final user-visible outcome is generation_failed_after_retries.
        "schema_failure_count": underlying_counts.get("schema_failure", 0),
        "schema_failure_rate": round(underlying_counts.get("schema_failure", 0) / len(rows), 4) if rows else None,
        "article_sanitation_count": sum(row["sanitation_count"] for row in rows),
        "article_sanitation_rate": round(sum(row["sanitation_count"] for row in rows) / len(rows), 4) if rows else None,
        "generation_failed_after_retries_count": failure_counts.get("generation_failed_after_retries", 0),
        "generation_failed_after_retries_rate": round(failure_counts.get("generation_failed_after_retries", 0) / len(rows), 4) if rows else None,
        "average_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "failure_taxonomy": dict(failure_counts),
        "underlying_failure_taxonomy": dict(underlying_counts),
        "per_query": rows,
    }


def main() -> None:
    load_dotenv()
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    output = {
        "evaluation": "Final 30-Query Real Generation Evaluation",
        "query_count": len(queries), "total_runs": len(queries) * 2,
        "provider": None, "modes": {},
        "limitations": [
            "legal_basis_accuracy 仅验证引用法规与expected_laws名称的自动匹配，不是人工法律正确率。",
            "case_reference_accuracy 仅验证被引用案例元数据/文本与expected_case_topics的自动词项匹配，不是专家判定的类案相似度。",
            "unsupported_claim_rate 来自自动citation/claim validator，不是人工逐句事实核验。",
            "本评测未保存完整prompt、context或LLM response，也未使用mock、人工补写或失败样本排除。",
        ],
    }
    try:
        provider = OpenAICompatibleProvider()
        output["provider"] = {"name": provider.name, "model": provider.model,
                               "base_url_configured": bool(provider.config.base_url),
                               "temperature": 0, "timeout_seconds": provider.config.timeout_seconds,
                               "retry_count": 2, "stream": False}
        retriever = HybridRetriever()
        reranker = load_reranker(local_files_only=True)
        law_pipeline = LegalRAGPipeline(provider, retriever=retriever, reranker=reranker, include_cases=False)
        full_pipeline = LegalRAGPipeline(provider, retriever=retriever, reranker=reranker,
                                          include_cases=True, case_corpus_path=ROOT / "data/processed/full_cases")
        output["modes"]["law_only"] = run_mode("law-only", law_pipeline, queries)
        output["modes"]["law_plus_6492_cases"] = run_mode("law+6492-cases", full_pipeline, queries)
    except Exception as exc:
        output["provider_error"] = type(exc).__name__
        output["limitations"].append("真实provider初始化或评测运行失败；没有使用mock替代。")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    law = output["modes"].get("law_only", {})
    cases = output["modes"].get("law_plus_6492_cases", {})
    names = ["generation_success_rate", "citation_validity", "unsupported_citation_count", "unsupported_citation_rate",
             "schema_failure_count", "schema_failure_rate", "article_sanitation_count", "article_sanitation_rate",
             "generation_failed_after_retries_count", "generation_failed_after_retries_rate", "average_latency_ms",
             "p50_latency_ms", "p95_latency_ms", "legal_basis_accuracy", "case_reference_accuracy", "unsupported_claim_rate"]
    def value(data: dict, key: str) -> str:
        return "—" if data.get(key) is None else str(data.get(key))
    table = "\n".join(f"| {name} | {value(law, name)} | {value(cases, name)} |" for name in names)
    report = f"""# Final 30-Query Real Generation Evaluation

## 实验环境

- 固定测试问题：{len(queries)} 条；模式：法规-only、法规+6492 cases；总 production generation：{len(queries) * 2} 次。
- 当前最终链路：retrieval → reranker → generation context budget → DeepSeek → JSON parser → schema normalization → article sanitizer → citation validator → deterministic citation metadata rendering。
- provider：`{(output.get('provider') or {}).get('name', '未初始化')}`；model：`{(output.get('provider') or {}).get('model', '未初始化')}`。
- 生成参数：temperature `{(output.get('provider') or {}).get('temperature', '—')}`，timeout `{(output.get('provider') or {}).get('timeout_seconds', '—')}s`，retry `{(output.get('provider') or {}).get('retry_count', '—')}`，stream `{(output.get('provider') or {}).get('stream', '—')}`。

## 指标对比

| 指标 | law-only | law+6492-cases |
|---|---:|---:|
{table}

所有失败样本均保留在分母中。`citation_validity` 仅对成功响应求均值；无成功响应时显示为 `—`。

## Failure taxonomy

### law-only

- final taxonomy：`{json.dumps(law.get('failure_taxonomy', {}), ensure_ascii=False)}`
- underlying taxonomy：`{json.dumps(law.get('underlying_failure_taxonomy', {}), ensure_ascii=False)}`

### law+6492-cases

- final taxonomy：`{json.dumps(cases.get('failure_taxonomy', {}), ensure_ascii=False)}`
- underlying taxonomy：`{json.dumps(cases.get('underlying_failure_taxonomy', {}), ensure_ascii=False)}`

## 结果解释

报告不预设案例增强一定改善结果。应重点比较成功率、citation validity、条号 sanitation、失败类型和延迟；案例是否进入答案仅以模型实际选择并通过 validator 的 CASE citation 及其确定性 metadata 为准，未被模型引用的案例不会计入引用。

## 自动评测限制

{chr(10).join('- ' + item for item in output['limitations'])}

逐问题安全摘要保存在 `{OUTPUT_FILE.relative_to(ROOT).as_posix()}`，不包含完整模型输出或完整 context。
"""
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
