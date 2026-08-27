"""Run the three-file public judgment adapter smoke test and write a report."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.cases.schemas import CaseRecord  # noqa: E402
from backend.cases.sources.public_judgment.adapter import import_one_file  # noqa: E402


INPUT_DIR = ROOT / "data/raw/cases/public_judgments/input/smoke"
OUTPUT_DIR = ROOT / "data/raw/cases/smoke_results"
REPORT_PATH = OUTPUT_DIR / "smoke_report.md"
FIELDS = (
    "title", "case_number", "court", "judgment_date", "case_type",
    "basic_facts", "court_reasoning", "judgment_result", "legal_basis", "raw_text",
)


def _has_value(value: object) -> bool:
    return bool(value) if isinstance(value, list) else bool(str(value or "").strip())


def run() -> dict[str, object]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="public-judgment-smoke-") as temp_dir:
        for path in sorted(INPUT_DIR.glob("sample_*.pdf")):
            summary: dict[str, object] = {"source_file": str(path), "parse_status": "failed"}
            try:
                imported = import_one_file(path, output_dir=Path(temp_dir))
                if imported["status"] == "need_ocr":
                    summary.update({
                        "case_id": "",
                        "title": "",
                        "case_number": "",
                        "court": "",
                        "judgment_date": "",
                        "case_type": "",
                        "basic_facts": "",
                        "court_reasoning": "",
                        "judgment_result": "",
                        "legal_basis": [],
                        "raw_text_length": 0,
                        "parse_status": "need_ocr",
                    })
                else:
                    record = CaseRecord.from_dict(imported["record"])
                    value = record.to_dict()
                    summary.update({field: value.get(field) for field in FIELDS if field != "raw_text"})
                    summary["raw_text_length"] = len(record.raw_text)
                    summary["parse_status"] = "success"
                    summary["case_id"] = record.case_id
            except Exception as exc:  # Keep one bad sample from hiding other results.
                summary["parse_status"] = "failed"
                summary["error"] = f"{type(exc).__name__}: {exc}"
            result_path = OUTPUT_DIR / f"{path.stem}.json"
            result_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(summary)

    successes = [item for item in results if item.get("parse_status") == "success"]
    failures = [item for item in results if item.get("parse_status") == "failed"]
    ocr_needed = [item for item in results if item.get("parse_status") == "need_ocr"]
    unique_ids = [str(item.get("case_id")) for item in successes]
    field_rates = {
        field: sum(1 for item in successes if _has_value(item.get(field))) / len(results) if results else 0
        for field in FIELDS
        if field != "raw_text"
    }
    field_rates["raw_text"] = sum(1 for item in successes if int(item.get("raw_text_length", 0)) > 0) / len(results) if results else 0
    report = {
        "total": len(results),
        "success": len(successes),
        "failed": len(failures),
        "need_ocr": len(ocr_needed),
        "unique_case_id": len(unique_ids) == len(set(unique_ids)),
        "field_completion_rate": field_rates,
        "errors": [item for item in results if item.get("parse_status") != "success"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    lines = [
        "# Public Judgment Adapter Smoke Report",
        "",
        f"- Samples: {report['total']}",
        f"- Success: {report['success']}",
        f"- Failed: {report['failed']}",
        f"- OCR required: {report['need_ocr']}",
        f"- Case ID unique: {'100%' if report['unique_case_id'] else 'FAIL'}",
        "",
        "## Field completion",
        "",
        "| Field | Completion |",
        "|---|---:|",
    ]
    for field, rate in field_rates.items():
        lines.append(f"| `{field}` | {rate:.1%} |" )
    lines.extend(["", "## Parse exceptions", ""])
    if report["errors"]:
        for item in report["errors"]:
            lines.append(f"- `{item['source_file']}`: {item.get('parse_status')} {item.get('error', '')}")
    else:
        lines.append("None")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
