"""Analyze the quality of the full processed labor-case corpus."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean, median


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = (
    PROJECT_ROOT / "data" / "processed" / "cases.jsonl",
    PROJECT_ROOT / "data" / "processed" / "cases" / "cases.jsonl",
)
REPORT_PATH = PROJECT_ROOT / "docs" / "full_case_corpus_analysis.md"


def resolve_input_path(path: str | None) -> Path:
    if path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        if not candidate.is_file():
            raise FileNotFoundError(f"案例文件不存在: {candidate}")
        return candidate
    for candidate in DEFAULT_PATHS:
        if candidate.is_file():
            return candidate
    tried = "、".join(str(candidate) for candidate in DEFAULT_PATHS)
    raise FileNotFoundError(f"未找到 cases.jsonl，已检查: {tried}")


def is_missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def percentile(values: list[int], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def load_records(path: Path) -> tuple[list[dict], int]:
    records: list[dict] = []
    invalid_lines = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                invalid_lines += 1
                continue
            if isinstance(record, dict):
                records.append(record)
            else:
                invalid_lines += 1
    return records, invalid_lines


def analyze(records: list[dict], invalid_lines: int = 0) -> dict:
    raw_lengths = [len(record.get("raw_text") or "") for record in records]
    duplicate_keys = Counter(
        (str(record.get("title") or "").strip(), str(record.get("court") or "").strip())
        for record in records
    )
    duplicate_groups = {
        key: count for key, count in duplicate_keys.items()
        if count > 1 and any(key)
    }
    duplicate_records = sum(count - 1 for count in duplicate_groups.values())

    return {
        "total_cases": len(records),
        "title_missing": sum(is_missing(record.get("title")) for record in records),
        "court_missing": sum(is_missing(record.get("court")) for record in records),
        "judgment_date_missing": sum(is_missing(record.get("judgment_date")) for record in records),
        "empty_raw_text": sum(length == 0 for length in raw_lengths),
        "invalid_lines": invalid_lines,
        "raw_text_lengths": {
            "min": min(raw_lengths, default=0),
            "max": max(raw_lengths, default=0),
            "mean": round(mean(raw_lengths), 2) if raw_lengths else 0,
            "median": round(median(raw_lengths), 2) if raw_lengths else 0,
            "p25": round(percentile(raw_lengths, 0.25), 2),
            "p75": round(percentile(raw_lengths, 0.75), 2),
            "p90": round(percentile(raw_lengths, 0.90), 2),
            "p95": round(percentile(raw_lengths, 0.95), 2),
        },
        "duplicate_groups": len(duplicate_groups),
        "duplicate_records": duplicate_records,
    }


def render_report(path: Path, stats: dict) -> str:
    lengths = stats["raw_text_lengths"]
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    return f"""# Full Case Corpus Analysis

## 分析概览

- 数据文件：`{path.relative_to(PROJECT_ROOT).as_posix()}`
- 分析时间：`{generated_at}`
- 有效案例数量：**{stats['total_cases']}**
- 无法解析或非对象 JSON 行：**{stats['invalid_lines']}**

## 字段完整性

| 指标 | 数量 | 占比 |
| --- | ---: | ---: |
| title 缺失 | {stats['title_missing']} | {stats['title_missing'] / stats['total_cases'] * 100 if stats['total_cases'] else 0:.2f}% |
| court 缺失 | {stats['court_missing']} | {stats['court_missing'] / stats['total_cases'] * 100 if stats['total_cases'] else 0:.2f}% |
| judgment_date 缺失 | {stats['judgment_date_missing']} | {stats['judgment_date_missing'] / stats['total_cases'] * 100 if stats['total_cases'] else 0:.2f}% |
| raw_text 为空 | {stats['empty_raw_text']} | {stats['empty_raw_text'] / stats['total_cases'] * 100 if stats['total_cases'] else 0:.2f}% |

## raw_text 长度分布

长度单位为字符。

| 统计量 | 长度 |
| --- | ---: |
| 最小值 | {lengths['min']} |
| P25 | {lengths['p25']} |
| 中位数 | {lengths['median']} |
| 平均值 | {lengths['mean']} |
| P75 | {lengths['p75']} |
| P90 | {lengths['p90']} |
| P95 | {lengths['p95']} |
| 最大值 | {lengths['max']} |

## 重复案例

重复判断键为 `title + court`，空键不计入重复判断。

- 重复键组数量：**{stats['duplicate_groups']}**
- 重复案例数量（每组首条之外的记录）：**{stats['duplicate_records']}**

## 结论

该报告仅描述 `cases.jsonl` 的数据质量，不修改案例数据，也不改变现有检索或 RAG 流程。后续如需纳入完整案例库，建议先针对缺失字段、空文本和重复键进行人工抽样复核。
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze the full processed case corpus")
    parser.add_argument("--input", help="Optional path to cases.jsonl")
    parser.add_argument("--output", help="Optional Markdown report path")
    args = parser.parse_args()

    input_path = resolve_input_path(args.input)
    output_path = Path(args.output) if args.output else REPORT_PATH
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    records, invalid_lines = load_records(input_path)
    stats = analyze(records, invalid_lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(input_path, stats), encoding="utf-8")

    print(f"input: {input_path}")
    print(f"report: {output_path}")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
