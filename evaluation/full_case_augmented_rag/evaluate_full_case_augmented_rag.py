"""Evaluate law/case context integration before and after full-corpus adoption."""

from __future__ import annotations

import json
import os
from pathlib import Path

from backend.cases.sources.hybrid_local import LocalHybridCaseProvider
from backend.rag.case_context_adapter import adapt_case_results
from backend.rag.context_builder import build_context
from hybrid_utils import HybridRetriever


ROOT = Path(__file__).resolve().parents[2]
QUERIES = ROOT / "evaluation/case_augmented_rag/integrated_queries.json"
OUTPUT = ROOT / "evaluation/full_case_augmented_rag/full_case_augmented_metrics.json"
REPORT = ROOT / "docs/full_case_augmented_rag_evaluation.md"
CORPORA = {"before_19_cases": ROOT / "data/processed/cases", "after_6492_cases": ROOT / "data/processed/full_cases"}


def evaluate_corpus(corpus_path: Path, queries: list[dict], full_case_weight: str | None = None) -> dict:
    previous_path = os.environ.get("CASE_CORPUS_PATH")
    previous_weight = os.environ.get("CASE_SEMANTIC_WEIGHT")
    os.environ["CASE_CORPUS_PATH"] = str(corpus_path)
    if full_case_weight is not None:
        os.environ["CASE_SEMANTIC_WEIGHT"] = full_case_weight
    try:
        laws = HybridRetriever()
        cases = LocalHybridCaseProvider(corpus_path=corpus_path)
        corpus_ids = {record["case_id"] for record in cases.index.bm25_index.records}
        law_hits = []
        case_hits = []
        citation_values = []
        grounded_values = []
        query_rows = []
        for row in queries:
            law_results = laws.search(row["query"], candidate_limit=50, limit=8)
            case_results = cases.search(row["query"], top_k=5)
            context = build_context(law_items=law_results, case_items=adapt_case_results(case_results), max_articles=8, max_cases=5)
            expected_laws = [str(value) for value in row.get("expected_laws", [])]
            expected_cases = set(row.get("expected_cases", []))
            covered_cases = expected_cases & corpus_ids
            retrieved_laws = " ".join(str(item.get("law_name") or "") for item in context["law_items"])
            law_hits.append(sum(expected in retrieved_laws for expected in expected_laws) / len(expected_laws) if expected_laws else 1.0)
            if covered_cases:
                retrieved_cases = {item.get("case_id") for item in context["case_items"]}
                case_hits.append(len(covered_cases & retrieved_cases) / len(covered_cases))
            citations = [item["citation_id"] for item in context["items"]]
            citation_values.append(float(len(citations) == len(set(citations)) and all(
                (item.startswith("LAW-") if item in {x["citation_id"] for x in context["law_items"]} else item.startswith("CASE-"))
                for item in citations
            )))
            grounded_values.append(sum(bool(item.get("text")) for item in context["items"]) / len(context["items"]) if context["items"] else 0.0)
            query_rows.append({"query": row["query"], "law_count": len(context["law_items"]), "case_count": len(context["case_items"]), "case_label_covered": bool(covered_cases)})
        return {
            "corpus_path": str(corpus_path),
            "corpus_count": len(corpus_ids),
            "query_count": len(queries),
            "case_label_covered_query_count": len(case_hits),
            "law_recall": sum(law_hits) / len(law_hits) if law_hits else None,
            "case_recall": sum(case_hits) / len(case_hits) if case_hits else None,
            "citation_validity": sum(citation_values) / len(citation_values) if citation_values else 0.0,
            "grounded_claim_rate": sum(grounded_values) / len(grounded_values) if grounded_values else 0.0,
            "unsupported_claim_rate": 1.0 - (sum(grounded_values) / len(grounded_values) if grounded_values else 0.0),
            "query_rows": query_rows,
        }
    finally:
        if previous_path is None:
            os.environ.pop("CASE_CORPUS_PATH", None)
        else:
            os.environ["CASE_CORPUS_PATH"] = previous_path
        if previous_weight is None:
            os.environ.pop("CASE_SEMANTIC_WEIGHT", None)
        else:
            os.environ["CASE_SEMANTIC_WEIGHT"] = previous_weight


def render(result: dict) -> str:
    lines = [
        "# Full Case-Augmented RAG Evaluation",
        "",
        "## 评测设置",
        "",
        "- 测试集：`evaluation/case_augmented_rag/integrated_queries.json`（20 条）",
        "- before：19 条 benchmark cases",
        "- after：6492 条 full cases",
        "- 检索和 context 构建使用真实 corpus；未调用 LLM API。",
        "",
        "## 指标",
        "",
        "| 模式 | law_recall | case_recall | citation_validity | grounded_claim_rate | unsupported_claim_rate | case label coverage |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in ("before_19_cases", "after_6492_cases"):
        item = result[name]
        def fmt(value): return "—" if value is None else f"{value:.4f}"
        lines.append(f"| {name} | {fmt(item['law_recall'])} | {fmt(item['case_recall'])} | {fmt(item['citation_validity'])} | {fmt(item['grounded_claim_rate'])} | {fmt(item['unsupported_claim_rate'])} | {item['case_label_covered_query_count']}/{item['query_count']} |")
    lines.extend([
        "",
        "## 解释",
        "",
        "`case_recall` 只对 expected case_id 出现在当前 corpus 的 query 计算；没有可对应标注的 query 显示为 `—`，不将标注缺失误判为检索失败。full corpus 的独立真实召回结果见 `docs/full_case_retrieval_evaluation.md`。",
        "`citation_validity`、`grounded_claim_rate` 和 `unsupported_claim_rate` 是 context evidence 层指标：检查 LAW/CASE namespace、context 文本完整性和无证据 context 比例，不冒充 LLM 生成质量。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    queries = json.loads(QUERIES.read_text(encoding="utf-8"))
    result = {
        name: evaluate_corpus(path, queries, full_case_weight="0.2" if name == "after_6492_cases" else None)
        for name, path in CORPORA.items()
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(render(result), encoding="utf-8")
    print(json.dumps({name: {key: value for key, value in item.items() if key not in {"query_rows"}} for name, item in result.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
