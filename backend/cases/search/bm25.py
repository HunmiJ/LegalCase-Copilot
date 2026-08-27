"""Small, read-only BM25 index for the curated local case corpus."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jieba
from rank_bm25 import BM25Okapi

from .models import CaseSearchResult


def tokenize(text: str) -> list[str]:
    return [token.strip() for token in jieba.lcut_for_search(text) if token.strip()]


def _search_text(record: dict[str, Any]) -> str:
    values: list[str] = []
    for name in ("title", "keywords", "basic_facts", "dispute_focus", "case_gist", "court_reasoning"):
        value = record.get(name)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    return " ".join(values)


class CaseBM25Index:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        if not records:
            raise ValueError("case corpus must not be empty")
        self.records = records
        self.tokenized_corpus = [tokenize(_search_text(record)) for record in records]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    @classmethod
    def from_jsonl(cls, path: Path) -> "CaseBM25Index":
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return cls(records)

    def search(self, query: str, top_k: int = 10) -> list[CaseSearchResult]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be positive")
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(self.records)), key=lambda index: float(scores[index]), reverse=True)[:top_k]
        retrieved_at = datetime.now(timezone.utc).isoformat()
        return [
            CaseSearchResult(
                case_id=self.records[index]["case_id"],
                title=self.records[index]["title"],
                case_number=self.records[index].get("case_number"),
                database_case_number=self.records[index].get("database_case_number"),
                case_type=self.records[index].get("case_type"),
                court=self.records[index].get("court"),
                judgment_date=self.records[index].get("judgment_date"),
                keywords=self.records[index].get("keywords", []),
                legal_basis=self.records[index].get("legal_basis", []),
                basic_facts=self.records[index].get("basic_facts"),
                dispute_focus=self.records[index].get("dispute_focus"),
                case_gist=self.records[index].get("case_gist"),
                court_reasoning=self.records[index].get("court_reasoning"),
                judgment_result=self.records[index].get("judgment_result"),
                source_name=self.records[index].get("source_name", ""),
                source_url=self.records[index].get("source_url"),
                source_file=self.records[index].get("source_file"),
                retrieved_at=retrieved_at,
                retrieval_source="local",
                score=float(scores[index]),
                matched_sources=["local"],
            )
            for index in ranked
        ]
