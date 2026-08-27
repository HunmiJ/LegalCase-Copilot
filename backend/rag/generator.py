"""Grounded generation with structured, evidence-aware safety fallbacks."""

from __future__ import annotations

import json
import re
import time

from .citation_validator import validate_citations
from .schemas import RAGSchemaError, validate_response


SYSTEM_PROMPT = """你是劳动争议法律检索辅助系统。只能依据本次 context 回答。
法律法规是首要法律依据，证明力和优先级高于案例；案例只能作为相似事实和裁判思路的类案参考，绝不能替代法律条文，也不能据案例推导普遍规则。
法律分析优先引用 LAW-*；CASE-* 仅作类案参考，不能替代法条。只能依据 context，不得编造 citation、法条、条号、司法解释、案例事实或裁判结论。不得提及 context 未列出的“第X条”。
每个法律判断都必须引用 context 中明确列出的、真实存在的 citation id；法规只能使用当前 context 中列出的 LAW-*，案例只能使用当前 context 中列出的 CASE-*，两者不能混淆。不要把条号、排序号或自行推测的数字转换成 citation id。
证据不足、引用不存在或问题不属于劳动法律领域时，必须明确说明无法基于当前法律数据库提供可靠回答，不得猜测。
不确定时说明事实、证据和数据库覆盖范围的限制，不预测法院一定如何判决。
只输出 JSON，字段必须是 answer、legal_analysis、law_citations、case_citations、risk_note、confidence。
canonical schema：answer、legal_analysis、risk_note 为非空字符串；law_citations、case_citations 为 citation ID 字符串数组；confidence 为 0 到 1 的数字。legal_analysis 只写一段分析文字，不要嵌套 claim、citation 或 source 对象。citation 只通过两个数组选择。
law_citations 和 case_citations 只能列出本次 context 中真实存在的对应 ID。不要输出法规名称、条号、案例标题、法院或日期，这些由系统根据 citation metadata 填充。answer、legal_analysis、risk_note 不要写具体“第X条”。
"""

LABOR_TERMS = ("劳动", "工资", "加班", "辞退", "解雇", "劳动合同", "社保", "工伤", "仲裁", "竞业", "试用期", "欠薪")
OUT_OF_DOMAIN_TERMS = ("租房", "租赁", "押金", "房东", "房屋", "天气", "股票", "菜谱", "代码", "数学题", "旅游")
EVIDENCE_INSUFFICIENT_MESSAGE = "无法基于当前法律数据库提供可靠回答。"


def _is_out_of_domain(query: str) -> bool:
    return any(term in query for term in OUT_OF_DOMAIN_TERMS) and not any(term in query for term in LABOR_TERMS)


def _empty_enhanced_fields(answer: str, risk_note: str, confidence: str = "low") -> dict:
    return {"answer": answer, "legal_basis": [], "related_cases": [],
            "risk_note": risk_note, "confidence": confidence}


def _safe_validation() -> dict:
    return {"valid": True, "errors": [], "citation_validity": 1.0,
            "citation_precision": 1.0, "grounded_claim_rate": 1.0,
            "unsupported_citation_rate": 0.0}


def _safe_error_message(error: Exception) -> str:
    """Keep provider diagnostics useful without exposing credentials."""
    message = str(error)
    message = re.sub(r"Bearer\s+[^\s]+", "Bearer <redacted>", message, flags=re.IGNORECASE)
    message = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-<redacted>", message)
    return message[:500]


def _allowed_context_guide(context: dict) -> str:
    """Build a compact, deterministic citation/article allowlist from context."""
    citations = [str(item.get("citation_id")) for item in context.get("items", [])
                 if item.get("citation_id")]
    articles = []
    for item in context.get("items", []):
        if item.get("type", "law") != "law":
            continue
        law_name = str(item.get("law_name") or "").strip()
        article_number = str(item.get("article_number") or "").strip()
        if law_name and article_number:
            articles.append(f"{law_name}{article_number}")
    return ("允许的 citation IDs：" + ("、".join(citations) or "无") +
            "\n允许直接提及的具体条号：" + ("、".join(dict.fromkeys(articles)) or "无") +
            "\n不在允许列表的条号必须省略；无法确认时只引用 LAW-* citation。")


