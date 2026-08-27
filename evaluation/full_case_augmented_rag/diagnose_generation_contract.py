"""First-pass generation contract breakdown with no automatic retry."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import OpenAICompatibleProvider
from backend.rag.citation_validator import validate_citations
from backend.rag.context_builder import build_context
from backend.rag.generator import SYSTEM_PROMPT, normalize_citation_format
from backend.rag.pipeline import LegalRAGPipeline
from backend.rag.schemas import RAGSchemaError, validate_response
from backend.cases.sources.hybrid_local import LocalHybridCaseProvider
from scripts.hybrid_utils import HybridRetriever
from scripts.reranker_utils import load_reranker, rerank_candidates

QUERY_FILE = ROOT / "evaluation/full_case_augmented_rag/generation_queries.json"
REPORT_FILE = ROOT / "docs/v1.5.8_generation_contract_stabilization.md"


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class CaptureProvider:
    name = "capture"
    model = "capture"

    def __init__(self):
        self.messages = None

    def complete_with_metadata(self, messages, response_format=None, temperature=0):
        self.messages = self.messages or messages
        return {"content": json.dumps({"issue_summary": ["capture"], "legal_analysis": [],
                                        "missing_information": [], "next_steps": [],
                                        "disclaimer": "capture"}),
                "finish_reason": "stop", "response_structure_type": "str",
                "http_api_success": True}


def production_prompt(query: str, include_cases: bool, retriever, reranker):
    capture = CaptureProvider()
    pipeline = LegalRAGPipeline(capture, retriever=retriever, reranker=reranker,
                                include_cases=include_cases,
                                case_corpus_path=ROOT / "data/processed/full_cases")
    result = pipeline.ask(query)
    if not capture.messages:
        raise RuntimeError("production prompt was not captured")
    context = result["context"]
    return capture.messages, context


def _response_text(response: dict) -> str:
    values = [response.get("answer", ""), response.get("risk_note", ""), response.get("disclaimer", ""),
              *response.get("issue_summary", []),
              *[item.get("claim", "") for item in response.get("legal_analysis", [])],
              *[item.get("content", "") for item in response.get("legal_basis", [])],
              *[item.get("reasoning", "") for item in response.get("related_cases", [])]]
    return " ".join(str(value or "") for value in values)


def _ids(response: dict, prefix: str) -> list[str]:
    values = []
    for claim in response.get("legal_analysis", []):
        values.extend(claim.get("citations", []))
    for field in ("legal_basis", "related_cases"):
        values.extend(item.get("citation") for item in response.get(field, []) if item.get("citation"))
    return sorted({str(value) for value in values if str(value).startswith(prefix)})


def _schema_failures(response: dict) -> list[str]:
    missing = [field for field in ("issue_summary", "legal_analysis", "missing_information", "next_steps", "disclaimer") if field not in response]
    empty = [field for field in ("issue_summary", "legal_analysis", "missing_information", "next_steps", "disclaimer") if field in response and (response[field] == "" or response[field] == [])]
    return [f"missing:{field}" for field in missing] + [f"empty:{field}" for field in empty]


def one_call(provider, messages, context, query_id, mode, repeat):
    started = time.perf_counter()
    record = {"query_id": query_id, "mode": mode, "repeat": repeat,
              "allowed_law_ids": [item["citation_id"] for item in context.get("law_items", [])],
              "allowed_case_ids": [item["citation_id"] for item in context.get("case_items", [])],
              "json_parse": False, "schema": False, "schema_failures": [],
              "citation": False, "citation_subtype": [], "returned_law_ids": [],
              "returned_case_ids": [], "article_mentions": [], "articles_in_context": [],
              "required_field_missing": False, "empty_fields": [],
              "final_validation": False, "exception_class": None,
              "provider_success": False, "http_status": None, "latency_ms": None}
    try:
        result = provider.complete_with_metadata(messages, {"type": "json_object"}, 0)
        raw = result.get("content")
        record["provider_success"] = bool(result.get("http_api_success")) and bool(raw)
        record["http_status"] = 200 if result.get("http_api_success") else None
        if not raw:
            record["citation_subtype"] = ["empty_response"]
            return record
        try:
            parsed = json.loads(str(raw).strip().removeprefix("```json").removesuffix("```").strip())
            record["json_parse"] = True
        except json.JSONDecodeError:
            record["citation_subtype"] = ["json_failure"]
            return record
        normalized = normalize_citation_format(parsed)
        record["returned_law_ids"] = _ids(normalized, "LAW-")
        record["returned_case_ids"] = _ids(normalized, "CASE-")
        record["article_mentions"] = sorted(set(re.findall(r"第[^，。；、\s]{1,12}条", _response_text(normalized))))
        record["articles_in_context"] = sorted(set(str(item.get("article_number")) for item in context.get("law_items", [])))
        try:
            validate_response(normalized)
            record["schema"] = True
        except RAGSchemaError as exc:
            record["schema_failures"] = [str(exc)[:200]]
            record["required_field_missing"] = "missing fields" in str(exc)
            record["empty_fields"] = _schema_failures(normalized)
            return record
        validation = validate_citations(normalized, context)
        record["citation"] = validation["valid"]
        record["citation_subtype"] = sorted(set(
            "article_outside_context" if "article mention outside context" in error else
            "unsupported_id" if "unsupported citation" in error else "other_citation_error"
            for error in validation["errors"]))
        record["final_validation"] = validation["valid"] and bool(normalized.get("legal_analysis"))
    except urllib.error.HTTPError as exc:
        record["exception_class"] = f"HTTPError_{exc.code}"
    except Exception as exc:
        record["exception_class"] = type(exc).__name__
    finally:
        record["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return record


def main() -> None:
    load_dotenv()
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))[:5]
    provider = OpenAICompatibleProvider()
    retriever = HybridRetriever()
    reranker = load_reranker(local_files_only=True)
    case_provider = LocalHybridCaseProvider(corpus_path=ROOT / "data/processed/full_cases")
    records = []
    for query_id, item in enumerate(queries, 1):
        for mode, include_cases in (("law-only", False), ("law+6492-cases", True)):
            messages, context = production_prompt(item["query"], include_cases, retriever, reranker)
            prompt = "".join(str(message.get("content") or "") for message in messages)
            for repeat in range(1, 4):
                record = one_call(provider, messages, context, query_id, mode, repeat)
                record.update({"context_chars": len(context["context_text"]),
                               "prompt_chars": len(prompt),
                               "estimated_tokens": round(len(prompt) / 2)})
                records.append(record)
    def count(predicate):
        return sum(1 for record in records if predicate(record))
    categories = {
        "A_json_failure": count(lambda r: not r["json_parse"] and not r["exception_class"]),
        "B_schema_failure": count(lambda r: r["json_parse"] and not r["schema"]),
        "C_unsupported_law_case_id": count(lambda r: r["schema"] and "unsupported_id" in r["citation_subtype"]),
        "D_article_outside_context": count(lambda r: r["schema"] and "article_outside_context" in r["citation_subtype"]),
        "E_required_claim_or_field_failure": count(lambda r: r["schema"] and not r["final_validation"] and not r["citation_subtype"]),
        "F_other": count(lambda r: bool(r["exception_class"]) or "other_citation_error" in r["citation_subtype"]),
    }
    lines = ["# V1.5.8 Generation Contract Stabilization", "", "## Validation breakdown", "",
             f"第一轮使用5条固定 query、两种模式、每个组合3次，共{len(records)}次真实生成；不自动 retry。只保存安全诊断元数据。", "",
             "| 类别 | 次数 | 比例 |", "|---|---:|---:|"]
    for name, value in categories.items():
        lines.append(f"| {name} | {value} | {value / len(records):.4f} |")
    lines += ["", "## 逐次记录", "", "| query id | mode | repeat | context chars | prompt chars | JSON | schema | schema errors | citation | subtype | returned LAW | returned CASE | allowed LAW | allowed CASE | article mentions | context articles | final | latency ms |", "|---:|---|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|---|---|---:|"]
    for r in records:
        lines.append(f"| {r['query_id']} | {r['mode']} | {r['repeat']} | {r['context_chars']} | {r['prompt_chars']} | {r['json_parse']} | {r['schema']} | {'；'.join(r['schema_failures']) or '—'} | {r['citation']} | {','.join(r['citation_subtype']) or '—'} | {','.join(r['returned_law_ids']) or '—'} | {','.join(r['returned_case_ids']) or '—'} | {','.join(r['allowed_law_ids'])} | {','.join(r['allowed_case_ids']) or '—'} | {','.join(r['article_mentions']) or '—'} | {','.join(r['articles_in_context']) or '—'} | {r['final_validation']} | {r['latency_ms']} |")
    lines += ["", "## 结论", "", "本轮不自动修改或放宽 validator。若失败主要集中在 context 外具体条号，应在下一阶段向 prompt 注入由 LAW context 确定性生成的 article allowlist；模型无法确认时只引用 LAW-*，不输出条号。法规名称、条号、案例标题、法院和日期应继续由真实 citation 对应的 retrieval metadata 渲染，不能由模型自由抄写后作为事实来源。", "", "本报告未运行完整30条正式评测。"]
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"calls": len(records), "categories": categories}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
