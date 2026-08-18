"""Dependency-free structured response validation for legal RAG."""

from __future__ import annotations

from typing import Any


class RAGSchemaError(ValueError):
    pass


def _string_list(value: Any, field: str, maximum: int = 20) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value]
    if not isinstance(value, list) or len(value) > maximum:
        raise RAGSchemaError(f"{field} must be a list of at most {maximum} strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise RAGSchemaError(f"{field} contains an invalid item")
    return value


def validate_response(value: Any) -> dict:
    if not isinstance(value, dict):
        raise RAGSchemaError("response must be an object")
    required = ("issue_summary", "legal_analysis", "missing_information", "next_steps", "disclaimer")
    missing = [field for field in required if field not in value]
    if missing:
        raise RAGSchemaError("missing fields: " + ", ".join(missing))
    for field in ("issue_summary", "missing_information", "next_steps"):
        value[field] = _string_list(value[field], field)
    if not isinstance(value["disclaimer"], str) or not value["disclaimer"].strip():
        raise RAGSchemaError("disclaimer must be a non-empty string")
    if not isinstance(value["legal_analysis"], list) or len(value["legal_analysis"]) > 20:
        raise RAGSchemaError("legal_analysis must be a list")
    for item in value["legal_analysis"]:
        if not isinstance(item, dict) or not isinstance(item.get("claim"), str) or not item["claim"].strip():
            raise RAGSchemaError("each legal_analysis item needs a claim")
        if not isinstance(item.get("citations"), list) or not item["citations"]:
            raise RAGSchemaError("each legal claim needs at least one citation")
        if any(not isinstance(citation, str) for citation in item["citations"]):
            raise RAGSchemaError("citations must be strings")
    value.setdefault("relevant_laws", [])
    if not isinstance(value["relevant_laws"], list) or len(value["relevant_laws"]) > 10:
        raise RAGSchemaError("relevant_laws must be a list")
    for item in value["relevant_laws"]:
        required_law = ("citation", "law_name", "article_number", "text")
        if not isinstance(item, dict) or any(not isinstance(item.get(field), str) or not item[field].strip() for field in required_law):
            raise RAGSchemaError("each relevant_laws item needs citation, law_name, article_number and text")
    return value
