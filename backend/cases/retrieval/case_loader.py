"""Loader for the enriched runtime case corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..schemas import CaseRecord

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUNTIME_CASES = ROOT / "data/runtime/cases/processed/runtime_cases_enriched.jsonl"


def load_runtime_cases(path: Path = DEFAULT_RUNTIME_CASES) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        CaseRecord.from_dict(record)
        records.append(record)
    if not records:
        raise ValueError("runtime case corpus is empty")
    return records
