"""MVP public judgment adapter; it imports one local file at a time."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .loader import load_one
from .normalizer import normalize


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_DIR = ROOT / "data/raw/cases"


def import_one_file(path: Path, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    extracted = load_one(Path(path))
    if extracted["status"] == "need_ocr":
        return {
            "status": "need_ocr",
            "source_file": str(path),
            "page_count": extracted["page_count"],
            "extractor": extracted["extractor"],
        }
    record = normalize(extracted, root=ROOT)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_case_id = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", record.case_id).strip(" .")
    output_path = output_dir / f"public_{safe_case_id}.json"
    output_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "imported", "output": str(output_path), "record": record.to_dict()}
