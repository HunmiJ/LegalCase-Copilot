"""Quality evaluation for the isolated V0.7.8 runtime case corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data/runtime/cases/processed/runtime_cases.jsonl"
DEFAULT_OUTPUT = ROOT / "data/runtime/cases/processed/corpus_quality_report.json"
REQUIRED_FIELDS = ("case_id", "title", "source_file", "raw_text")
QUALITY_FIELDS = ("basic_facts", "dispute_focus", "court_reasoning", "judgment_result", "legal_basis", "keywords")
ALL_CHECKED_FIELDS = REQUIRED_FIELDS + QUALITY_FIELDS


def present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) and all(isinstance(item, str) and item.strip() for item in value)
    return value is not None


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"record on line {line_number} is not an object")
        records.append(value)
    return records


def evaluate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    missing_counts = {field: 0 for field in ALL_CHECKED_FIELDS}
    case_reports: list[dict[str, Any]] = []
    valid_cases = 0
    for record in records:
        case_id = record.get("case_id") or "<missing-case-id>"
        issues: list[str] = []
        for field in ALL_CHECKED_FIELDS:
            if not present(record.get(field)):
                missing_counts[field] += 1
                issues.append(f"missing_or_empty:{field}")
        if not issues:
            valid_cases += 1
        case_reports.append({"case_id": case_id, "issues": issues})
    total = len(records)
    rates = {field: round((total - missing_counts[field]) / total, 4) if total else 0.0 for field in ALL_CHECKED_FIELDS}
    return {
        "total_cases": total,
        "valid_cases": valid_cases,
        "missing_fields": missing_counts,
        "field_completion_rate": rates,
        "cases": case_reports,
    }


def evaluate_file(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    report = evaluate_records(load_records(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = evaluate_file(args.input, args.output)
    print(json.dumps({key: report[key] for key in ("total_cases", "valid_cases", "missing_fields")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
