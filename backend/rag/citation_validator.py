"""Strict validation of citations against the actual retrieval context."""

from __future__ import annotations

import re

from .schemas import RAGSchemaError, validate_response

CITATION_RE = re.compile(r"\[\d+\]")
ARTICLE_RE = re.compile(r"第[^，。；、\s]{1,12}条")


def validate_citations(response: dict, context: dict) -> dict:
    errors = []
    try:
        validate_response(response)
    except RAGSchemaError as exc:
        return {"valid": False, "errors": [str(exc)], "citation_validity": 0.0,
                "citation_precision": 0.0, "grounded_claim_rate": 0.0,
                "unsupported_citation_rate": 1.0}
    by_id = {item["citation_id"]: item for item in context.get("items", [])}
    cited = []
    for claim in response["legal_analysis"]:
        cited.extend(claim["citations"])
        if not claim["citations"]:
            errors.append("legal claim without citation")
    for law in response["relevant_laws"]:
        cited.append(law["citation"])
        item = by_id.get(law["citation"])
        if not item:
            errors.append(f"unsupported citation: {law['citation']}")
            continue
        if law["law_name"] != item["law_name"]:
            errors.append(f"law_name mismatch for {law['citation']}")
        if law["article_number"] != item["article_number"]:
            errors.append(f"article_number mismatch for {law['citation']}")
        if law["text"] not in item["article_content"]:
            errors.append(f"text mismatch for {law['citation']}")
    valid_citations = [citation for citation in cited if citation in by_id]
    for citation in cited:
        if citation not in by_id:
            errors.append(f"unsupported citation: {citation}")
    all_text = " ".join([item["claim"] for item in response["legal_analysis"]] +
                         [response["disclaimer"]] + response["issue_summary"])
    context_articles = {item["article_number"] for item in context.get("items", [])}
    for article in ARTICLE_RE.findall(all_text):
        if article not in context_articles:
            errors.append(f"article mention outside context: {article}")
    claim_count = len(response["legal_analysis"])
    grounded_claims = sum(bool(item.get("citations")) for item in response["legal_analysis"])
    total_citations = len(cited)
    return {
        "valid": not errors,
        "errors": list(dict.fromkeys(errors)),
        "citation_validity": len(valid_citations) / total_citations if total_citations else 1.0,
        "citation_precision": (sum(1 for item in response["relevant_laws"] if item["citation"] in by_id) /
                               len(response["relevant_laws"]) if response["relevant_laws"] else 1.0),
        "grounded_claim_rate": grounded_claims / claim_count if claim_count else 1.0,
        "unsupported_citation_rate": 1 - (len(valid_citations) / total_citations if total_citations else 1.0),
    }
