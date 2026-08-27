"""Diagnose exact case-id recall versus topic-level related-case recall."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.cases.sources.hybrid_local import LocalHybridCaseProvider

QUERY_FILE = ROOT / "evaluation/full_case_augmented_rag/full_case_rag_queries.json"
CORPUS_DIR = ROOT / "data/processed/full_cases"
REPORT_FILE = ROOT / "docs/full_case_case_recall_analysis.md"

TOPIC_TERMS = {
    "违法解除": ("违法解除", "解除", "辞退", "解雇", "赔偿", "劳动合同"),
    "经济补偿": ("经济补偿", "补偿金", "解除", "终止", "赔偿"),
    "加班": ("加班", "加班费", "休息日", "工作时间", "考勤"),
    "工伤": ("工伤", "工伤认定", "伤残", "工伤保险", "待遇"),
    "未签劳动合同": ("未签", "劳动合同", "二倍工资", "确认劳动关系"),
    "竞业限制": ("竞业", "商业秘密", "竞业限制", "竞业补偿"),
    "欠薪": ("欠薪", "拖欠工资", "工资", "劳动报酬", "薪酬"),
    "试用期": ("试用期", "试用", "转正", "考核", "录用"),
}


def _text(result) -> str:
    values = [
        getattr(result, "title", ""), getattr(result, "basic_facts", ""),
        getattr(result, "dispute_focus", ""), getattr(result, "court_reasoning", ""),
        getattr(result, "judgment_result", ""),
    ]
    return " ".join(str(value or "") for value in values)


def _related(query: dict, result) -> tuple[bool, list[str]]:
    text = _text(result)
    terms = TOPIC_TERMS.get(query.get("category", ""), ())
    matched = [term for term in terms if term in text]
    # This is intentionally a transparent topic-overlap proxy, not an LLM judge.
    return len(matched) >= 2, matched


def main() -> None:
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    provider = LocalHybridCaseProvider(corpus_path=CORPUS_DIR)
    details = []
    exact_hits = 0
    related_hits = 0

    for item in queries:
        results = provider.search(item["query"], top_k=5)
        expected = item.get("expected_cases", [])
        expected_set = set(expected)
        retrieved_ids = [result.case_id for result in results]
        exact = bool(expected_set & set(retrieved_ids))
        related_rows = []
        for result in results:
            is_related, matched = _related(item, result)
            related_rows.append({
                "case_id": result.case_id,
                "title": result.title,
                "related": is_related,
                "matched_topic_terms": matched,
            })
        related = any(row["related"] for row in related_rows)
        exact_hits += int(exact)
        related_hits += int(related)
        details.append({
            "query": item["query"],
            "category": item.get("category", ""),
            "expected_case": expected,
            "retrieved_top5_cases": related_rows,
            "exact_case_hit": exact,
            "semantic_related_case_hit": related,
        })

    def pct(value: int) -> str:
        return f"{value / len(queries):.4f}" if queries else "—"

    lines = [
        "# Full Corpus Case Recall Analysis",
        "",
        "## 结论摘要",
        "",
        f"- query数量：{len(queries)}",
        f"- exact case recall：{pct(exact_hits)}（{exact_hits}/{len(queries)}）",
        f"- related case recall：{pct(related_hits)}（{related_hits}/{len(queries)}）",
        "- 本分析未修改任何检索、embedding、pipeline 或数据文件。",
        "",
        "## 评测设计检查",
        "",
        "当前 `expected_cases` 是从被抽取案例的完整 `case_id` 生成的。query 是按领域模板生成的泛化劳动争议问题，并没有包含该具体案件的案号、当事人或独特事实。因此，要求 top-5 必须命中同一个完整 case_id，衡量的是“特定文档识别”，不是通常意义上的法律类案召回。",
        "",
        "此外，法律类案通常不存在唯一正确案例：同一问题可能对应多个法院、年份和事实变体。将未命中指定案例直接计为失败，会低估检索结果的法律相关性。",
        "",
        "## 新指标建议",
        "",
        "- `exact_case_recall@5`：保留现有严格指标，用于衡量指定案例是否进入 top-5。",
        "- `related_case_recall@5`：top-5 中至少有一条案例与 query 所属争议领域具有明确主题词重叠。该指标是可解释的自动代理指标，不能替代人工类案相关性标注。",
        "- 后续更可靠的 `graded_case_relevance@5`：由法律标注者按0（无关）、1（同领域但事实弱相关）、2（事实和争点相关）、3（高度相似）评分，再计算 nDCG@5 或 Recall@5。",
        "",
        "## 每条 query 的结果",
        "",
    ]
    for row in details:
        lines.extend([
            f"### {row['category']}｜{row['query']}",
            "",
            f"- expected_case：`{'`; `'.join(row['expected_case'])}`",
            f"- exact case recall：`{'是' if row['exact_case_hit'] else '否'}`",
            f"- 是否存在语义相关案例：`{'是' if row['semantic_related_case_hit'] else '否'}`",
            "",
            "| rank | case_id | title | 语义相关 | 匹配主题词 |",
            "|---:|---|---|---|---|",
        ])
        for rank, result in enumerate(row["retrieved_top5_cases"], 1):
            terms = "、".join(result["matched_topic_terms"]) or "—"
            title = result["title"].replace("|", "／")
            lines.append(f"| {rank} | `{result['case_id']}` | {title} | {'是' if result['related'] else '否'} | {terms} |")
        lines.append("")

    lines.extend([
        "## 判定规则与限制",
        "",
        "本报告的“语义相关”不是调用LLM得出的结论，而是按 query 的 category 对 top-5 案例文本做透明的主题词匹配：至少命中两个该领域主题词即标记为相关。该规则可复现，但存在词汇覆盖不足和误判，最终评测应使用人工标注的分级相关性。",
        "",
        "原始逐条结果保存在本脚本运行时内存中；本报告已逐条列出 query、expected case、top-5 case 和判定结果。",
    ])
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"query_count": len(queries), "exact_case_recall_at_5": exact_hits / len(queries),
                      "related_case_recall_at_5": related_hits / len(queries)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
