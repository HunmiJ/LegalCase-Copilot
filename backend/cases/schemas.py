"""Stable, source-traceable schema for official labor dispute cases."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class CaseValidationError(ValueError):
    """Raised when a case record violates the V0.7.0 data contract."""


REQUIRED_FIELDS = ("case_id", "title", "case_type", "source_name", "source_file", "raw_text")
ALL_FIELDS = (
    "case_id", "title", "case_number", "case_type", "court", "judgment_date",
    "keywords", "basic_facts", "dispute_focus", "court_reasoning", "judgment_result",
    "legal_basis", "case_level", "source_name", "source_url", "source_file", "raw_text",
)


@dataclass
class CaseRecord:
    """A normalized case record; nullable fields remain explicitly nullable."""

    case_id: str
    title: str
    case_type: str
    source_name: str
    source_file: str
    raw_text: str
    case_number: str | None = None
    court: str | None = None
    judgment_date: str | None = None
    keywords: list[str] = field(default_factory=list)
    basic_facts: str | None = None
    dispute_focus: str | None = None
    court_reasoning: str | None = None
    judgment_result: str | None = None
    legal_basis: list[str] = field(default_factory=list)
    case_level: str | None = None
    source_url: str | None = None

    def __post_init__(self) -> None:
        for field_name in REQUIRED_FIELDS:
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise CaseValidationError(f"{field_name} must be a non-empty string")
        if not isinstance(self.keywords, list) or not all(isinstance(item, str) and item.strip() for item in self.keywords):
            raise CaseValidationError("keywords must be a list of non-empty strings")
        if not isinstance(self.legal_basis, list) or not all(isinstance(item, str) and item.strip() for item in self.legal_basis):
            raise CaseValidationError("legal_basis must be a list of non-empty strings")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CaseRecord":
        if not isinstance(value, dict):
            raise CaseValidationError("case record must be an object")
        missing = [name for name in REQUIRED_FIELDS if name not in value]
        if missing:
            raise CaseValidationError("missing fields: " + ", ".join(missing))
        unknown = set(value) - set(ALL_FIELDS)
        if unknown:
            raise CaseValidationError("unknown fields: " + ", ".join(sorted(unknown)))
        data = {name: value.get(name) for name in ALL_FIELDS if name in value}
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_duplicate_case_ids(records: list[CaseRecord | dict[str, Any]]) -> list[str]:
    """Return duplicate canonical IDs in first-seen order."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for record in records:
        case_id = record.case_id if isinstance(record, CaseRecord) else record.get("case_id")
        if case_id in seen and case_id not in duplicates:
            duplicates.append(case_id)
        seen.add(case_id)
    return duplicates
