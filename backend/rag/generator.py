"""Grounded generation with bounded retries and retrieval-only fallback."""

from __future__ import annotations

import json
import re
import time

from .citation_validator import validate_citations
from .schemas import RAGSchemaError, validate_response

SYSTEM_PROMPT = """你是劳动争议法律检索辅助系统。只能依据给定的法律条文回答。
不得凭记忆补充 context 外的法条、条号、司法解释或案例。每个法律判断必须带本次 context 中的 citation id，例如 [1]。
不确定时明确说明信息不足，不预测法院一定如何判决，不把初步分析表达为确定法律结论。
只输出 JSON，字段必须是 issue_summary、legal_analysis、missing_information、next_steps、disclaimer；relevant_laws 可以省略，由程序根据合法 citation id 从 context 回填。
legal_analysis 每项必须有 claim 和 citations；citations 只能使用 context 中出现的 citation id。
"""


def retrieval_only_response(context: dict, reason: str) -> dict:
    laws = [{"citation": item["citation_id"], "law_name": item["law_name"],
             "article_number": item["article_number"], "text": item["article_content"]}
            for item in context.get("items", [])]
    return {
        "issue_summary": ["生成模型未能在有限重试内完成可靠的结构化回答。"],
        "legal_analysis": [],
        "relevant_laws": laws,
        "missing_information": ["需要结合完整事实、证据和程序状态进一步判断。"],
        "next_steps": ["请先核对上列法律条文，并咨询专业法律人士。"],
        "disclaimer": "当前仅展示检索到的法律条文，不构成确定性法律意见。",
        "generation_status": "retrieval_only",
        "failure_reason": reason,
    }


class GroundedGenerator:
    def __init__(self, provider, max_retries: int = 2):
        self.provider = provider
        self.max_retries = max(0, max_retries)

    def generate(self, query: str, context: dict) -> tuple[dict, dict]:
        user_prompt = f"用户问题：{query}\n\n本次唯一可用 context：\n{context['context_text']}\n\n请严格按要求输出 JSON。"
        feedback = ""
        attempts = []
        generation_start = time.perf_counter()
        validation_total_ms = 0.0
        for attempt in range(self.max_retries + 1):
            diagnostic = {
                "attempt_number": attempt + 1,
                "provider_request_success": False,
                "http_api_success": False,
                "exception_type": None,
                "response_empty": None,
                "response_truncated": None,
                "raw_response_structure_type": None,
                "json_parse_success": False,
                "schema_validation_success": False,
                "citation_validation_success": False,
                "citation_errors": [],
            }
            try:
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt + feedback},
                ]
                if hasattr(self.provider, "complete_with_metadata"):
                    outcome = self.provider.complete_with_metadata(messages, {"type": "json_object"}, 0)
                    raw = outcome.get("content")
                    diagnostic["http_api_success"] = bool(outcome.get("http_api_success"))
                    diagnostic["response_truncated"] = outcome.get("finish_reason") in {"length", "max_tokens"}
                    diagnostic["raw_response_structure_type"] = outcome.get("response_structure_type")
                else:
                    raw = self.provider.complete(messages, {"type": "json_object"}, 0)
                    diagnostic["http_api_success"] = True
                    diagnostic["raw_response_structure_type"] = type(raw).__name__
                diagnostic["provider_request_success"] = True
                diagnostic["response_empty"] = not bool(raw)
                if not raw:
                    raise ValueError("empty_response")
                raw_text = str(raw).strip()
                if raw_text.startswith("```") and raw_text.endswith("```"):
                    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
                    raw_text = re.sub(r"\s*```$", "", raw_text)
                parsed = json.loads(raw_text)
                diagnostic["json_parse_success"] = True
                validation_start = time.perf_counter()
                response = validate_response(normalize_citation_format(parsed))
                diagnostic["schema_validation_success"] = True
                validation = validate_citations(response, context)
                validation_total_ms += (time.perf_counter() - validation_start) * 1000
                diagnostic["citation_validation_success"] = validation["valid"]
                diagnostic["citation_errors"] = validation["errors"][:10]
                attempts.append(diagnostic)
                if validation["valid"]:
                    response["relevant_laws"] = materialize_relevant_laws(response, context)
                    response["generation_status"] = "success"
                    return response, {"retry_count": attempt, "fallback": False, "validation": validation,
                                      "attempts": attempts, "validation_latency_ms": validation_total_ms,
                                      "generation_latency_ms": (time.perf_counter() - generation_start) * 1000}
                feedback = "\n上一版存在 citation 错误，请删除无法支持的 claim 并重新输出。错误：" + "; ".join(validation["errors"][:5])
            except json.JSONDecodeError:
                diagnostic["exception_type"] = "JSONDecodeError"
                diagnostic["error_detail"] = "invalid_json"
                attempts.append(diagnostic)
                feedback = "\n上一版不是有效结构化 JSON，请严格按 schema 重试。"
            except RAGSchemaError as exc:
                diagnostic["exception_type"] = "RAGSchemaError"
                diagnostic["error_detail"] = str(exc)[:200]
                attempts.append(diagnostic)
                feedback = "\n上一版 schema 不符合要求，请严格按字段输出 JSON。"
            except Exception:
                diagnostic["exception_type"] = "ProviderError"
                diagnostic["error_detail"] = "provider_error_without_response_details"
                attempts.append(diagnostic)
                # Network timeout, rate limit, or provider failure must not
                # crash the legal retrieval path or expose request details.
                feedback = "\n生成服务暂时不可用，请返回基于检索条文的保守结果。"
        return retrieval_only_response(context, "generation_failed_after_retries"), {
            "retry_count": self.max_retries, "fallback": True, "attempts": attempts,
            "validation_latency_ms": validation_total_ms,
            "generation_latency_ms": (time.perf_counter() - generation_start) * 1000,
            "validation": validate_citations(retrieval_only_response(context, "validation_failed"), context),
        }