def _validate_generation_contract(response: dict, context: dict) -> None:
    """Validate the model-owned citation lists without weakening citation checks."""
    required = ("answer", "legal_analysis", "law_citations", "case_citations", "risk_note", "confidence")
    missing = [field for field in required if field not in response]
    if missing:
        raise RAGSchemaError("missing generation contract fields: " + ", ".join(missing))
    if not isinstance(response.get("answer"), str) or not response["answer"].strip():
        raise RAGSchemaError("answer must be a non-empty string")
    analysis_text = response.get("_generation_legal_analysis_text")
    if not isinstance(analysis_text, str) or not analysis_text.strip():
        raise RAGSchemaError("legal_analysis must normalize to a non-empty string")
    if not isinstance(response.get("risk_note"), str) or not response["risk_note"].strip():
        raise RAGSchemaError("risk_note must be a non-empty string")
    if not isinstance(response.get("confidence"), (int, float)) or isinstance(response.get("confidence"), bool) or not 0 <= response["confidence"] <= 1:
        raise RAGSchemaError("confidence must be a number between 0 and 1")
    by_id = {item["citation_id"]: item for item in context.get("items", [])}
    for field, prefix, item_type in (("law_citations", "LAW-", "law"), ("case_citations", "CASE-", "case")):
        values = response.get(field, [])
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise RAGSchemaError(f"{field} must be a list of strings")
        for value in values:
            normalized = _normalize_citation_token(value)
            if not isinstance(normalized, str) or not normalized.startswith(prefix):
                raise RAGSchemaError(f"{field} contains wrong citation namespace")
            if normalized not in by_id or by_id[normalized].get("type", "law") != item_type:
                raise RAGSchemaError(f"unsupported citation: {normalized}")
        response[field] = list(dict.fromkeys(_normalize_citation_token(value) for value in values))
    declared = set(response.get("law_citations", [])) | set(response.get("case_citations", []))
    if declared:
        response["legal_analysis"] = [{"claim": response["_generation_legal_analysis_text"],
                                        "citations": sorted(declared)}]
    else:
        raise RAGSchemaError("legal_analysis requires at least one selected citation")


def _sanitize_article_mentions(response: dict, context: dict) -> list[dict]:
    """Replace unsupported article numbers while preserving strict citation checks."""
    by_id = {item["citation_id"]: item for item in context.get("items", [])}
    cited_laws = {citation for citation in _cited_ids(response) if citation in by_id and by_id[citation].get("type", "law") == "law"}
    allowed = {str(by_id[citation].get("article_number") or "") for citation in cited_laws}
    events = []
    pattern = re.compile(r"第[^，。；、\s]{1,12}条")

    def clean(value: str, location: str) -> str:
        # A range or a nested paragraph reference cannot be safely reduced
        # without changing its scope. Reject it instead of guessing.
        if re.search(r"第[^，。；、\s]{1,12}条(?:至|到|-|—)第[^，。；、\s]{1,12}条", value):
            raise RAGSchemaError("unsafe unsupported article mention")
        if re.search(r"第[^，。；、\s]{1,12}条第[^，。；、\s]{1,12}(款|项)", value):
            raise RAGSchemaError("unsafe unsupported article mention")
        def replace(match):
            article = match.group(0)
            if article in allowed:
                return article
            events.append({"location": location, "original": article, "replacement": "相关法律规定"})
            return "相关法律规定"
        return pattern.sub(replace, value)

    for field in ("answer", "risk_note", "disclaimer"):
        if isinstance(response.get(field), str):
            response[field] = clean(response[field], field)
    if isinstance(response.get("issue_summary"), list):
        response["issue_summary"] = [clean(value, "issue_summary") for value in response["issue_summary"]]
    for index, claim in enumerate(response.get("legal_analysis", [])):
        if isinstance(claim, dict) and isinstance(claim.get("claim"), str):
            claim["claim"] = clean(claim["claim"], f"legal_analysis[{index}].claim")
    if "_generation_legal_analysis_text" in response and response.get("legal_analysis"):
        response["_generation_legal_analysis_text"] = response["legal_analysis"][0].get("claim", "")
        response["_public_legal_analysis"] = response["_generation_legal_analysis_text"]
    return events


def evidence_insufficient_response(context: dict, reason: str) -> dict:
    """Return a safe refusal without presenting retrieved text as legal advice."""
    response = _empty_enhanced_fields(
        EVIDENCE_INSUFFICIENT_MESSAGE,
        "当前证据不足或问题超出劳动法律数据库覆盖范围；请补充事实并咨询专业人士。",
    )
    response.update({
        "issue_summary": [EVIDENCE_INSUFFICIENT_MESSAGE], "legal_analysis": [],
        "relevant_laws": [], "missing_information": ["需要与问题直接对应且可核验的法律依据、事实和证据。"],
        "next_steps": ["补充事实、证据和程序信息后重新检索。"],
        "disclaimer": response["risk_note"], "generation_status": "evidence_insufficient",
        "failure_reason": reason,
    })
    return response


