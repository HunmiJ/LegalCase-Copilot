"""Analyze replacement-character encoding damage in the 6,492-case corpus."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = Path(r"D:\Project\legal-rag-system\data\processed\cases.jsonl")
REPORT_PATH = PROJECT_ROOT / "docs" / "case_encoding_analysis.md"
FIELDS = ("title", "court", "raw_text", "basic_facts", "judgment_result")
REPLACEMENT_CHARACTER = "�"


def read_records(path: Path) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    errors: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({"line": line_number, "error": str(exc)})
                continue
            if isinstance(record, dict):
                records.append(record)
            else:
                errors.append({"line": line_number, "error": "JSON value is not an object"})
    return records, errors


def field_text(record: dict, field: str) -> str:
    value = record.get(field)
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def analyze(records: list[dict], parse_errors: list[dict]) -> dict:
    field_stats = {}
    damaged_record_indexes: set[int] = set()
    examples: list[dict] = []

    for field in FIELDS:
        missing = 0
        damaged = 0
        damaged_chars = 0
        for index, record in enumerate(records):
            if field not in record or record.get(field) is None:
                missing += 1
                continue
            value = field_text(record, field)
            count = value.count(REPLACEMENT_CHARACTER)
            if count:
                damaged += 1
                damaged_chars += count
                damaged_record_indexes.add(index)
        field_stats[field] = {
            "missing": missing,
            "damaged_records": damaged,
            "damaged_characters": damaged_chars,
        }

    for index, record in enumerate(records):
        damaged_fields = [
            field for field in FIELDS
            if REPLACEMENT_CHARACTER in field_text(record, field)
        ]
        if damaged_fields and len(examples) < 20:
            examples.append({
                "record_number": index + 1,
                "case_id": record.get("case_id", ""),
                "damaged_fields": damaged_fields,
                "title": field_text(record, "title")[:160],
                "court": field_text(record, "court")[:160],
                "raw_text": field_text(record, "raw_text")[:240],
                "basic_facts": field_text(record, "basic_facts")[:240],
                "judgment_result": field_text(record, "judgment_result")[:240],
            })

    return {
        "total_records": len(records),
        "parse_errors": len(parse_errors),
        "damaged_records": len(damaged_record_indexes),
        "field_stats": field_stats,
        "examples": examples,
    }


def ratio(value: int, total: int) -> str:
    return f"{value / total * 100:.2f}%" if total else "0.00%"


def render_report(stats: dict, source_path: Path) -> str:
    total = stats["total_records"]
    lines = [
        "# Case Encoding Analysis",
        "",
        "## 分析范围",
        "",
        f"- 数据源：`{source_path}`",
        f"- 读取记录数：**{total}**",
        f"- JSON 解析错误：**{stats['parse_errors']}**",
        f"- 至少一个目标字段包含 `�` 的记录数：**{stats['damaged_records']}**（{ratio(stats['damaged_records'], total)}）",
        "- 损坏判定：字段文本中出现 Unicode replacement character `�`。",
        "",
        "## 字段统计",
        "",
        "| 字段 | 字段缺失 | 包含 `�` 的记录 | 损坏比例（全部记录） | `�` 字符总数 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for field in FIELDS:
        item = stats["field_stats"][field]
        lines.append(
            f"| `{field}` | {item['missing']} | {item['damaged_records']} | "
            f"{ratio(item['damaged_records'], total)} | {item['damaged_characters']} |"
        )

    lines.extend([
        "",
        "## 前 20 条异常案例示例",
        "",
        "以下内容为原始记录的截断展示，未对原始数据进行修复或回写。",
        "",
    ])
    if not stats["examples"]:
        lines.append("未发现包含 `�` 字符的案例记录。")
    else:
        for number, example in enumerate(stats["examples"], start=1):
            lines.extend([
                f"### {number}. 记录 #{example['record_number']}",
                "",
                f"- case_id：`{example['case_id']}`",
                f"- 损坏字段：`{', '.join(example['damaged_fields'])}`",
                f"- title：`{example['title']}`",
                f"- court：`{example['court']}`",
                f"- raw_text 片段：`{example['raw_text']}`",
                f"- basic_facts 片段：`{example['basic_facts']}`",
                f"- judgment_result 片段：`{example['judgment_result']}`",
                "",
            ])

    lines.extend([
        "## 说明",
        "",
        "本报告仅统计编码损坏特征，不代表法律内容本身的正确性，也未修改原始 `cases.jsonl`。字段缺失与字段编码损坏分别统计；字段不存在不会被计入编码损坏。",
        f"生成时间：`{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}`。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze encoding damage in the full case corpus")
    parser.add_argument("--input", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    records, parse_errors = read_records(args.input)
    stats = analyze(records, parse_errors)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(stats, args.input), encoding="utf-8")

    print(json.dumps({
        "source": str(args.input),
        "total_records": stats["total_records"],
        "damaged_records": stats["damaged_records"],
        "field_stats": stats["field_stats"],
        "parse_errors": stats["parse_errors"],
        "report": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
