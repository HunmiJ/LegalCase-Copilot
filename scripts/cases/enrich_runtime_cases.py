"""Rule-based enrichment for missing runtime case dispute focus fields."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data/runtime/cases/processed/runtime_cases.jsonl"
DEFAULT_OUTPUT = ROOT / "data/runtime/cases/processed/runtime_cases_enriched.jsonl"

FOCUS_TERMS = (
    "确认劳动关系", "新就业形态", "违法解除", "经济补偿", "赔偿金", "工资", "欠薪", "加班费",
    "竞业限制", "调岗调薪", "劳动合同变更", "年休假", "女职工保护", "社会保险", "工伤保险待遇",
    "劳务派遣", "非全日制用工", "严重违纪", "不能胜任工作", "劳动合同终止", "仲裁时效",
)


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "；".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def infer_dispute_focus(record: dict[str, Any]) -> str:
    searchable = "；".join(_text(record.get(field)) for field in ("title", "keywords", "basic_facts", "judgment_result", "raw_text"))
    matched: list[str] = []
    for term in FOCUS_TERMS:
        if term in searchable and term not in matched:
            matched.append(term)
    if matched:
        return "、".join(matched[:4])
    judgment = _text(record.get("judgment_result"))
    if judgment:
        return re.sub(r"\s+", "", judgment)[:120]
    facts = _text(record.get("basic_facts"))
    if facts:
        return re.sub(r"\s+", "", facts)[:120]
    return _text(record.get("title"))[:120]


def enrich_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    enriched_count = 0
    output: list[dict[str, Any]] = []
    for original in records:
        record = dict(original)
        if not _text(record.get("dispute_focus")):
            record["dispute_focus"] = infer_dispute_focus(record)
            enriched_count += 1
        output.append(record)
    return output, enriched_count


def enrich_file(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT) -> dict[str, int]:
    records = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    enriched, enriched_count = enrich_records(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in enriched), encoding="utf-8")
    return {"total_cases": len(enriched), "enriched_dispute_focus": enriched_count}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(enrich_file(args.input, args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
