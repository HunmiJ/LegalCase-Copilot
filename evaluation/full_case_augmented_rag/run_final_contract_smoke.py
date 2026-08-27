"""Run the fixed five-query final-contract smoke test with safe summaries only."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import OpenAICompatibleProvider
from backend.rag.pipeline import LegalRAGPipeline
from scripts.hybrid_utils import HybridRetriever
from scripts.reranker_utils import load_reranker

QUERY_FILE = ROOT / "evaluation/full_case_augmented_rag/generation_queries.json"
REPORT_FILE = ROOT / "docs/final_generation_contract_report.md"


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def classify_failure(response: dict, meta: dict) -> str | None:
    if response.get("generation_status") == "success" and not meta.get("fallback"):
        return None
    reasons = []
    for attempt in meta.get("attempts", []):
        detail = str(attempt.get("error_detail") or "")
        reasons.append(detail)
        reasons.extend(str(error) for error in attempt.get("citation_errors", []))
    text = " ".join(reasons).lower()
    if "unsupported citation" in text or "article mention" in text:
        return "unsupported_citation"
    if ("missing fields" in text or "generation contract" in text or "schema" in text
            or "legal_analysis" in text or "claim" in text):
        return "required_field_failure"
    if any(term in text for term in ("timeout", "urlerror", "connection", "provider")):
        return "provider_or_transport_failure"
    return response.get("failure_reason") or response.get("generation_status") or "other"


def run_mode(label: str, pipeline: LegalRAGPipeline, queries: list[dict], repeats: int) -> dict:
    rows = []
    shape_counts = {}
    stage_counts = {"provider_success": 0, "json_parse_success": 0,
                    "schema_success": 0, "citation_validation_success": 0}
    for query_index, item in enumerate(queries, 1):
        for repeat in range(1, repeats + 1):
            start = time.perf_counter()
            try:
                result = pipeline.ask(item["query"])
                elapsed = round((time.perf_counter() - start) * 1000, 2)
                response = result.get("response") or {}
                meta = result.get("generation_meta") or {}
                validation = meta.get("validation") or {}
                for attempt in meta.get("attempts", []):
                    shape = attempt.get("legal_analysis_shape")
                    if shape:
                        shape_counts[shape] = shape_counts.get(shape, 0) + 1
                    for stage in stage_counts:
                        if attempt.get({
                            "provider_success": "provider_request_success",
                            "json_parse_success": "json_parse_success",
                            "schema_success": "schema_validation_success",
                            "citation_validation_success": "citation_validation_success",
                        }[stage]):
                            stage_counts[stage] += 1
                success = response.get("generation_status") == "success" and not meta.get("fallback", False)
                rows.append({
                    "query_id": query_index, "mode": label, "repeat": repeat,
                    "generation_success": success,
                    "citation_validity": validation.get("citation_validity") if success else None,
                    "normalization_count": sum(int(attempt.get("normalization_count") or 0) for attempt in meta.get("attempts", [])),
                    "sanitation_count": len(meta.get("sanitation_events") or []),
                    "unsupported_citation": classify_failure(response, meta) == "unsupported_citation",
                    "required_field_failure": classify_failure(response, meta) == "required_field_failure",
                    "generation_failed_after_retries": response.get("failure_reason") == "generation_failed_after_retries",
                    "failure_reason": classify_failure(response, meta),
                    "latency_ms": elapsed,
                    "context_chars": (result.get("context") or {}).get("char_count"),
                })
            except Exception as exc:
                rows.append({
                    "query_id": query_index, "mode": label, "repeat": repeat,
                    "generation_success": False, "citation_validity": None,
                    "sanitation_count": 0, "unsupported_citation": False,
                    "required_field_failure": False, "generation_failed_after_retries": False,
                    "failure_reason": f"{type(exc).__name__}",
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                    "context_chars": None,
                })
    successes = [row for row in rows if row["generation_success"]]
    return {
        "mode": label, "attempt_count": len(rows),
        "generation_success_rate": round(len(successes) / len(rows), 4) if rows else None,
        "citation_validity": round(sum(row["citation_validity"] for row in successes) / len(successes), 4) if successes else None,
        "sanitation_count": sum(row["sanitation_count"] for row in rows),
        "normalization_count": sum(row["normalization_count"] for row in rows),
        "unsupported_citation_count": sum(row["unsupported_citation"] for row in rows),
        "required_field_failure_count": sum(row["required_field_failure"] for row in rows),
        "generation_failed_after_retries_count": sum(row["generation_failed_after_retries"] for row in rows),
        "average_latency_ms": round(sum(row["latency_ms"] for row in rows) / len(rows), 2) if rows else None,
        "legal_analysis_shape_frequency": shape_counts,
        "stage_success_counts": stage_counts,
        "per_run": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    load_dotenv()
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))[:5]
    output = {"query_count": len(queries), "repeats": args.repeats,
              "total_generation_runs": len(queries) * 2 * args.repeats,
              "provider": None, "modes": {}, "limitations": [
                  "本报告只统计固定5条问题的重复smoke，不代表30条正式评测。",
                  "未保存完整LLM响应、法规/案例context或凭据；质量指标不是人工法律意见评分。",
              ]}
    try:
        provider = OpenAICompatibleProvider()
        output["provider"] = {"name": provider.name, "model": provider.model,
                               "base_url_configured": bool(provider.config.base_url),
                               "temperature": 0, "timeout_seconds": provider.config.timeout_seconds,
                               "retry_count": 2, "stream": False}
        retriever = HybridRetriever()
        reranker = load_reranker(local_files_only=True)
        law_pipeline = LegalRAGPipeline(provider, retriever=retriever, reranker=reranker,
                                         include_cases=False)
        case_pipeline = LegalRAGPipeline(provider, retriever=retriever, reranker=reranker,
                                          include_cases=True,
                                          case_corpus_path=ROOT / "data/processed/full_cases")
        output["modes"]["law_only"] = run_mode("law-only", law_pipeline, queries, args.repeats)
        output["modes"]["law_plus_6492_cases"] = run_mode("law+6492-cases", case_pipeline, queries, args.repeats)
    except Exception as exc:
        output["provider_error"] = f"{type(exc).__name__}"
        output["limitations"].append("真实provider初始化或smoke运行失败；未用mock替代。")

    def mode(name: str) -> dict:
        return output["modes"].get(name, {})

    before = "V1.5.8 最近一次正常重试 smoke：law-only 0/5，law+6492-cases 0/5；该基线未使用本次确定性元数据渲染。"
    report = f"""# Final Generation Contract Refactor Report

