"""Runtime-only PDF parser pipeline for collected official case PDFs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.cases.parser import parse_case_pdf
from backend.cases.schemas import CaseRecord


DEFAULT_RAW = ROOT / "data/runtime/cases/raw"
DEFAULT_PROCESSED = ROOT / "data/runtime/cases/processed"
DEFAULT_MANIFEST = ROOT / "data/runtime/cases/case_manifest.json"


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("case_manifest.json must contain a list")
    return {str(row.get("pdf_path")): row for row in rows if row.get("pdf_path")}


def normalize_record(record: CaseRecord, pdf_path: Path, source_url: str | None) -> CaseRecord:
    data = record.to_dict()
    data["source_file"] = str(pdf_path.relative_to(ROOT)).replace("\\", "/")
    data["source_url"] = source_url or data.get("source_url")
    return CaseRecord.from_dict(data)


def parse_runtime_cases(raw_dir: Path = DEFAULT_RAW, processed_dir: Path = DEFAULT_PROCESSED, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    processed_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(manifest_path)
    records: list[CaseRecord] = []
    metadata: list[dict[str, Any]] = []
    for pdf_path in sorted(raw_dir.glob("*.pdf"), key=lambda path: path.name):
        relative_pdf = str(pdf_path.relative_to(ROOT)).replace("\\", "/")
        source_url = (manifest.get(relative_pdf) or {}).get("source_url")
        try:
            parsed, page_count = parse_case_pdf(pdf_path, source_url=source_url)
            record = normalize_record(parsed, pdf_path, source_url)
            records.append(record)
            metadata.append({"case_id": record.case_id, "title": record.title, "source_file": record.source_file, "source_url": record.source_url, "page_count": page_count, "parser_status": "parsed"})
        except Exception as exc:
            metadata.append({"source_file": relative_pdf, "parser_status": "failed", "parse_error": f"{type(exc).__name__}: {exc}"})

    records_path = processed_dir / "runtime_cases.jsonl"
    records_path.write_text("".join(json.dumps(record.to_dict(), ensure_ascii=False) + "\n" for record in sorted(records, key=lambda item: item.case_id)), encoding="utf-8")
    metadata_path = processed_dir / "case_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"pdf_count": len(list(raw_dir.glob("*.pdf"))), "parsed": len(records), "failed": len(metadata) - len(records), "records_path": str(records_path), "metadata_path": str(metadata_path)}


if __name__ == "__main__":
    result = parse_runtime_cases()
    print(json.dumps(result, ensure_ascii=False))
