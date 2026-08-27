"""Build a deterministic, evidence-derived evaluation set for the full corpus."""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/processed/full_cases/cases.jsonl"
DEFAULT_OUTPUT = ROOT / "evaluation/full_case_retrieval/full_case_queries.json"
DEFAULT_REPORT = ROOT / "docs/full_case_eval_dataset_report.md"
SEED = 20260826
TARGET_COUNT = 30
TOPICS = {
    "违法解除": ("违法解除", "违法解除劳动合同", "解除劳动合同"),
    "经济补偿": ("经济补偿", "补偿金"),
    "加班": ("加班", "加班费"),
    "工伤": ("工伤", "工伤保险"),
    "未签劳动合同": ("未签订劳动合同", "未签劳动合同", "二倍工资"),
    "竞业限制": ("竞业限制", "竞业协议", "竞业"),
    "欠薪": ("拖欠工资", "欠薪", "未支付劳动报酬", "工资未支付"),
    "试用期": ("试用期",),
}
TARGET_PER_TOPIC = {
    "违法解除": 4,
    "经济补偿": 4,
    "加班": 4,
    "工伤": 4,
    "未签劳动合同": 4,
    "竞业限制": 4,
    "欠薪": 3,
    "试用期": 3,
}


def load_records(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    records.append(value)
    return records


def field_texts(record: dict) -> list[tuple[str, str]]:
    texts = []
    # The normalized full corpus retains the source evidence under the
    # CaseRecord names dispute_focus/basic_facts/judgment_result. These are
    # direct conversions of the source legal_issues/facts/judgment fields.
    for source_field, normalized_field in (
        ("legal_issues", "dispute_focus"),
        ("facts", "basic_facts"),
        ("judgment", "judgment_result"),
    ):
        field = source_field if source_field in record else normalized_field
        value = record.get(field)
        if isinstance(value, list):
            value = "；".join(str(item) for item in value)
        elif value is None:
            value = ""
        else:
            value = str(value)
        if value.strip():
            texts.append((source_field, value.strip()))
    return texts


def evidence_query(record: dict, terms: tuple[str, ...]) -> tuple[str, str]:
    """Return a query copied from a matching source field, without generation."""
    for field, text in field_texts(record):
        pieces = [piece.strip() for piece in re.split(r"[。！？；\n]", text) if piece.strip()]
        for piece in pieces:
            if any(term in piece for term in terms) and len(piece) >= 8:
                return piece[:180], field
    for field, text in field_texts(record):
        for term in terms:
            position = text.find(term)
            if position >= 0:
                start = max(0, position - 60)
                return text[start:start + 180], field
    raise ValueError(f"record {record.get('case_id')} has no matching evidence")


def build_dataset(records: list[dict], seed: int = SEED) -> tuple[list[dict], list[dict]]:
    randomizer = random.Random(seed)
    candidates = {}
    for topic, terms in TOPICS.items():
        topic_candidates = []
        for record in records:
            try:
                query, source_field = evidence_query(record, terms)
            except ValueError:
                continue
            topic_candidates.append((record, query, source_field))
        randomizer.shuffle(topic_candidates)
        if len(topic_candidates) < TARGET_PER_TOPIC[topic]:
            raise RuntimeError(f"主题 {topic} 只有 {len(topic_candidates)} 条候选，无法抽取 {TARGET_PER_TOPIC[topic]} 条")
        candidates[topic] = topic_candidates[:TARGET_PER_TOPIC[topic]]

    rows = []
    metadata = []
    for topic, topic_candidates in candidates.items():
        for record, query, source_field in topic_candidates:
            rows.append({"query": query, "relevant_case_ids": [record["case_id"]]})
            metadata.append({"topic": topic, "case_id": record["case_id"], "source_field": source_field, "query": query})

    randomizer.shuffle(rows)
    randomizer.shuffle(metadata)
    return rows, metadata


def render_report(records: list[dict], rows: list[dict], metadata: list[dict], input_path: Path) -> str:
    topic_counts = Counter(item["topic"] for item in metadata)
    case_ids = {case_id for row in rows for case_id in row["relevant_case_ids"]}
    lines = [
        "# Full Case Evaluation Dataset Report",
        "",
        "## 数据集概览",
        "",
        f"- 输入语料：`{input_path}`",
        f"- full corpus 案例总数：**{len(records)}**",
        f"- query 数量：**{len(rows)}**",
        f"- 对应唯一案例数量：**{len(case_ids)}**",
        f"- 随机种子：`{SEED}`",
        "- query 来源：原始案例字段 `legal_issues`、`facts`、`judgment` 的匹配片段；在标准化 full corpus 中分别对应 `dispute_focus`、`basic_facts`、`judgment_result`。",
        "- LLM API 调用：0 次。",
        "",
        "## 覆盖领域",
        "",
        "| 领域 | query 数量 |",
        "| --- | ---: |",
    ]
    for topic in TOPICS:
        lines.append(f"| {topic} | {topic_counts[topic]} |")
    lines.extend([
        "",
        "## 数据格式",
        "",
        "输出文件只包含 `query` 和 `relevant_case_ids` 两个字段。每条 query 对应抽取案例的 `case_id` 作为相关案例标注。",
        "现有 `evaluation/case_retrieval_queries.json` 未被修改。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build full-corpus retrieval evaluation queries")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    records = load_records(args.input)
    rows, metadata = build_dataset(records)
    if len(rows) != TARGET_COUNT:
        raise RuntimeError(f"expected {TARGET_COUNT} queries, got {len(rows)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(records, rows, metadata, args.input), encoding="utf-8")
    print(json.dumps({
        "input_records": len(records),
        "query_count": len(rows),
        "unique_case_count": len({case_id for row in rows for case_id in row["relevant_case_ids"]}),
        "topic_counts": dict(Counter(item["topic"] for item in metadata)),
        "output": str(args.output),
        "report": str(args.report),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
