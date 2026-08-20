"""Inspect the V0.7.0 raw case corpus without downloading or parsing cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_CASES = ROOT / "data/raw/cases"
METADATA_PATH = ROOT / "data/case_metadata.json"


def load_metadata() -> list[dict]:
    if not METADATA_PATH.exists():
        return []
    value = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("data/case_metadata.json must contain a JSON array")
    return [item for item in value if isinstance(item, dict)]


def inspect_cases(raw_dir: Path = RAW_CASES, metadata_path: Path = METADATA_PATH) -> dict:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else []
    if not isinstance(metadata, list):
        raise ValueError("case metadata must be a JSON array")
    # The intake directory also contains provenance/planning CSV files.  The
    # corpus inspector reports case files, so only PDFs are intake records.
    files = sorted(path for path in raw_dir.glob("*.pdf") if path.is_file()) if raw_dir.exists() else []
    by_file = {item.get("source_file"): item for item in metadata if isinstance(item, dict)}
    rows = []
    for path in files:
        readable = True
        try:
            path.read_bytes()
        except OSError:
            readable = False
        item = by_file.get(path.name) or by_file.get(str(path).replace("\\", "/"))
        if item is None:
            item = next((candidate for key, candidate in by_file.items() if key and Path(key).name == path.name), None)
        rows.append({
            "file_name": path.name,
            "file_type": path.suffix.lower().lstrip(".") or None,
            "readable": readable,
            "metadata_present": item is not None,
            "source_url_present": bool(item and item.get("source_url")),
            "case_id": item.get("case_id") if item else None,
        })
    ids = [item.get("case_id") for item in metadata if item.get("case_id")]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    return {"case_file_count": len(files), "metadata_count": len(metadata), "duplicate_case_ids": duplicates, "files": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect raw labor case corpus")
    parser.add_argument("--raw-dir", type=Path, default=RAW_CASES)
    parser.add_argument("--metadata", type=Path, default=METADATA_PATH)
    args = parser.parse_args()
    report = inspect_cases(args.raw_dir, args.metadata)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
