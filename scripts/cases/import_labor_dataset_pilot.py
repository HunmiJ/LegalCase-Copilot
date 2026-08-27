"""Import a deterministic 100-record labor_case_dataset pilot.

The source path must be supplied by the caller. This script never downloads,
rewrites, or deletes source data and does not use LLM field completion.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.cases.sources.labor_case_dataset.adapter import import_one_record  # noqa: E402
from backend.cases.sources.labor_case_dataset.loader import load_file  # noqa: E402
from backend.cases.sources.labor_case_dataset.normalizer import normalize  # noqa: E402
from backend.cases.sources.labor_case_dataset.validators import validate_record  # noqa: E402


DEFAULT_OUTPUT = ROOT / "data/raw/cases/labor_pilot"
DEFAULT_REPORT = ROOT / "docs/labor_dataset_pilot_report.md"
FIELDS = (
    "title", "case_number", "court", "judgment_date", "case_type",
    "raw_text", "basic_facts", "judgment_result", "legal_basis",
)


def _has_value(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value)
    return bool(str(value or "").strip())


def _select(records: list[dict[str, Any]], limit: int, seed: int) -> list[dict[str, Any]]:
    if len(records) < limit:
        raise ValueError(f"dataset contains {len(records)} records; {limit} are required")
    rng = random.Random(seed)
    selected = list(records)
    rng.shuffle(selected)
    return selected[:limit]


def _write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# labor_case_dataset 100-Record Pilot Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Input records: {report['input_records']}",
        f"- Selected records: {report['selected_records']}",
        f"- Successfully imported: {report['success_count']}",
        f"- Failed: {report['failure_count']}",
        f"- Duplicate records: {report['duplicate_count']}",
        "",
        "## Field completion",
        "",
        "| Field | Completion |",
        "|---|---:|",
    ]
    for field, rate in report["field_completion_rate"].items():
        lines.append(f"| `{field}` | {rate:.1%} |")
    lines.extend([
        "",
        "## Quality checks",
        "",
        f"- CaseRecord validation success rate: {report['validation_success_rate']:.1%}",
        f"- case_id unique rate: {report['case_id_unique_rate']:.1%}",
        f"- raw_text non-empty rate: {report['raw_text_non_empty_rate']:.1%}",
        f"- duplicate rate: {report['duplicate_rate']:.1%}",
        f"- source_file traceability rate: {report['source_file_traceability_rate']:.1%}",
        "",
        "## Failures",
        "",
    ])
    if report["failures"]:
        lines.extend(f"- {item['error']}" for item in report["failures"])
    else:
        lines.append("None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(input_path: Path, limit: int = 100, seed: int = 42, output_dir: Path = DEFAULT_OUTPUT, report_path: Path = DEFAULT_REPORT) -> dict[str, Any]:
    loaded = list(load_file(input_path))
    selected = _select(loaded, limit, seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    successes: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    duplicate_count = 0
    seen_ids: set[str] = set()

    for item in selected:
        try:
            normalized = validate_record(normalize(item, root=ROOT))
            if normalized.case_id in seen_ids:
                duplicate_count += 1
                continue
            seen_ids.add(normalized.case_id)
            imported = import_one_record(item, output_dir=output_dir)
            successes.append(imported["record"])
        except Exception as exc:
            failures.append({"source_file": str(item.get("source_file", "")), "error": f"{type(exc).__name__}: {exc}"})

    denominator = len(selected) or 1
    field_rates = {
        field: sum(1 for record in successes if _has_value(record.get(field))) / denominator
        for field in FIELDS
    }
    unique_rate = len({record.get("case_id") for record in successes}) / len(successes) if successes else 0.0
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_records": len(loaded),
        "selected_records": len(selected),
        "success_count": len(successes),
        "failure_count": len(failures),
        "duplicate_count": duplicate_count,
        "field_completion_rate": field_rates,
        "validation_success_rate": len(successes) / denominator,
        "case_id_unique_rate": unique_rate,
        "raw_text_non_empty_rate": sum(1 for record in successes if _has_value(record.get("raw_text"))) / denominator,
        "duplicate_rate": duplicate_count / denominator,
        "source_file_traceability_rate": sum(1 for record in successes if _has_value(record.get("source_file"))) / denominator,
        "failures": failures,
        "source_file": str(input_path),
        "selection_seed": seed,
    }
    (output_dir / "import_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(report, report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Import 100 labor_case_dataset records")
    parser.add_argument("--input", type=Path, required=True, help="authorized local JSON, JSONL, or TXT dataset file")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if args.limit != 100:
        parser.error("this pilot requires --limit 100")
    report = run(args.input, args.limit, args.seed, args.output_dir, args.report)
    print(json.dumps({key: report[key] for key in ("input_records", "selected_records", "success_count", "failure_count", "duplicate_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
