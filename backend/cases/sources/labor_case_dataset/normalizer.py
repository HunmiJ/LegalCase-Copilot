"""Normalize labor_case_dataset records into the existing CaseRecord schema."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ...schemas import CaseRecord


def _original(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("original_data")
    return value if isinstance(value, dict) else record


def _qwen(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("qwen_res")
    return value if isinstance(value, dict) else {}


def _first(mapping: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = mapping.get(name)
        if value is not None and value != "":
            return value
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        elif isinstance(item, dict):
            text = " ".join(str(v).strip() for v in item.values() if str(v).strip())
            if text:
                result.append(text)
    return result


def _legal_basis(value: Any) -> list[str]:
    if not isinstance(value, list):
        return _list_of_strings(value)
    result: list[str] = []
    for item in value:
        if isinstance(item, dict):
            code = str(item.get("code") or item.get("name") or "").strip()
            section = str(item.get("section") or item.get("article") or "").strip()
            value_text = " ".join(part for part in (code, section) if part)
            if value_text:
                result.append(value_text)
        elif isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result


def _stable_id(title: str, raw_text: str) -> str:
    return "public-" + hashlib.sha256((title + "\x1f" + raw_text).encode("utf-8")).hexdigest()[:24]


def normalize(loaded: dict[str, Any], root: Path | None = None) -> CaseRecord:
    record = loaded["record"]
    original = _original(record)
    qwen = _qwen(record)
    raw_text = _text(_first(record, "raw_text", "content", "text"))
    title = _text(_first(original, "title", "case_title"))
    if not title:
        raise ValueError("labor_case_dataset record has no title")

    original_id = _text(_first(original, "identifier", "id", "case_id", "caseId"))
    case_number = _text(_first(original, "caseNumber", "case_number", "caseNo"))
    case_id = original_id or case_number or _stable_id(title, raw_text)
    source_file = str(loaded.get("source_file") or "")
    if root is not None and source_file:
        try:
            source_file = str(Path(source_file).resolve().relative_to(root.resolve())).replace("\\", "/")
        except ValueError:
            pass

    facts = _first(qwen, "basic_facts", "basicFacts", "facts")
    if facts is None:
        facts = _first(record, "basic_facts", "basicFacts", "facts")
    reasoning = _first(record, "court_reasoning", "courtReasoning", "reasoning")
    judgment = _first(record, "judgement", "judgment", "judgment_result", "judgmentResult")
    if judgment is None:
        judgment = _first(qwen, "judgement", "judgment", "judgment_result", "judgmentResult")
    return CaseRecord(
        case_id=case_id,
        title=title,
        case_number=case_number or None,
        case_type=_text(_first(original, "caseType", "case_type", "reason")) or "未分类",
        court=_text(_first(original, "court", "court_name")) or None,
        judgment_date=_text(_first(original, "judgementDate", "judgmentDate", "judgment_date")) or None,
        keywords=_list_of_strings(_first(original, "keywords", "keyword")),
        basic_facts=_text(facts) or None,
        dispute_focus=_text(_first(record, "dispute_focus", "disputeFocus")) or None,
        court_reasoning=_text(reasoning) or None,
        judgment_result=_text(judgment) or None,
        legal_basis=_legal_basis(_first(record, "lawArticles", "legal_basis", "legalBasis")),
        source_name="labor_case_dataset",
        source_url=_text(_first(original, "source_url", "sourceUrl")) or None,
        source_file=source_file,
        raw_text=raw_text,
    )
