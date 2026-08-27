"""Read-only loader for labor_case_dataset JSON, JSONL, and TXT files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator


def _decode_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _record_id(record: dict[str, Any]) -> str:
    original = record.get("original_data") if isinstance(record.get("original_data"), dict) else record
    for key in ("identifier", "id", "case_id", "caseId", "caseNumber"):
        value = original.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def load_json(path: Path) -> Iterator[dict[str, Any]]:
    value = json.loads(_decode_text(path))
    if isinstance(value, list):
        for record in value:
            if not isinstance(record, dict):
                raise ValueError(f"JSON list contains a non-object record: {path}")
            yield {"record": record, "source_file": str(path), "record_id": _record_id(record)}
    elif isinstance(value, dict):
        yield {"record": value, "source_file": str(path), "record_id": _record_id(value)}
    else:
        raise ValueError(f"JSON root must be an object or list: {path}")


def load_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    for line_number, line in enumerate(_decode_text(path).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"JSONL record must be an object at {path}:{line_number}")
        yield {"record": record, "source_file": str(path), "record_id": _record_id(record)}


def load_txt(path: Path) -> Iterator[dict[str, Any]]:
    text = _decode_text(path)
    yield {"record": {"raw_text": text, "title": "", "identifier": ""}, "source_file": str(path), "record_id": ""}


def load_file(path: Path) -> Iterator[dict[str, Any]]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        yield from load_json(path)
    elif suffix == ".jsonl":
        yield from load_jsonl(path)
    elif suffix == ".txt":
        yield from load_txt(path)
    else:
        raise ValueError(f"unsupported labor_case_dataset file type: {path.suffix}")


def load_dataset_sample(path: Path, limit: int = 10) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("limit must be positive")
    records: list[dict[str, Any]] = []
    for item in load_file(Path(path)):
        records.append(item)
        if len(records) >= limit:
            break
    return records
