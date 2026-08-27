"""Deterministic safety smoke evaluation for the structured RAG answer layer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.rag.context_builder import build_context
from backend.rag.generator import EVIDENCE_INSUFFICIENT_MESSAGE, GroundedGenerator


class SafetyProvider:
    def __init__(self, citation: str = "LAW-1"):
        self.citation = citation

    def complete(self, messages, response_format=None, temperature=0):
        return json.dumps({"answer": "需要结合检索依据和完整事实判断。",
                           "legal_basis": [{"citation": self.citation, "content": "依据"}],
                           "related_cases": [], "risk_note": "不构成确定性法律意见。", "confidence": "medium"})


def make_context():
    return build_context(law_items=[{"id": "law-1", "law_name": "劳动合同法",
                                     "article_number": "第三十九条", "article_content": "解除规则。",
                                     "source_file": "law.docx"}])


def main() -> int:
    cases = [
        ("normal", "违法解除劳动合同怎么办？", make_context(), SafetyProvider("LAW-1"), False),
        ("empty_context", "违法解除劳动合同怎么办？", {}, SafetyProvider("LAW-1"), True),
        ("out_of_domain", "今天天气怎么样？", make_context(), SafetyProvider("LAW-1"), True),
        ("unsupported_citation", "违法解除劳动合同怎么办？", make_context(), SafetyProvider("LAW-99"), True),
    ]
    rows = []
    for name, query, context, provider, expected_refusal in cases:
        response, meta = GroundedGenerator(provider, max_retries=0).generate(query, context)
        refused = response.get("answer") == EVIDENCE_INSUFFICIENT_MESSAGE
        rows.append({"case": name, "refusal": refused, "expected_refusal": expected_refusal,
                     "refusal_correct": refused == expected_refusal,
                     "citation_valid": meta["validation"]["citation_validity"],
                     "unsupported_claim_rate": meta["validation"]["unsupported_citation_rate"],
                     "response": response})
    refusal_rows = [row for row in rows if row["expected_refusal"]]
    metrics = {
        "query_count": len(rows),
        "refusal_accuracy": sum(row["refusal_correct"] for row in refusal_rows) / len(refusal_rows),
        "citation_accuracy": sum(row["citation_valid"] for row in rows) / len(rows),
        "unsupported_claim_rate": sum(row["unsupported_claim_rate"] for row in rows) / len(rows),
        "rows": rows,
    }
    output = Path(__file__).with_name("safety_metrics.json")
    output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: metrics[key] for key in ("query_count", "refusal_accuracy", "citation_accuracy", "unsupported_claim_rate")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
