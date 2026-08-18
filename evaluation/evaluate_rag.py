"""Automatic V0.6 RAG evaluation using the deterministic mock provider."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.rag import LegalRAGPipeline, MockRAGProvider, validate_citations
from hybrid_utils import canonical_id


def main() -> int:
    queries = json.loads((ROOT / "evaluation/rag_queries.json").read_text(encoding="utf-8"))
    pipeline = LegalRAGPipeline(MockRAGProvider())
    rows = []
    for item in queries:
        result = pipeline.ask(item["query"])
        validation = result["generation_meta"]["validation"]
        status = result["response"].get("generation_status", "success")
        expected = item["expected_behavior"]
        refused = expected in {"out_of_domain", "insufficient", "nonexistent_article"} and (
            bool(result["response"].get("missing_information")) or status == "retrieval_only")
        retrieved_ids = {row["canonical_id"] for row in result["context"]["items"]}
        relevant_ids = set()
        lookup = {(row["source_file"], row["article_number"]): row for row in pipeline.retriever.records}
        for ref in item["relevant_articles"]:
            if (ref["source_file"], ref["article_number"]) in lookup:
                relevant_ids.add(canonical_id(lookup[(ref["source_file"], ref["article_number"])]))
        rows.append({"query_id": item["query_id"], "query": item["query"], "expected_behavior": expected,
                     "citation_validation": validation, "generation_status": status,
                     "refusal_or_insufficient_evidence_correct": refused,
                     "retrieval_coverage": bool(relevant_ids & retrieved_ids) if relevant_ids else None,
                     "context_article_count": result["context"]["article_count"],
                     "context_char_count": result["context"]["char_count"],
                     "retrieval_latency_ms": result["retrieval_latency_ms"]})
    grounded = [row for row in rows if row["expected_behavior"] == "grounded"]
    refusal = [row for row in rows if row["expected_behavior"] != "grounded"]
    summary = {
        "provider": "deterministic mock",
        "automatic_only": True,
        "query_count": len(rows),
        "citation_validity": sum(row["citation_validation"]["citation_validity"] for row in rows) / len(rows),
        "citation_precision": sum(row["citation_validation"]["citation_precision"] for row in rows) / len(rows),
        "grounded_claim_rate": sum(row["citation_validation"]["grounded_claim_rate"] for row in rows) / len(rows),
        "unsupported_citation_rate": sum(row["citation_validation"]["unsupported_citation_rate"] for row in rows) / len(rows),
        "refusal_insufficient_evidence_accuracy": sum(row["refusal_or_insufficient_evidence_correct"] for row in refusal) / len(refusal),
        "retrieval_coverage_grounded": sum(bool(row["retrieval_coverage"]) for row in grounded) / len(grounded),
        "average_context_articles": sum(row["context_article_count"] for row in rows) / len(rows),
        "average_context_chars": sum(row["context_char_count"] for row in rows) / len(rows),
        "rows": rows,
    }
    output = ROOT / "evaluation/results/v0.6_rag_results.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = ROOT / "evaluation/results/v0.6_rag_summary.md"
    markdown.write_text("\n".join([
        "# V0.6 RAG Evaluation", "", "This is an automatic deterministic-mock evaluation; manual review is not represented.", "",
        f"- Citation Validity: {summary['citation_validity']:.4f}",
        f"- Citation Precision: {summary['citation_precision']:.4f}",
        f"- Grounded Claim Rate: {summary['grounded_claim_rate']:.4f}",
        f"- Unsupported Citation Rate: {summary['unsupported_citation_rate']:.4f}",
        f"- Refusal / insufficient evidence accuracy: {summary['refusal_insufficient_evidence_accuracy']:.4f}",
        f"- Retrieval coverage on grounded queries: {summary['retrieval_coverage_grounded']:.4f}",
        f"- Average context: {summary['average_context_articles']:.2f} articles / {summary['average_context_chars']:.0f} chars",
    ]) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("citation_validity", "citation_precision", "grounded_claim_rate", "unsupported_citation_rate", "refusal_insufficient_evidence_accuracy", "retrieval_coverage_grounded")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
