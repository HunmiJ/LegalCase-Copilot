"""Validation helpers for normalized labor_case_dataset records."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ...schemas import CaseRecord


def validate_record(record: CaseRecord | dict[str, Any], root: Path | None = None) -> CaseRecord:
    validated = record if isinstance(record, CaseRecord) else CaseRecord.from_dict(record)
    if not validated.raw_text.strip():
        raise ValueError("raw_text must be non-empty")
    if not validated.title.strip():
        raise ValueError("title must be non-empty")
    if not validated.source_file.strip():
        raise ValueError("source_file must be traceable")
    if root is not None and Path(validated.source_file).is_absolute():
        try:
            Path(validated.source_file).resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError("source_file is outside the declared root") from exc
    return validated


def validate_unique_case_ids(records: Iterable[CaseRecord | dict[str, Any]]) -> None:
    ids: list[str] = []
    for record in records:
        ids.append(record.case_id if isinstance(record, CaseRecord) else str(record.get("case_id", "")))
    if len(ids) != len(set(ids)):
        raise ValueError("case_id values must be unique")