## 运行范围

- 固定问题：5 条；每种模式重复：{args.repeats} 次；总 production generation runs：{output['total_generation_runs']}。
- 模式：法规-only、法规+6492案例。
- 完整链路：provider → JSON parser → schema → sanitizer → 严格 citation validator → deterministic metadata rendering。
- 真实provider配置仅摘要记录：{(output.get('provider') or {}).get('name', '未初始化')}，不写入密钥或完整响应。

## 修改前后 smoke 对比

| 指标 | V1.5.8基线 | law-only本次 | law+6492本次 |
|---|---:|---:|---:|
| generation success rate | 0.0000 | {mode('law_only').get('generation_success_rate', '—')} | {mode('law_plus_6492_cases').get('generation_success_rate', '—')} |
| citation validity（成功响应） | — | {mode('law_only').get('citation_validity', '—')} | {mode('law_plus_6492_cases').get('citation_validity', '—')} |
| sanitation events | — | {mode('law_only').get('sanitation_count', '—')} | {mode('law_plus_6492_cases').get('sanitation_count', '—')} |
| unsupported citation failures | — | {mode('law_only').get('unsupported_citation_count', '—')} | {mode('law_plus_6492_cases').get('unsupported_citation_count', '—')} |
| required field failures | — | {mode('law_only').get('required_field_failure_count', '—')} | {mode('law_plus_6492_cases').get('required_field_failure_count', '—')} |
| generation failed after retries | — | {mode('law_only').get('generation_failed_after_retries_count', '—')} | {mode('law_plus_6492_cases').get('generation_failed_after_retries_count', '—')} |
| average latency (ms) | — | {mode('law_only').get('average_latency_ms', '—')} | {mode('law_plus_6492_cases').get('average_latency_ms', '—')} |

基线说明：{before}

## 契约与安全结论

- 模型只选择已在当前 context 中存在的 LAW-* / CASE-* ID；法规名称、条号、案例标题、法院和日期由真实 retrieval metadata 确定性渲染。
- 不存在的 citation ID 仍被拒绝；未被模型引用的 source 不展示为引用。
- 不支持的正文具体条号仅在可安全替换时记录 sanitation event 并重新校验；范围/嵌套条款等无法安全处理的内容仍拒绝。
- citation validator 的严格规则未放宽，失败响应未标记为成功。

## legal_analysis shape 与阶段统计

### law-only

- shape frequency：`{json.dumps(mode('law_only').get('legal_analysis_shape_frequency', {}), ensure_ascii=False)}`
- stage success counts：`{json.dumps(mode('law_only').get('stage_success_counts', {}), ensure_ascii=False)}`

### law+6492-cases

- shape frequency：`{json.dumps(mode('law_plus_6492_cases').get('legal_analysis_shape_frequency', {}), ensure_ascii=False)}`
- stage success counts：`{json.dumps(mode('law_plus_6492_cases').get('stage_success_counts', {}), ensure_ascii=False)}`

## pytest

本报告由 smoke 运行器生成；完整 pytest 结果在运行结束后补录。

## 限制与下一步

本次是5条固定问题的重复 smoke，不是最终30条正式评测。只有当两种模式在重复运行中保持稳定成功、成功响应的 citation validity 为1.0且不再由 context外条号主导失败时，才建议进入最终正式评测；否则应停止继续堆叠版本并保留失败样本供后续分析。
"""
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
