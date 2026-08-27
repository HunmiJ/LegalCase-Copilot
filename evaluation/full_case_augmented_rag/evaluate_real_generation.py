"""Run the two real-provider generation evaluations and record only observable metrics."""

from __future__ import annotations

import json
import os
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import OpenAICompatibleProvider
from backend.rag.pipeline import LegalRAGPipeline
from backend.rag.generator import materialize_legal_basis
from scripts.hybrid_utils import HybridRetriever
from scripts.reranker_utils import load_reranker

QUERY_FILE = ROOT / "evaluation/full_case_augmented_rag/generation_queries.json"
OUTPUT_FILE = ROOT / "evaluation/results/full_case_generation_metrics.json"
REPORT_FILE = ROOT / "docs/v1.5_generation_evaluation.md"


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _mean(values: list[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    return round(sum(usable) / len(usable), 4) if usable else None


def _law_accuracy(response: dict, context: dict, expected: list[str]) -> float | None:
    if not expected:
        return None
    by_id = {item.get("citation_id"): item for item in context.get("items", [])}
    cited_names = []
    for item in response.get("legal_basis", []):
        source = by_id.get(item.get("citation"))
        if source and source.get("type", "law") == "law":
            cited_names.append(str(source.get("law_name") or ""))
    return round(sum(any(law in name or name in law for name in cited_names) for law in expected) / len(expected), 4)


def _case_accuracy(response: dict, expected_topics: list[str]) -> float | None:
    if not expected_topics:
        return None
    cited = response.get("related_cases", [])
    text = " ".join(str(item.get(key) or "") for item in cited for key in ("title", "reasoning"))
    return round(sum(topic in text for topic in expected_topics) / len(expected_topics), 4)


def run_mode(label: str, pipeline: LegalRAGPipeline, queries: list[dict]) -> dict:
    rows = []
    for item in queries:
        try:
            result = pipeline.ask(item["query"])
            response = result.get("response") or {}
            meta = result.get("generation_meta") or {}
            validation = meta.get("validation") or {}
            success = response.get("generation_status") == "success" and not meta.get("fallback", False)
            rows.append({
                "query": item["query"],
                "generation_success": success,
                "citation_validity": validation.get("citation_validity") if success else None,
                "legal_basis_accuracy": _law_accuracy(response, result.get("context") or {}, item.get("expected_laws", [])) if success else None,
                "case_reference_accuracy": _case_accuracy(response, item.get("expected_case_topics", [])) if success else None,
                "unsupported_claim_rate": validation.get("unsupported_citation_rate") if success else None,
                "failure_reason": None if success else response.get("failure_reason") or response.get("generation_status"),
                "provider": getattr(pipeline.provider, "name", "unknown"),
            })
        except Exception as exc:
            rows.append({"query": item["query"], "generation_success": False,
                         "citation_validity": None, "legal_basis_accuracy": None,
                         "case_reference_accuracy": None, "unsupported_claim_rate": None,
                         "failure_reason": f"{type(exc).__name__}: {str(exc)[:200]}",
                         "provider": getattr(pipeline.provider, "name", "unknown")})
    return {
        "mode": label,
        "query_count": len(queries),
        "generation_success_rate": round(sum(row["generation_success"] for row in rows) / len(rows), 4) if rows else None,
        "citation_validity": _mean([row["citation_validity"] for row in rows]),
        "legal_basis_accuracy": _mean([row["legal_basis_accuracy"] for row in rows]),
        "case_reference_accuracy": _mean([row["case_reference_accuracy"] for row in rows]),
        "unsupported_claim_rate": _mean([row["unsupported_claim_rate"] for row in rows]),
        "per_query": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="run only the first N queries")
    args = parser.parse_args()
    load_dotenv()
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    if args.limit:
        queries = queries[:args.limit]
    output = {"query_count": len(queries), "provider": None, "modes": {},
              "limitations": []}
    try:
        provider = OpenAICompatibleProvider()
        output["provider"] = {"name": provider.name, "model": provider.model,
                               "base_url_configured": bool(provider.config.base_url)}
        # Fail fast on an unavailable endpoint. This is a real provider probe,
        # not a substitute answer and prevents 60 repeated timeout waits.
        provider.complete_with_metadata(
            [{"role": "system", "content": "只返回JSON。"},
             {"role": "user", "content": "返回{\"ok\":true}"}],
            {"type": "json_object"}, 0,
        )
        retriever = HybridRetriever()
        reranker = load_reranker(local_files_only=True)
        benchmark_pipeline = LegalRAGPipeline(provider, retriever=retriever, reranker=reranker,
                                               include_cases=False)
        full_pipeline = LegalRAGPipeline(provider, retriever=retriever, reranker=reranker,
                                          include_cases=True,
                                          case_corpus_path=ROOT / "data/processed/full_cases")
        output["modes"]["law_only"] = run_mode("law-only", benchmark_pipeline, queries)
        output["modes"]["law_plus_6492_cases"] = run_mode("law+6492-cases", full_pipeline, queries)
    except Exception as exc:
        output["provider_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        output["limitations"].append("真实provider未能初始化或评测未完成；未用mock结果替代真实生成结果。")
    output["limitations"].extend([
        "legal_basis_accuracy 仅验证模型引用的法规是否来自检索上下文且与expected_laws名称匹配，不代表法律结论正确。",
        "case_reference_accuracy 仅验证模型引用案例文本是否包含expected_case_topics，不代表人工判断的类案相似性。",
        "unsupported_claim_rate 使用citation validator的unsupported_citation_rate；没有人工逐句事实核验。",
    ])
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    law_only = output["modes"].get("law_only", {})
    augmented = output["modes"].get("law_plus_6492_cases", {})
    metric_names = ("generation_success_rate", "citation_validity", "legal_basis_accuracy",
                    "case_reference_accuracy", "unsupported_claim_rate")
    def value(mode: dict, name: str) -> str:
        result = mode.get(name)
        return "—" if result is None else str(result)
    rows = "\n".join(f"| {name} | {value(law_only, name)} | {value(augmented, name)} |" for name in metric_names)
    report = f"""# V1.5 Real LLM Generation Evaluation

## 实验设置

- 测试问题：{len(queries)} 条，覆盖八类劳动争议。
- A：法规-only模式。
- B：法规 + 6492案例增强模式。
- provider：`{(output.get('provider') or {}).get('name', '未初始化')}`；model：`{(output.get('provider') or {}).get('model', '未初始化')}`。
- 两组使用相同问题、法规检索、reranker 和真实结构化生成链路。

## 指标对比

| 指标 | 法规-only | 法规+6492案例 |
|---|---:|---:|
{rows}

## 自动评价范围

- `generation_success_rate`：真实 provider 返回并通过结构化 schema、citation 校验且未 fallback 的比例。
- `citation_validity`：citation validator 的有效率。
- `legal_basis_accuracy`：模型引用的法规名称与 `expected_laws` 的名称匹配代理指标，不代表法律结论正确。
- `case_reference_accuracy`：被引用案例文本与 `expected_case_topics` 的词项匹配代理指标，不代表人工认定的类案相似性。
- `unsupported_claim_rate`：使用 citation validator 的 unsupported citation 指标，不是人工逐句事实核验。

## 真实运行限制

{output.get('provider_error', '本次运行未记录 provider 初始化错误。')}

如果 provider 不可达或生成失败，指标显示为 `—` 或失败率；本评测没有用 mock、规则答案或人工评分替代真实结果。因此，在缺少人工参考答案时，不能据此宣称最终法律问答质量提升或下降。

后续若要评价法律答案本身，应为每条问题增加人工标注的法规适用性、类案相关性和事实性错误标签，并在固定 provider/model 与温度下重复运行。

详细逐条结果位于 `evaluation/results/full_case_generation_metrics.json`。
"""
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
