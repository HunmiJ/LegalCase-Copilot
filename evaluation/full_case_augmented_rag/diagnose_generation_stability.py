"""Record per-attempt real generation diagnostics without storing model text."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import OpenAICompatibleProvider
from backend.rag.pipeline import LegalRAGPipeline
from scripts.hybrid_utils import HybridRetriever
from scripts.reranker_utils import load_reranker

QUERY_FILE = ROOT / "evaluation/full_case_augmented_rag/generation_queries.json"
REPORT_FILE = ROOT / "docs/v1.5.3_real_generation_stability_analysis.md"


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def retry_reason(attempt: dict) -> str:
    if attempt.get("exception_type"):
        return f"provider_or_transport_exception:{attempt['exception_type']}"
    if not attempt.get("json_parse_success"):
        return "invalid_json"
    if not attempt.get("schema_validation_success"):
        return "schema_validation_failed"
    if not attempt.get("citation_validation_success"):
        errors = attempt.get("citation_errors") or []
        return "citation_validation_failed:" + " | ".join(errors[:3])
    return "none"


def run_mode(label: str, pipeline: LegalRAGPipeline, queries: list[dict]) -> list[dict]:
    records = []
    for item in queries:
        try:
            result = pipeline.ask(item["query"])
            meta = result.get("generation_meta") or {}
            response = result.get("response") or {}
            context_ids = [entry.get("citation_id") for entry in result.get("context", {}).get("items", [])]
            attempts = []
            for attempt in meta.get("attempts") or []:
                attempts.append({
                    "attempt_number": attempt.get("attempt_number"),
                    "provider_request_success": attempt.get("provider_request_success"),
                    "provider_http_api_success": attempt.get("http_api_success"),
                    "response_empty": attempt.get("response_empty"),
                    "response_truncated": attempt.get("response_truncated"),
                    "response_structure_type": attempt.get("raw_response_structure_type"),
                    "json_parse_success": attempt.get("json_parse_success"),
                    "schema_validation_success": attempt.get("schema_validation_success"),
                    "citation_validation_success": attempt.get("citation_validation_success"),
                    "citation_errors": (attempt.get("citation_errors") or [])[:10],
                    "retry_trigger_reason": retry_reason(attempt),
                })
            records.append({
                "query": item["query"], "mode": label,
                "allowed_citation_ids": context_ids, "attempts": attempts,
                "final_generation_status": response.get("generation_status"),
                "final_failure_reason": response.get("failure_reason") or response.get("generation_status"),
                "retry_count": meta.get("retry_count"),
            })
        except Exception as exc:
            records.append({"query": item["query"], "mode": label,
                            "allowed_citation_ids": [], "attempts": [],
                            "final_generation_status": "provider_exception",
                            "final_failure_reason": f"{type(exc).__name__}: {str(exc)[:200]}",
                            "retry_count": None})
    return records


def main() -> None:
    load_dotenv()
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))[:5]
    provider = OpenAICompatibleProvider()
    retriever = HybridRetriever()
    reranker = load_reranker(local_files_only=True)
    law_pipeline = LegalRAGPipeline(provider, retriever=retriever, reranker=reranker, include_cases=False)
    case_pipeline = LegalRAGPipeline(provider, retriever=retriever, reranker=reranker, include_cases=True,
                                     case_corpus_path=ROOT / "data/processed/full_cases")
    records = run_mode("law-only", law_pipeline, queries) + run_mode("law+6492-cases", case_pipeline, queries)
    counts = {}
    for record in records:
        for attempt in record["attempts"]:
            reason = attempt["retry_trigger_reason"].split(":", 1)[0]
            counts[reason] = counts.get(reason, 0) + 1
    lines = [
        "# V1.5.3 Real Generation Stability Analysis", "",
        "## 范围", "",
        "对与V1.5.2相同的5条 query，分别运行法规-only和法规+6492案例模式；每次只记录 provider/HTTP 状态、解析和校验状态，不保存完整响应、API Key、Authorization 或配置值。", "",
        "## 每次 generation attempt", "",
    ]
    for index, record in enumerate(records, 1):
        lines.extend([
            f"### {index}. {record['mode']}｜{record['query']}", "",
            f"- allowed citation IDs：`{', '.join(record['allowed_citation_ids']) or '未获取'}`",
            f"- final：`{record['final_generation_status']}`；failure reason：`{record['final_failure_reason'] or '—'}`；retry_count：`{record['retry_count']}`", "",
            "| attempt | provider返回 | HTTP成功 | JSON | schema | citation | retry触发原因 | citation错误 |",
            "|---:|---|---|---|---|---|---|---|",
        ])
        if not record["attempts"]:
            lines.append("| — | 未捕获 | 未捕获 | 未捕获 | 未捕获 | 未捕获 | provider exception | — |")
        for attempt in record["attempts"]:
            errors = "；".join(attempt["citation_errors"]).replace("|", "／") or "—"
            lines.append(f"| {attempt['attempt_number']} | {attempt['provider_request_success']} | {attempt['provider_http_api_success']} | {attempt['json_parse_success']} | {attempt['schema_validation_success']} | {attempt['citation_validation_success']} | {attempt['retry_trigger_reason']} | {errors} |")
        lines.append("")
    lines.extend([
        "## 失败分类", "",
        f"本次 attempt 触发原因计数：`{json.dumps(counts, ensure_ascii=False)}`。A=provider/transport exception；B=invalid_json；C=schema_validation_failed；D/E=citation_validation_failed；F=所有尝试耗尽后仍失败。", "",
        "- A provider/network失败：provider 请求未成功或出现异常。",
        "- B JSON格式错误：响应无法被 JSON parser 解析。",
        "- C schema字段缺失/类型错误：JSON 可解析但不符合结构化 schema。",
        "- D citation格式错误：citation 形态不符合可安全规范化的格式。",
        "- E 不存在的 LAW/CASE ID：citation validator 找不到对应 context item。",
        "- F retry 后仍无法满足要求：所有尝试耗尽后仍未通过 schema/citation 或 provider 失败。", "",
        "## 说明", "",
        "本报告由真实 provider 运行生成。若当前网络导致某些 attempt 无法捕获，相关字段明确标记为未捕获，不用推测内容补齐。",
    ])
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"record_count": len(records), "attempt_failure_counts": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
