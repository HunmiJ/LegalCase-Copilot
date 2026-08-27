"""Convert extracted public judgments into the existing CaseRecord schema."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ...schemas import CaseRecord
from .field_extractor import extract_fields


def _stable_case_id(title: str, raw_text: str) -> str:
    digest = hashlib.sha256((title + raw_text).encode("utf-8")).hexdigest()
    return digest[:32]


def normalize(extracted: dict[str, Any], root: Path | None = None) -> CaseRecord:
    path = Path(extracted["path"])
    raw_text = str(extracted.get("raw_text") or "")
    fields = extract_fields(raw_text, path.stem)
    title = str(fields["title"] or path.stem).strip()
    case_number = str(fields["case_number"] or "").strip()
    case_id = case_number or _stable_case_id(title, raw_text)
    source_file = str(path)
    if root is not None:
        try:
            source_file = str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
        except ValueError:
            source_file = str(path)
    case_type = str(fields["case_type"] or "未分类").strip()
    return CaseRecord(
        case_id=case_id,
        title=title,
        case_number=case_number or None,
        case_type=case_type,
        court=str(fields["court"] or "") or None,
        judgment_date=str(fields["judgment_date"] or "") or None,
        keywords=[],
        basic_facts=str(fields["basic_facts"] or "") or None,
        dispute_focus=None,
        court_reasoning=str(fields["court_reasoning"] or "") or None,
        judgment_result=str(fields["judgment_result"] or "") or None,
        legal_basis=list(fields["legal_basis"]),
        source_name="public_judgment",
        source_url=None,
        source_file=source_file,
        raw_text=raw_text,
    )