def retrieval_only_response(context: dict, reason: str) -> dict:
    laws = [{"citation": item["citation_id"], "law_name": item["law_name"],
             "article_number": item["article_number"], "text": item["article_content"]}
            for item in context.get("items", [])
            if item.get("type", "law") == "law" and item.get("article_content")]
    response = {
        "issue_summary": ["生成模型未能在有限重试内完成可靠的结构化回答。"],
        "legal_analysis": [], "relevant_laws": laws,
        "missing_information": ["需要结合完整事实、证据和程序状态进一步判断。"],
        "next_steps": ["请先核对上列法律条文，并咨询专业法律人士。"],
        "disclaimer": "当前仅展示检索到的法律条文，不构成确定性法律意见。",
        "generation_status": "retrieval_only", "failure_reason": reason,
    }
    response.update(_empty_enhanced_fields(
        "生成模型未能在有限重试内完成可靠的结构化回答。",
        "仅保留法规检索结果，未生成可验证的完整回答。",
    ))
    response["legal_basis"] = [{"citation": item["citation"], "content": item["text"]} for item in laws]
    return response


class GroundedGenerator:
    def __init__(self, provider, max_retries: int = 2):
        self.provider = provider
        self.max_retries = max(0, max_retries)

    def generate(self, query: str, context: dict) -> tuple[dict, dict]:
        if _is_out_of_domain(query):
            response = evidence_insufficient_response(context, "out_of_domain")
            return response, {"retry_count": 0, "fallback": False, "attempts": [], "validation": _safe_validation()}
        if not context.get("items") or not context.get("context_text", "").strip():
            response = evidence_insufficient_response(context, "empty_context")
            return response, {"retry_count": 0, "fallback": True, "attempts": [], "validation": _safe_validation()}

        user_prompt = (f"用户问题：{query}\n\n本次唯一可用 context：\n{context['context_text']}\n\n"
                       f"{_allowed_context_guide(context)}\n请严格按要求输出 JSON。")
        feedback = ""
        attempts = []
        generation_start = time.perf_counter()
        validation_total_ms = 0.0
        for attempt in range(self.max_retries + 1):
            diagnostic = {
                "attempt_number": attempt + 1, "provider_request_success": False,
                "http_api_success": False, "exception_type": None,
                "response_empty": None, "response_truncated": None,
                "raw_response_structure_type": None, "json_parse_success": False,
                "schema_validation_success": False, "citation_validation_success": False,
                "citation_errors": [],
            }
            try:
                messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt + feedback}]
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
                diagnostic["raw_response_preview"] = str(raw)[:2000] if raw else ""
                if not raw:
                    raise ValueError("empty_response")
                raw_text = str(raw).strip()
                if raw_text.startswith("```") and raw_text.endswith("```"):
                    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
                    raw_text = re.sub(r"\s*```$", "", raw_text)
                parsed = json.loads(raw_text)
                diagnostic["json_parse_success"] = True
                diagnostic["response_json_keys"] = sorted(parsed.keys()) if isinstance(parsed, dict) else []
                diagnostic["legal_analysis_shape"] = _legal_analysis_shape(parsed.get("legal_analysis")) if isinstance(parsed, dict) and "legal_analysis" in parsed else "missing"
                validation_start = time.perf_counter()
                response = normalize_citation_format(parsed)
                diagnostic["normalization_count"] = response.pop("_normalization_count", 0)
                if "law_citations" in response or "case_citations" in response:
                    _validate_generation_contract(response, context)
                sanitation_events = _sanitize_article_mentions(response, context)
                diagnostic["sanitation_count"] = len(sanitation_events)
                response = validate_response(response)
                diagnostic["schema_validation_success"] = True
                validation = validate_citations(response, context)
                validation_total_ms += (time.perf_counter() - validation_start) * 1000
                diagnostic["citation_validation_success"] = validation["valid"]
                diagnostic["citation_errors"] = validation["errors"][:10]
                attempts.append(diagnostic)
                if validation["valid"] and response.get("legal_analysis"):
                    response["relevant_laws"] = materialize_relevant_laws(response, context)
                    response["legal_basis"] = materialize_legal_basis(response, context)
                    response["related_cases"] = materialize_related_cases(response, context)
                    if response.pop("_canonical_generation", False):
                        response.pop("_generation_legal_analysis_text", None)
                        # Keep the public canonical contract simple. The old
                        # claim list was only an in-memory validator adapter.
                        response["legal_analysis"] = response.get("_public_legal_analysis", "")
                        response.pop("_public_legal_analysis", None)
                    response["generation_status"] = "success"
                    return response, {"retry_count": attempt, "fallback": False, "validation": validation,
                                      "sanitation_events": sanitation_events,
                                      "normalization_count": diagnostic.get("normalization_count", 0),
                                      "attempts": attempts, "validation_latency_ms": validation_total_ms,
                                      "generation_latency_ms": (time.perf_counter() - generation_start) * 1000}
                feedback = "\n修正后重试：只使用当前 context 的 LAW-* / CASE-* ID；删除无依据 claim；不得输出 context 外条号。错误类型：" + _compact_retry_reason(validation["errors"])
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
            except Exception as exc:
                diagnostic["exception_type"] = "ProviderError"
                diagnostic["provider_error_type"] = type(exc).__name__
                diagnostic["error_detail"] = _safe_error_message(exc)
                attempts.append(diagnostic)
                feedback = "\n生成服务暂时不可用，请返回基于检索证据的保守结果。"

        citation_failure = any("citation" in error or "article mention" in error for attempt in attempts for error in attempt.get("citation_errors", []))
        fallback = evidence_insufficient_response(context, "unsupported_citation") if citation_failure else retrieval_only_response(context, "generation_failed_after_retries")
        return fallback, {"retry_count": self.max_retries, "fallback": True, "attempts": attempts,
                          "validation_latency_ms": validation_total_ms,
                          "generation_latency_ms": (time.perf_counter() - generation_start) * 1000,
                          "validation": validate_citations(fallback, context)}


