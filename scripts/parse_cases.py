"""Audit all official case PDFs and write only eligible main-corpus records."""

from __future__ import annotations

import json
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.cases.parser import extract_pdf_text, parse_case_pdf
from backend.cases.schemas import detect_duplicate_case_ids


RAW_DIR = ROOT / "data/raw/cases"
PROCESSED_DIR = ROOT / "data/processed/cases"
JSONL_PATH = PROCESSED_DIR / "cases.jsonl"
METADATA_PATH = ROOT / "data/case_metadata.json"
SOURCE_URLS_PATH = RAW_DIR / "source_urls.csv"
ELIGIBILITY_PATH = ROOT / "data/case_eligibility.json"


def load_source_urls(path: Path = SOURCE_URLS_PATH) -> dict[str, str | None]:
    """Load only explicitly recorded provenance URLs keyed by PDF filename."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        mapping: dict[str, str | None] = {}
        for row in rows:
            filename = (row.get("filename") or "").strip()
            url = (row.get("source_url") or "").strip() or None
            if not filename:
                continue
            if filename in mapping and mapping[filename] != url:
                raise ValueError(f"conflicting source URLs for {filename}")
            mapping[filename] = url
    return mapping


def parse_all(pdf_paths=None) -> list[dict]:
    records = []
    source_urls = load_source_urls()
    paths = sorted(pdf_paths or RAW_DIR.glob("*.pdf"))
    for pdf_path in paths:
        record, _ = parse_case_pdf(pdf_path, source_url=source_urls.get(pdf_path.name))
        records.append(record.to_dict())
    duplicates = detect_duplicate_case_ids(records)
    if duplicates:
        raise ValueError("duplicate case IDs: " + ", ".join(duplicates))
    return records


def load_eligibility(path: Path = ELIGIBILITY_PATH) -> dict[str, dict]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("data/case_eligibility.json must contain a JSON array")
    return {item["source_file"]: item for item in value if item.get("source_file")}


def main() -> int:
    all_records = parse_all()
    eligibility = load_eligibility()
    missing = [record["source_file"] for record in all_records if record["source_file"] not in eligibility]
    if missing:
        raise ValueError("missing corpus eligibility for: " + ", ".join(missing))
    records = [record for record in all_records if eligibility[record["source_file"]]["corpus_status"] == "ELIGIBLE_MAIN_CORPUS"]
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    JSONL_PATH.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")
    metadata = []
    for record in all_records:
        item = {key: record.get(key) for key in ("case_id", "title", "case_number", "case_type", "court", "judgment_date", "keywords", "case_level", "source_name", "source_url", "source_file", "database_case_number")}
        item.update({key: eligibility[record["source_file"]][key] for key in ("corpus_status", "eligibility_reason")})
        metadata.append(item)
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"audited_cases={len(all_records)}")
    print(f"main_corpus_cases={len(records)}")
    print(f"wrote={JSONL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
