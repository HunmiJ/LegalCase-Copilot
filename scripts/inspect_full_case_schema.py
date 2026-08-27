"""Inspect the source schema of the full 6,492-case corpus."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = Path(r"<RELATED_PROJECT_ROOT>\data\processed\cases.jsonl")
REPORT_PATH = PROJECT_ROOT / "docs" / "full_case_schema_analysis.md"
SAMPLE_SIZE = 100
RANDOM_SAMPLE_SIZE = 5
RANDOM_SEED = 20260826
TARGET_FIELDS = (
    "case_id", "title", "court", "judgment_date", "raw_text", "keywords",
    "dispute_focus", "basic_facts", "court_reasoning", "judgment_result",
)


def read_first_records(path: Path, limit: int) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if len(records) >= limit:
                break
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(value)
    return records


def type_name(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def display_text(value: object, limit: int = 800) -> str:
    if value is None:
        return "（缺失）"
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    text = text.replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def inspect(records: list[dict]) -> dict:
    fields = sorted({field for record in records for field in record})
    stats = {}
    for field in fields:
        values = [record[field] for record in records if field in record]
        string_lengths = [len(value) for value in values if isinstance(value, str)]
        stats[field] = {
            "occurrences": len(values),
            "types": dict(sorted(Counter(type_name(value) for value in values).items())),
            "string_lengths": {
                "count": len(string_lengths),
                "min": min(string_lengths, default=0),
                "max": max(string_lengths, default=0),
                "mean": round(sum(string_lengths) / len(string_lengths), 2) if string_lengths else 0,
            },
        }
    randomizer = random.Random(RANDOM_SEED)
    sample = randomizer.sample(records, min(RANDOM_SAMPLE_SIZE, len(records)))
    return {"fields": fields, "stats": stats, "sample": sample}


def mapping_assessment() -> list[tuple[str, str, str]]:
    return [
        ("case_id", "直接映射", "源字段 `case_id`"),
        ("title", "直接映射", "源字段 `title`"),
        ("court", "直接映射", "源字段 `court`"),
        ("judgment_date", "改名映射", "源字段 `date`，需统一日期格式"),
        ("raw_text", "组合生成", "源数据无同名字段，可由 `facts`、`legal_issues`、`law_articles`、`judgment` 组合；需保留来源标签"),
        ("keywords", "转换生成", "源数据无同名字段，可由 `legal_issues` 与 `law_articles` 规范化生成，不能无依据臆造"),
        ("dispute_focus", "转换生成", "源数据无同名字段，可从 `legal_issues` 提取；应标记为派生字段"),
        ("basic_facts", "直接/改名映射", "源字段 `facts`"),
        ("court_reasoning", "直接/改名映射", "源字段 `judgment`；需确认其内容是否同时包含裁判结果"),
        ("judgment_result", "待拆分映射", "源字段无同名字段，需从 `judgment` 中拆分结果或保留原文并标记不确定"),
    ]


def render(data: dict, source_path: Path) -> str:
    stats = data["stats"]
    lines = [
        "# Full Case Corpus Schema Analysis",
        "",
        "## 分析范围",
        "",
        f"- 数据源：`{source_path}`",
        f"- 抽取记录数：**{len(data['sample']) if False else SAMPLE_SIZE}**（前 100 条）",
        f"- 随机样本：**{len(data['sample'])}** 条",
        f"- 随机种子：`{RANDOM_SEED}`",
        "",
        "## 字段名称与出现次数",
        "",
        "| 字段 | 出现次数 | 出现比例 | 类型统计 | 字符长度统计（字符串） |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for field in data["fields"]:
        item = stats[field]
        types = ", ".join(f"{name}: {count}" for name, count in item["types"].items())
        lengths = item["string_lengths"]
        length_text = (
            f"n={lengths['count']}, min={lengths['min']}, "
            f"mean={lengths['mean']}, max={lengths['max']}"
        )
        lines.append(f"| `{field}` | {item['occurrences']} | {item['occurrences'] / SAMPLE_SIZE * 100:.2f}% | {types} | {length_text} |")

    lines.extend(["", "## 前 100 条记录中的字段类型统计", ""])
    lines.append("字符长度统计只对字符串值计算；数组、对象和 null 不转换为字符串参与长度统计。")
    lines.extend(["", "## 随机抽取的 5 条完整案例", "", "以下为固定随机种子抽取结果，长文本已截断展示。", ""])
    for number, record in enumerate(data["sample"], start=1):
        lines.extend([
            f"### 案例 {number}",
            "",
            f"- case_id：`{display_text(record.get('case_id'))}`",
            f"- title：{display_text(record.get('title'))}",
            f"- court：{display_text(record.get('court'))}",
            f"- date：`{display_text(record.get('date'))}`",
            f"- 主要文本字段 `facts`：{display_text(record.get('facts'))}",
            f"- 主要文本字段 `legal_issues`：{display_text(record.get('legal_issues'))}",
            f"- 主要文本字段 `judgment`：{display_text(record.get('judgment'))}",
            f"- 其他关键字段 `case_type`：{display_text(record.get('case_type'))}",
            f"- 其他关键字段 `law_articles`：{display_text(record.get('law_articles'))}",
            "",
        ])

    lines.extend(["## 目标字段映射判断", "", "| 目标字段 | 判断 | 方案说明 |", "| --- | --- | --- |"])
    for target, decision, explanation in mapping_assessment():
        lines.append(f"| `{target}` | {decision} | {explanation} |")

    lines.extend([
        "",
        "## 接入建议",
        "",
        "1. 保留源记录和源字段，不直接覆盖原始数据。",
        "2. 将 `date` 映射为 `judgment_date`，同时保留原始日期文本以便追溯。",
        "3. 使用带字段标签的组合文本生成 `raw_text`，避免把 `facts`、法律争点和裁判内容混为无来源文本。",
        "4. `keywords`、`dispute_focus` 属于派生字段，应记录生成规则或置信度。",
        "5. `judgment` 可能同时包含裁判理由和结果，`court_reasoning` 与 `judgment_result` 的拆分需要单独规则和抽样验证。",
        "",
        f"生成时间：`{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}`。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the full case corpus schema")
    parser.add_argument("--input", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    records = read_first_records(args.input, SAMPLE_SIZE)
    if len(records) < SAMPLE_SIZE:
        raise RuntimeError(f"只读取到 {len(records)} 条记录，少于要求的 {SAMPLE_SIZE} 条")
    data = inspect(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(data, args.input), encoding="utf-8")
    print(json.dumps({
        "source": str(args.input),
        "records_inspected": len(records),
        "fields": data["fields"],
        "random_sample_case_ids": [record.get("case_id") for record in data["sample"]],
        "report": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
