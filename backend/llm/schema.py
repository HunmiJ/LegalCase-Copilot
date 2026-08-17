"""Small dependency-free schema validation for query understanding output."""

from __future__ import annotations

import json
from typing import Any


REQUIRED_FIELDS = ("original_query", "domain", "issue", "user_intent", "legal_concepts", "search_queries")


class SchemaValidationError(ValueError):
    pass


def validate_understanding(value: Any, original_query: str | None = None) -> dict:
    if not isinstance(value, dict):
        raise SchemaValidationError("understanding must be an object")
    missing = [field for field in REQUIRED_FIELDS if field not in value]
    if missing:
        raise SchemaValidationError("missing fields: " + ", ".join(missing))
    for field in ("original_query", "domain", "issue", "user_intent"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise SchemaValidationError(f"{field} must be a non-empty string")
    if original_query is not None and value["original_query"] != original_query:
        raise SchemaValidationError("original_query does not match input")
    if value["domain"] not in ("劳动争议", "labor_dispute"):
        raise SchemaValidationError("domain must be labor dispute")
    if not isinstance(value["legal_concepts"], list) or not 0 <= len(value["legal_concepts"]) <= 8:
        raise SchemaValidationError("legal_concepts must contain 0 to 8 items")
    if any(not isinstance(item, str) or not item.strip() for item in value["legal_concepts"]):
        raise SchemaValidationError("legal_concepts items must be non-empty strings")
    if not isinstance(value["search_queries"], list) or not 1 <= len(value["search_queries"]) <= 3:
        raise SchemaValidationError("search_queries must contain 1 to 3 items")
    if any(not isinstance(item, str) or not item.strip() for item in value["search_queries"]):
        raise SchemaValidationError("search_queries items must be non-empty strings")
    normalized = dict(value)
    normalized["original_query"] = original_query or value["original_query"]
    normalized["search_queries"] = list(dict.fromkeys(value["search_queries"]))[:3]
    return normalized


def parse_and_validate(raw: str, original_query: str) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"invalid JSON: {exc.msg}") from exc
    return validate_understanding(value, original_query)