def materialize_relevant_laws(response: dict, context: dict) -> list[dict]:
    """Build law metadata from validated citation ids, never from LLM text."""
    by_id = {item["citation_id"]: item for item in context.get("items", [])}
    citations = []
    for claim in response.get("legal_analysis", []):
        citations.extend(claim.get("citations", []))
    laws = []
    for citation in dict.fromkeys(citations):
        item = by_id.get(citation)
        if item:
            laws.append({"citation": citation, "law_name": item["law_name"],
                         "article_number": item["article_number"], "text": item["article_content"]})
    return laws


def normalize_citation_format(response: dict) -> dict:
    """Normalize only unambiguous numeric citation ids; never invent ids."""
    for claim in response.get("legal_analysis", []):
        citations = claim.get("citations")
        if isinstance(citations, list):
            normalized = []
            for citation in citations:
                if isinstance(citation, int) and citation >= 0:
                    normalized.append(f"[{citation}]")
                elif isinstance(citation, str) and re.fullmatch(r"\d+", citation.strip()):
                    normalized.append(f"[{citation.strip()}]")
                else:
                    normalized.append(citation)
            claim["citations"] = normalized
    return response


class MockRAGProvider:
    name = "mock"
    model = "deterministic-rag-mock-v0.6"

    def complete(self, messages, response_format=None, temperature=0):
        user = messages[-1]["content"]
        context = user.split("本次唯一可用 context：", 1)[-1]
        citations = re.findall(r"\[\d+\]", context)
        query = user.split("用户问题：", 1)[-1].split("\n", 1)[0]
        if "租房" in query or "押金" in query:
            return json.dumps({"issue_summary": ["当前劳动争议知识库不足以回答租赁纠纷。"], "legal_analysis": [], "relevant_laws": [], "missing_information": ["需要查询租赁法律资料。"], "next_steps": ["请使用与租赁纠纷匹配的法律资料。"], "disclaimer": "当前知识库不足，不构成法律意见。"}, ensure_ascii=False)
        if "999" in query or "合法吗" in query and len(query) < 12:
            return json.dumps({"issue_summary": ["现有信息不足以作出确定判断。"], "legal_analysis": [], "relevant_laws": [], "missing_information": ["需要补充解除原因、合同期限、通知和证据等事实。"], "next_steps": ["补充事实后再核对适用条文。"], "disclaimer": "这不是确定性法律结论。"}, ensure_ascii=False)
        citation = citations[0] if citations else "[1]"
        return json.dumps({"issue_summary": ["问题涉及劳动争议法律规则。"], "legal_analysis": [{"claim": "检索到的条文可作为进一步核对的法律依据。", "citations": [citation]}], "relevant_laws": [], "missing_information": ["仍需结合具体事实和证据。"], "next_steps": ["核对引用条文并准备相关证据。"], "disclaimer": "仅供法律信息检索参考，不构成确定性法律意见。"}, ensure_ascii=False)
