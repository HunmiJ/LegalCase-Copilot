"""Measure real-generation stability across context and output-shape variants."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import OpenAICompatibleProvider
from backend.rag.citation_validator import validate_citations
from backend.rag.context_builder import build_context
from backend.rag.generator import SYSTEM_PROMPT, normalize_citation_format
from backend.rag.schemas import RAGSchemaError, validate_response
from backend.cases.sources.hybrid_local import LocalHybridCaseProvider
from scripts.hybrid_utils import HybridRetriever
from scripts.reranker_utils import load_reranker, build_candidate_pool, rerank_candidates

QUERY_FILE = ROOT / "evaluation/full_case_augmented_rag/generation_queries.json"
REPORT_FILE = ROOT / "docs/v1.5.5_rag_context_stress_analysis.md"


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 2)) if text else 0


def strip_json_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```") and value.endswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    return value.strip()


def build_retrieval(retriever, reranker, query: str, law_k: int, case_k: int, case_provider=None):
    laws = retriever.search(query, candidate_limit=50, limit=max(law_k, 8))[:law_k]
    reranked_laws = rerank_candidates(reranker, query, laws, law_k)
    cases = case_provider.search(query, top_k=case_k) if case_provider and case_k else []
    case_items = []
    for position, result in enumerate(cases, 1):
        case_items.append({
            "citation_id": f"CASE-{position}", "type": "case", "case_id": result.case_id,
            "title": result.title, "court": getattr(result, "court", "") or "",
            "date": getattr(result, "judgment_date", "") or "",
            "facts": getattr(result, "basic_facts", "") or "",
            "legal_issue": getattr(result, "dispute_focus", "") or "",
            "judgment": getattr(result, "judgment_result", "") or "",
            "source": getattr(result, "source_file", "") or "",
            "dispute_focus": getattr(result, "dispute_focus", "") or "",
            "basic_facts": getattr(result, "basic_facts", "") or "",
            "judgment_result": getattr(result, "judgment_result", "") or "",
            "legal_basis": list(getattr(result, "legal_basis", []) or []),
        })
    context = build_context(law_items=reranked_laws, case_items=case_items,
                            max_articles=law_k, max_cases=case_k)
    return context


def run_generation(provider, query: str, context: dict, variant: str) -> dict:
    if variant == "E":
        variant_instruction = "不输出 related_cases 字段；只输出 answer、legal_basis、risk_note、confidence。"
    elif variant == "F":
        variant_instruction = "只输出最小 JSON：answer、legal_basis、confidence；不要输出其他字段。"
    else:
        variant_instruction = "输出完整结构化 JSON：answer、legal_basis、related_cases、risk_note、confidence。"
    base_user = (f"用户问题：{query}\n\n本次唯一可用 context：\n{context['context_text']}\n\n"
                 f"{variant_instruction}\n只能使用上述 context 中明确存在的 LAW-* / CASE-* citation。"
                 "不得自行生成 citation 或提及 context 外的法条号。")
    feedback = ""
    attempts = []
    for attempt_number in range(1, 4):
        prompt = base_user + feedback
        started = time.perf_counter()
        row = {"attempt": attempt_number, "prompt_chars": len(SYSTEM_PROMPT) + len(prompt),
               "prompt_tokens_est": estimate_tokens(SYSTEM_PROMPT + prompt),
               "provider_returned": False, "http_success": False, "provider_latency_ms": None,
               "json_parse_success": False, "schema_validation_success": False,
               "citation_validation_success": False, "citation_errors": [],
               "retry_trigger_reason": None}
        try:
            outcome = provider.complete_with_metadata(
                [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
                {"type": "json_object"}, 0,
            )
            row["provider_returned"] = bool(outcome.get("content"))
            row["http_success"] = bool(outcome.get("http_api_success"))
            row["provider_latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            raw = outcome.get("content")
            if not raw:
                raise ValueError("empty_response")
            parsed = json.loads(strip_json_fence(str(raw)))
            row["json_parse_success"] = True
            response = validate_response(normalize_citation_format(parsed))
            row["schema_validation_success"] = True
            validation = validate_citations(response, context)
            row["citation_validation_success"] = validation["valid"]
            row["citation_errors"] = validation["errors"][:8]
            if validation["valid"] and response.get("legal_analysis"):
                return {"success": True, "attempts": attempts + [row], "final_reason": None}
            if not validation["valid"]:
                row["retry_trigger_reason"] = "citation_validation_failed"
                feedback = "\n上一版 citation 或条号不受当前 context 支持。请删除错误 claim，只引用 context 中明确存在的 LAW-* / CASE-* ID，不得输出 context 外条号。错误：" + "; ".join(validation["errors"][:5])
            else:
                row["retry_trigger_reason"] = "schema_or_required_claim_failed"
                feedback = "\n上一版缺少可验证的法律分析。请严格输出 JSON，并至少提供一条带真实 context citation 的法律分析。"
        except json.JSONDecodeError:
            row["retry_trigger_reason"] = "invalid_json"
            feedback = "\n上一版不是合法 JSON。只输出 JSON 对象，不要 markdown 或额外说明。"
        except RAGSchemaError as exc:
            row["retry_trigger_reason"] = "schema_validation_failed"
            row["citation_errors"] = [str(exc)[:240]]
            feedback = "\n上一版 schema 不符合要求，请按字段要求重试。"
        except Exception as exc:
            row["retry_trigger_reason"] = f"provider_exception:{type(exc).__name__}"
            row["citation_errors"] = [str(exc)[:240]]
            feedback = "\n生成服务暂时不可用，请重试。"
        finally:
            if row["provider_latency_ms"] is None:
                row["provider_latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        attempts.append(row)
    return {"success": False, "attempts": attempts,
            "final_reason": attempts[-1].get("retry_trigger_reason") if attempts else "no_attempt"}


def main() -> None:
    load_dotenv()
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))[:5]
    provider = OpenAICompatibleProvider()
    retriever = HybridRetriever()
    reranker = load_reranker(local_files_only=True)
    case_provider = LocalHybridCaseProvider(corpus_path=ROOT / "data/processed/full_cases")
    configs = {
        "A": (3, 0, "完整结构"), "B": (8, 0, "完整结构"),
        "C": (3, 2, "完整结构"), "D": (8, 5, "完整结构"),
        "E": (8, 5, "去掉related_cases"), "F": (8, 5, "最小结构"),
    }
    records = []
    for label, (law_k, case_k, variant) in configs.items():
        for item in queries:
            context = build_retrieval(retriever, reranker, item["query"], law_k, case_k, case_provider)
            result = run_generation(provider, item["query"], context, label if label in {"E", "F"} else "standard")
            records.append({"config": label, "config_description": variant, "query": item["query"],
                            "context_item_count": len(context["items"]),
                            "context_chars": len(context["context_text"]),
                            "estimated_context_tokens": estimate_tokens(context["context_text"]),
                            "allowed_law_citations": len(context.get("law_items", [])),
                            "allowed_case_citations": len(context.get("case_items", [])),
                            **result})
    summary = {}
    for label in configs:
        rows = [record for record in records if record["config"] == label]
        attempts = [attempt for record in rows for attempt in record["attempts"]]
        successes = sum(record["success"] for record in rows)
        summary[label] = {"query_count": len(rows), "success_count": successes,
                          "success_rate": successes / len(rows) if rows else None,
                          "average_context_chars": round(sum(r["context_chars"] for r in rows) / len(rows), 2),
                          "average_prompt_chars_initial": round(sum(r["attempts"][0]["prompt_chars"] for r in rows) / len(rows), 2),
                          "average_retry_count": round(sum(max(0, len(r["attempts"]) - 1) for r in rows) / len(rows), 2),
                          "attempt_failure_reasons": {reason: sum(a["retry_trigger_reason"] == reason or str(a["retry_trigger_reason"]).startswith(reason + ":") for a in attempts) for reason in ("provider_exception", "invalid_json", "schema_validation_failed", "citation_validation_failed", "schema_or_required_claim_failed")},
                          "citation_valid_attempt_rate": round(sum(a["citation_validation_success"] for a in attempts) / len(attempts), 4) if attempts else None,
                          "average_provider_latency_ms": round(sum(a["provider_latency_ms"] for a in attempts) / len(attempts), 2) if attempts else None}
    lines = ["# V1.5.5 RAG Context Stress Analysis", "", "## 配置", "",
             "A=Top3法规；B=Top8法规；C=Top3法规+Top2案例；D=当前默认Top8法规+Top5案例；E/F为诊断对照。token为字符数/2粗略估算。", "",
             "## 汇总", "", "| 配置 | 成功率 | 平均context字符 | 初始prompt字符 | 平均retry | citation通过率 | 平均provider延迟ms |", "|---|---:|---:|---:|---:|---:|---:|"]
    for label in configs:
        s = summary[label]
        lines.append(f"| {label}（{configs[label][2]}） | {s['success_rate']:.4f} | {s['average_context_chars']} | {s['average_prompt_chars_initial']} | {s['average_retry_count']} | {s['citation_valid_attempt_rate']} | {s['average_provider_latency_ms']} |" if s["success_rate"] is not None else f"| {label} | — | — | — | — | — | — |")
    lines += ["", "## 每条 query 与每次 attempt", ""]
    for record in records:
        lines += [f"### {record['config']}｜{record['query']}", "",
                  f"- context items={record['context_item_count']}；context chars={record['context_chars']}；estimated tokens={record['estimated_context_tokens']}；allowed LAW={record['allowed_law_citations']}；allowed CASE={record['allowed_case_citations']}",
                  f"- final success={record['success']}；final reason={record['final_reason'] or '—'}；attempts={len(record['attempts'])}", "",
                  "| attempt | prompt chars | provider | HTTP | latency ms | JSON | schema | citation | retry trigger | errors |", "|---:|---:|---|---|---:|---|---|---|---|---|"]
        for attempt in record["attempts"]:
            errors = "；".join(attempt["citation_errors"]).replace("|", "／") or "—"
            lines.append(f"| {attempt['attempt']} | {attempt['prompt_chars']} | {attempt['provider_returned']} | {attempt['http_success']} | {attempt['provider_latency_ms']} | {attempt['json_parse_success']} | {attempt['schema_validation_success']} | {attempt['citation_validation_success']} | {attempt['retry_trigger_reason'] or '—'} | {errors} |")
        lines.append("")
    lines += ["## 初步分析", "", "- provider/transport失败应与context长度无关；若在此测试中仍出现，应单独归类为provider层问题。",
              "- citation validation failure若随案例数量或prompt长度上升，说明额外namespace/长案例文本增加了模型约束负担，但不能放宽validator。",
              "- retry prompt长度变化可由每条attempt的prompt chars直接比较；若持续增长，说明错误反馈本身造成上下文膨胀。",
              "- 单个超长案例和重复字段应通过context chars及逐条context item检查定位，后续再考虑裁剪字段。",
              "- E/F仅用于诊断，不构成产品schema建议。"]
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"config_summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
