"""Explicit runtime cache store; never promotes records to curated corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CaseRuntimeCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, cache_key: str, payload: dict[str, Any]) -> Path:
        required = {"canonical_id", "source_url", "source_name", "retrieved_at", "normalized_data", "cache_version"}
        missing = required - set(payload)
        if missing:
            raise ValueError(f"cache payload missing fields: {', '.join(sorted(missing))}")
        path = self.root / f"{cache_key}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def get(self, cache_key: str) -> dict[str, Any] | None:
        path = self.root / f"{cache_key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
