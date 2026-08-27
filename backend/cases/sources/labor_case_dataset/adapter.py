"""Import a sample or one record without modifying the source dataset."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .loader import load_dataset_sample
from .normalizer import normalize
from .validators import validate_record, validate_unique_case_ids


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_DIR = ROOT / "data/raw/cases"


def _safe_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .") or "unknown"


def import_one_record(
    loaded: dict[str, Any],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    record = validate_record(normalize(loaded, root=ROOT))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"public_{_safe_filename(record.case_id)}.json"
    output_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "imported", "output": str(output_path), "record": record.to_dict()}


def import_dataset_sample(
    path: Path,
    limit: int = 10,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[dict[str, Any]]:
    loaded_records = load_dataset_sample(Path(path), limit=limit)
    normalized = [normalize(item, root=ROOT) for item in loaded_records]
    validate_unique_case_ids(normalized)
    return [import_one_record(item, output_dir=output_dir) for item in loaded_records]