def _cited_ids(response: dict) -> list[str]:
    if isinstance(response.get("legal_analysis"), str):
        return list(dict.fromkeys(response.get("law_citations", []) + response.get("case_citations", [])))
    return [citation for claim in response.get("legal_analysis", []) for citation in claim.get("citations", [])]


def materialize_relevant_laws(response: dict, context: dict) -> list[dict]:
    by_id = {item["citation_id"]: item for item in context.get("items", [])}
    return [{"citation": citation, "law_name": by_id[citation]["law_name"], "article_number": by_id[citation]["article_number"], "text": by_id[citation]["article_content"]}
            for citation in dict.fromkeys(_cited_ids(response)) if citation in by_id and by_id[citation].get("type", "law") == "law"]


def materialize_legal_basis(response: dict, context: dict) -> list[dict]:
    by_id = {item["citation_id"]: item for item in context.get("items", [])}
    return [{"citation": citation,
             "law_name": by_id[citation].get("law_name", ""),
             "article_number": by_id[citation].get("article_number", ""),
             "content": by_id[citation].get("article_content", ""),
             "source": by_id[citation].get("source_file", "")}
            for citation in dict.fromkeys(_cited_ids(response)) if citation in by_id and by_id[citation].get("type", "law") == "law"]


def materialize_related_cases(response: dict, context: dict) -> list[dict]:
    by_id = {item["citation_id"]: item for item in context.get("items", [])}
    return [{"citation": citation,
             "case_id": by_id[citation].get("case_id", ""),
             "title": by_id[citation].get("title", ""),
             "court": by_id[citation].get("court", ""),
             "judgment_date": by_id[citation].get("date") or by_id[citation].get("judgment_date", ""),
             "dispute_focus": by_id[citation].get("dispute_focus") or by_id[citation].get("legal_issue", ""),
             "reasoning": by_id[citation].get("judgment_result") or by_id[citation].get("judgment") or ""}
            for citation in dict.fromkeys(_cited_ids(response)) if citation in by_id and by_id[citation].get("type") == "case"]


