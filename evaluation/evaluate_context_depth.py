"""Compare RAG context depth using one local V0.4 reranking pass per query."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from hybrid_utils import HybridRetriever, canonical_id
from reranker_utils import build_candidate_pool, load_reranker, rerank_candidates
from backend.rag.context_builder import build_context


def main():
    queries = json.loads((ROOT / "evaluation/rag_queries.json").read_text(encoding="utf-8"))
    retriever = HybridRetriever()
    reranker = load_reranker(local_files_only=True)
    lookup = {(row["source_file"], row["article_number"]): row for row in retriever.records}
    rows = []
    for query in queries:
        relevant = {canonical_id(lookup[(ref["source_file"], ref["article_number"])])
                    for ref in query["relevant_articles"] if (ref["source_file"], ref["article_number"]) in lookup}
        candidates = build_candidate_pool(retriever, query["query"], 50)
        top10 = rerank_candidates(reranker, query["query"], candidates, 10)
        row = {"query_id": query["query_id"], "expected_behavior": query["expected_behavior"], "relevant_ids": sorted(relevant), "depths": {}}
        for depth in (5, 8, 10):
            context = build_context(top10[:depth], max_articles=depth)
            found = {item["canonical_id"] for item in context["items"]}
            row["depths"][str(depth)] = {"coverage": bool(found & relevant) if relevant else None,
                                          "context_articles": context["article_count"], "context_chars": context["char_count"],
                                          "missing_relevant_ids": sorted(relevant - found)}
        rows.append(row)
    result = {"automatic": True, "depths": {}}
    for depth in (5, 8, 10):
        grounded = [row for row in rows if row["expected_behavior"] == "grounded"]
        values = [row["depths"][str(depth)] for row in grounded]
        result["depths"][str(depth)] = {
            "grounded_query_coverage": sum(item["coverage"] for item in values) / len(values),
            "average_context_articles": sum(item["context_articles"] for item in values) / len(values),
            "average_context_chars": sum(item["context_chars"] for item in values) / len(values),
            "missing_grounded_queries": [row["query_id"] for row in grounded if not row["depths"][str(depth)]["coverage"]],
        }
    result["rows"] = rows
    output = ROOT / "evaluation/results/v0.6_context_depth_results.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["depths"], ensure_ascii=False))


if __name__ == "__main__":
    main()
