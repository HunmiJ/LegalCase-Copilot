"""Capture real-provider citation failures without recording secrets."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import OpenAICompatibleProvider
from backend.rag.pipeline import LegalRAGPipeline
from scripts.hybrid_utils import HybridRetriever
from scripts.reranker_utils import load_reranker

QUERY_FILE = ROOT / "evaluation/full_case_augmented_rag/generation_queries.json"
REPORT_FILE = ROOT / "docs/v1.5.2_citation_failure_analysis.md"


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class CaptureProvider:
    def __init__(self, provider):
        self.provider = provider
        self.name = provider.name
        self.model = provider.model
        self.config = provider.config
        self.raw_responses: list[str] = []

    def complete_with_metadata(self, messages, response_format=None, temperature=0):
        result = self.provider.complete_with_metadata(messages, response_format, temperature)
        content = result.get("content")
        self.raw_responses.append("" if content is None else str(content))
        return result


def _raw_citations(raw: str) -> list[str]:
    # Only extract citation-looking tokens; never persist the full model output.
    return list(dict.fromkeys(re.findall(r"(?:\[(?:LAW|CASE)-?\d+\]|(?:LAW|CASE)-\d+|\[\d+\])", raw)))


def _response_citations(response: dict) -> list[str]:
    citations = []
    for claim in response.get("legal_analysis", []):
        citations.extend(str(value) for value in claim.get("citations", []))
    for field in ("legal_basis", "related_cases"):
        citations.extend(str(item.get("citation")) for item in response.get(field, []) if item.get("citation"))
    return list(dict.fromkeys(citations))


def run_samples(label: str, pipeline: LegalRAGPipeline, capture: CaptureProvider, queries: list[dict]) -> list[dict]:
    records = []
    for item in queries:
        before = len(capture.raw_responses)
        result = pipeline.ask(item["query"])
        response = result.get("response") or {}
        meta = result.get("generation_meta") or {}
        attempts = meta.get("attempts") or []
        raw = capture.raw_responses[before:]
        errors = [error for attempt in attempts for error in attempt.get("citation_errors", [])]
        records.append({
            "mode": label,
            "query": item["query"],
            "allowed_context_citation_ids": [entry.get("citation_id") for entry in result.get("context", {}).get("items", [])],
            "llm_returned_citation_ids": list(dict.fromkeys(value for text in raw for value in _raw_citations(text))),
            "parser_result": {"generation_status": response.get("generation_status"),
                              "citations_after_normalization": _response_citations(response)},
            "validator_rejection_reasons": list(dict.fromkeys(errors)),
            "retry_count": meta.get("retry_count"),
            "retry_result": {"generation_status": response.get("generation_status"),
                             "fallback": meta.get("fallback"),
                             "validation_valid": (meta.get("validation") or {}).get("valid")},
            "attempt_diagnostics": [{"attempt_number": attempt.get("attempt_number"),
                                     "exception_type": attempt.get("exception_type"),
                                     "json_parse_success": attempt.get("json_parse_success"),
                                     "schema_validation_success": attempt.get("schema_validation_success"),
                                     "citation_validation_success": attempt.get("citation_validation_success"),
                                     "citation_errors": attempt.get("citation_errors", [])}
                                    for attempt in attempts],
        })
    return records


def main() -> None:
    load_dotenv()
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    provider = CaptureProvider(OpenAICompatibleProvider())
    retriever = HybridRetriever()
    reranker = load_reranker(local_files_only=True)
    law_only = LegalRAGPipeline(provider, retriever=retriever, reranker=reranker, include_cases=False)
    augmented = LegalRAGPipeline(provider, retriever=retriever, reranker=reranker, include_cases=True,
                                  case_corpus_path=ROOT / "data/processed/full_cases")
    law_samples = run_samples("law-only", law_only, provider, queries[:10])
    case_samples = run_samples("law+6492-cases", augmented, provider, queries[10:15])
    samples = law_samples + case_samples
    lines = [
        "# V1.5.2 Citation Failure Analysis",
        "",
        "## 根因摘要",
        "",
        "法规-only 主 pipeline 的旧调用 `build_context(reranked, context_top_k)` 触发兼容路径，法规 context ID 为 `[1]`、`[2]`。但 generator prompt 要求模型使用 `LAW-1`、`LAW-2`，因此模型按 prompt 返回的 LAW citation 在 validator 的 `by_id` 中不存在，产生 `unsupported citation`。案例增强路径使用命名参数，context 为 `LAW-*` 和 `CASE-*`，所以成功率明显更高。",
        "",
        "## 格式链路检查",
        "",
        "| 层 | 当前行为 |",
        "|---|---|",
        "| context builder 旧位置调用 | `[1]`、`[2]`（仅保留旧调用兼容性） |",
        "| context builder 命名调用 | `LAW-1`、`CASE-1`，展示为 `[LAW-1]`、`[CASE-1]` |",
        "| prompt | 要求 `LAW-*` / `CASE-*`，禁止自行生成不存在 ID |",
        "| parser | 接受 `LAW-1`、`CASE-1`、`[LAW-1]`、`[CASE-1]`；数字保持为旧 `[1]` |",
        "| validator | 只接受能在当前 context 中精确找到的 citation；不做猜测映射 |",
        "",
        "## 真实失败样本",
        "",
        "以下仅保存 citation 令牌、解析状态和 validator 错误，不保存完整模型输出或任何 API 凭据。",
        "",
    ]
    for index, sample in enumerate(samples, 1):
        lines.extend([
            f"### {index}. {sample['mode']}｜{sample['query']}",
            "",
            f"- context允许的 citation IDs：`{', '.join(sample['allowed_context_citation_ids'])}`",
            f"- LLM返回的 citation IDs：`{', '.join(sample['llm_returned_citation_ids']) or '未提取到'}`",
            f"- parser结果：`{json.dumps(sample['parser_result'], ensure_ascii=False)}`",
            f"- validator拒绝原因：`{'; '.join(sample['validator_rejection_reasons']) or '无'}`",
            f"- retry后结果：`{json.dumps(sample['retry_result'], ensure_ascii=False)}`；retry_count=`{sample['retry_count']}`",
            "",
        ])
    lines.extend([
        "## 安全修复方案",
        "",
        "1. 仅让主 pipeline 的法规-only context 也走 `LAW-*` 命名空间；保留 `build_context` 的旧位置调用和 `[1]` 行为，避免破坏历史调用者。",
        "2. 保留严格 validator，不把不存在的 citation 映射到最近编号。",
        "3. 仅规范化成对的安全表示：`[LAW-1]`→`LAW-1`、`[CASE-1]`→`CASE-1`；最终仍必须在当前 context 精确存在。",
        "4. prompt 明确 citation 只能从本次 context 显式列出的 ID 中选择。",
        "",
        "## 评测限制",
        "",
        "本报告的样本来自真实 provider 请求；为保护敏感信息，只记录 citation 令牌和校验诊断，不记录完整回答。最终法律回答质量仍需人工审核。",
    ])
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"sample_count": len(samples), "law_only": len(law_samples),
                      "law_plus_cases": len(case_samples)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