def normalize_citation_format(response: dict) -> dict:
    """Normalize old numeric and new namespaced citation formats."""
    canonical = any(field in response for field in ("law_citations", "case_citations"))
    if "answer" in response:
        if canonical:
            response["_canonical_generation"] = True
            analysis = response.get("legal_analysis")
            normalized_analysis, count = _normalize_analysis_text(analysis)
            if normalized_analysis is not None:
                response["_generation_legal_analysis_text"] = normalized_analysis
                response["_public_legal_analysis"] = normalized_analysis
                response["legal_analysis"] = []
                response["_normalization_count"] = count
            # The remaining fields are internal adapter fields required by
            # the unchanged strict citation validator.
        response.setdefault("legal_basis", [])
        response.setdefault("related_cases", [])
        response.setdefault("risk_note", "")
        response.setdefault("confidence", "medium")
        response.setdefault("issue_summary", [response.get("answer") or ""])
        response.setdefault("missing_information", [])
        response.setdefault("next_steps", [])
        response.setdefault("disclaimer", response.get("risk_note") or "请结合完整事实和证据核验。")
        response.setdefault("relevant_laws", [])
        response.setdefault("legal_analysis", [])
        # The final contract owns legal_analysis and citation lists. Legacy
        # presentation fields remain accepted for existing callers/tests.
        if not response["legal_analysis"] and not canonical:
            for item in response.get("legal_basis", []):
                if isinstance(item, dict) and item.get("citation"):
                    response["legal_analysis"].append({"claim": item.get("content") or "检索到的法规依据。", "citations": [item["citation"]]})
            for item in response.get("related_cases", []):
                if isinstance(item, dict) and item.get("citation"):
                    response["legal_analysis"].append({"claim": item.get("reasoning") or "该案例仅供类案参考。", "citations": [item["citation"]]})
    else:
        response.setdefault("answer", " ".join(response.get("issue_summary", [])))
        response.setdefault("legal_basis", [])
        response.setdefault("related_cases", [])
        response.setdefault("risk_note", response.get("disclaimer", ""))
        response.setdefault("confidence", "medium")
    for claim in response.get("legal_analysis", []):
        if not isinstance(claim, dict):
            # Leave malformed items for the explicit contract/schema error;
            # do not turn a model-shape error into an internal AttributeError.
            continue
        citations = claim.get("citations")
        if isinstance(citations, list):
            normalized = []
            for citation in citations:
                normalized.append(_normalize_citation_token(citation))
            claim["citations"] = normalized
    for field in ("legal_basis", "related_cases"):
        for item in response.get(field, []):
            if isinstance(item, dict) and isinstance(item.get("citation"), str):
                citation = item["citation"].strip()
                if re.fullmatch(r"\[(?:LAW|CASE)-\d+\]", citation):
                    item["citation"] = citation[1:-1]
    return response


def _normalize_analysis_text(value) -> tuple[str | None, int]:
    """Normalize only unambiguous semantic shape variants to one string."""
    if isinstance(value, str) and value.strip():
        return value.strip(), 0
    if isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value):
        return "\n".join(item.strip() for item in value), 1
    if isinstance(value, dict) and set(value) == {"analysis"} and isinstance(value.get("analysis"), str) and value["analysis"].strip():
        return value["analysis"].strip(), 1
    return None, 0


def _legal_analysis_shape(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        if not value:
            return "list[empty]"
        if all(isinstance(item, str) for item in value):
            return "list[string]"
        if all(isinstance(item, dict) for item in value):
            keys = sorted({key for item in value for key in item.keys()})
            return "list[object] keys=" + ",".join(keys[:12])
        return "list[mixed]"
    if isinstance(value, dict):
        return "object keys=" + ",".join(sorted(value.keys())[:12])
    return type(value).__name__


def _compact_retry_reason(errors: list[str]) -> str:
    """Return bounded retry feedback without echoing a growing error list."""
    if any("article mention outside context" in error for error in errors):
        return "unsupported citation: article outside supplied context"
    if any("unsupported citation" in error for error in errors):
        return "unsupported citation"
    if any("legal claim without citation" in error for error in errors):
        return "claim missing citation"
    return "citation validation failed"


def _normalize_citation_token(citation):
    """Normalize safe bracket differences without inventing an ID.

    Numeric citations remain in the legacy ``[1]`` form and are validated
    against legacy contexts. Namespaced citations are only unwrapped from
    brackets; existence is still checked by ``validate_citations``.
    """
    if isinstance(citation, int) and citation >= 0:
        return f"[{citation}]"
    if not isinstance(citation, str):
        return citation
    token = citation.strip()
    if re.fullmatch(r"\d+", token):
        return f"[{token}]"
    match = re.fullmatch(r"\[(LAW|CASE)-(\d+)\]", token)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return token


class MockRAGProvider:
    name = "mock"
    model = "deterministic-rag-mock-v0.9"

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
