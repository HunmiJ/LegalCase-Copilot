"""Convert the 6,492-case source corpus into LegalCase-Copilot CaseRecord JSONL."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = Path(r"D:\Project\legal-rag-system\data\processed\cases.jsonl")
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "full_cases" / "cases.jsonl"
REPORT_PATH = PROJECT_ROOT / "docs" / "full_case_conversion_report.md"
SOURCE_MARKER = "labor_case_dataset_6492"
TARGET_FIELDS = (
    "case_id", "title", "court", "judgment_date", "basic_facts",
    "court_reasoning", "judgment_result", "legal_basis", "dispute_focus",
    "keywords", "raw_text", "source_file",
)


def as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def as_string_list(value: object) -> list[str]:
    if value is None:
        return []
    values: Iterable[object] = value if isinstance(value, list) else [value]
    result = []
    for item in values:
        text = as_text(item)
        if text and text not in result:
            result.append(text)
    return result


def build_keywords(record: dict) -> list[str]:
    return as_string_list(record.get("legal_issues")) + [
        item for item in as_string_list(record.get("law_articles"))
        if item not in as_string_list(record.get("legal_issues"))
    ]


def build_raw_text(record: dict) -> str:
    sections = [
        ("title", record.get("title")),
        ("facts", record.get("facts")),
        ("legal_issues", record.get("legal_issues")),
        ("law_articles", record.get("law_articles")),
        ("judgment", record.get("judgment")),
    ]
    return "\n\n".join(f"[{name}]\n{as_text(value)}" for name, value in sections if as_text(value))


def convert(record: dict) -> dict:
    legal_issues = as_string_list(record.get("legal_issues"))
    legal_basis = as_string_list(record.get("law_articles"))
    judgment = as_text(record.get("judgment"))
    converted = {
        "case_id": as_text(record.get("case_id")),
        "title": as_text(record.get("title")),
        "case_number": None,
        "case_type": as_text(record.get("case_type")) or "民事案件",
        "court": as_text(record.get("court")) or None,
        "judgment_date": as_text(record.get("date")) or None,
        "keywords": build_keywords(record),
        "basic_facts": as_text(record.get("facts")) or None,
        "dispute_focus": "；".join(legal_issues) or None,
        "court_reasoning": judgment or None,
        "judgment_result": judgment or None,
        "case_gist": None,
        "legal_basis": legal_basis,
        "related_index": [],
        "database_case_number": None,
        "case_level": None,
        "source_name": SOURCE_MARKER,
        "source_url": None,
        "source_file": SOURCE_MARKER,
        "raw_text": build_raw_text(record),
    }
    required = ("case_id", "title", "case_type", "source_name", "source_file", "raw_text")
    missing = [field for field in required if not as_text(converted.get(field))]
    if missing:
        raise ValueError("missing required fields: " + ", ".join(missing))
    return converted


def read_source(path: Path) -> Iterable[tuple[int, dict]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number}: JSON value is not an object")
            yield line_number, value


def completion_stats(records: list[dict], total: int) -> dict[str, int]:
    def complete(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, dict)):
            return bool(value)
        return True

    return {
        field: sum(complete(record.get(field)) for record in records)
        for field in TARGET_FIELDS
    }


def render_report(stats: dict, output_path: Path) -> str:
    total = stats["total_input"]
    success = stats["success"]
    lines = [
        "# Full Case Corpus Conversion Report",
        "",
        "## 转换概览",
        "",
        f"- 输入：`{SOURCE_PATH}`",
        f"- 输出：`{output_path}`",
        f"- 输入记录数：**{total}**",
        f"- 成功转换数量：**{success}**",
        f"- 失败数量：**{stats['failed']}**",
        "- 转换过程未调用 LLM API。",
        "- 当前 19 条案例库未被读取写入或覆盖。",
        "",
        "## 字段完成率",
        "",
        "完成率按成功转换记录计算；空字符串、空数组和 null 视为未完成。",
        "",
        "| 字段 | 已完成数量 | 完成率 |",
        "| --- | ---: | ---: |",
    ]
    for field in TARGET_FIELDS:
        count = stats["field_completion"][field]
        lines.append(f"| `{field}` | {count} | {count / success * 100 if success else 0:.2f}% |")

    lines.extend([
        "",
        "## 文本长度",
        "",
        f"- raw_text 平均长度：**{stats['average_raw_text_length']:.2f}** 字符",
        f"- raw_text 最短长度：**{stats['min_raw_text_length']}** 字符",
        f"- raw_text 最长长度：**{stats['max_raw_text_length']}** 字符",
        "",
        "## 转换规则",
        "",
        "- `case_id`、`title`、`court`、`date`、`facts` 按要求映射到标准字段。",
        "- `judgment` 同时保留到 `court_reasoning` 和 `judgment_result`，未对原文做主观拆分。",
        "- `law_articles` 映射为 `legal_basis`。",
        "- `legal_issues` 映射为 `dispute_focus`，并与 `law_articles` 合并生成 `keywords`。",
        "- `raw_text` 按 title、facts、legal_issues、law_articles、judgment 分段组合，并保留字段标签。",
        f"- `source_file` 固定标记为 `{SOURCE_MARKER}`。",
        "",
    ])
    if stats["errors"]:
        lines.extend(["## 失败记录", "", "| 行号 | 错误 |", "| ---: | --- |"])
        for item in stats["errors"][:50]:
            lines.append(f"| {item['line']} | {item['error']} |")
        if len(stats["errors"]) > 50:
            lines.append(f"| … | 其余 {len(stats['errors']) - 50} 条错误未展开 |")
        lines.append("")
    else:
        lines.extend(["## 失败记录", "", "未发现失败记录。", ""])
    lines.append(f"生成时间：`{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}`。")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the full normalized case corpus")
    parser.add_argument("--input", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    converted: list[dict] = []
    errors: list[dict] = []
    total_input = 0
    for line_number, record in read_source(args.input):
        total_input += 1
        try:
            converted.append(convert(record))
        except Exception as exc:
            errors.append({"line": line_number, "error": str(exc)})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in converted:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    raw_lengths = [len(record["raw_text"]) for record in converted]
    stats = {
        "total_input": total_input,
        "success": len(converted),
        "failed": len(errors),
        "errors": errors,
        "field_completion": completion_stats(converted, total_input),
        "average_raw_text_length": sum(raw_lengths) / len(raw_lengths) if raw_lengths else 0,
        "min_raw_text_length": min(raw_lengths, default=0),
        "max_raw_text_length": max(raw_lengths, default=0),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(stats, args.output), encoding="utf-8")
    print(json.dumps({
        "input": str(args.input), "output": str(args.output), "report": str(args.report),
        "total_input": total_input, "success": len(converted), "failed": len(errors),
        "average_raw_text_length": round(stats["average_raw_text_length"], 2),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
