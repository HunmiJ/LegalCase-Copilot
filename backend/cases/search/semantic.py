"""Local semantic retrieval over the curated case corpus."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from scripts.semantic_utils import encode_query, load_model

from .models import CaseSearchResult


def case_embedding_text(record: dict[str, Any]) -> str:
    """Build semantic content without provenance or oversized raw text."""
    parts: list[str] = [str(record["title"])]
    # Put compact discriminative fields first so long facts do not consume the
    # encoder context before dispute focus and case gist are represented.
    for name in ("keywords", "dispute_focus", "case_gist"):
        value = record.get(name)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))
    if record.get("basic_facts"):
        parts.append(str(record["basic_facts"])[:800])
    if record.get("judgment_result"):
        parts.append(str(record["judgment_result"])[:300])
    if record.get("court_reasoning"):
        parts.append(str(record["court_reasoning"])[:300])
    return " ".join(parts)


class CaseSemanticIndex:
    def __init__(self, records: list[dict[str, Any]], embeddings: np.ndarray, index: list[dict[str, Any]], model=None) -> None:
        self.records_by_id = {record["case_id"]: record for record in records}
        self.index = sorted(index, key=lambda item: item["position"])
        self.embeddings = np.asarray(embeddings, dtype=np.float32)
        if len(self.records_by_id) != len(self.index) or len(self.embeddings) != len(self.index):
            raise ValueError("case records, embedding index, and embeddings must have equal lengths")
        if self.embeddings.ndim != 2 or not np.isfinite(self.embeddings).all():
            raise ValueError("case embeddings must be a finite 2D matrix")
        if {item["case_id"] for item in self.index} != set(self.records_by_id):
            raise ValueError("embedding index case_ids do not match cases.jsonl")
        self.model = model or load_model(local_files_only=True)

    @classmethod
    def from_files(cls, corpus_path: Path, embeddings_path: Path, index_path: Path, model=None) -> "CaseSemanticIndex":
        records = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        index = json.loads(index_path.read_text(encoding="utf-8"))
        return cls(records, np.load(embeddings_path), index, model=model)

    def search(self, query: str, top_k: int = 10) -> list[CaseSearchResult]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query_vector = encode_query(self.model, query)
        matrix = self.embeddings / np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        scores = matrix @ (query_vector / np.linalg.norm(query_vector))
        positions = np.argsort(-scores, kind="stable")[:top_k]
        retrieved_at = datetime.now(timezone.utc).isoformat()
        results: list[CaseSearchResult] = []
        for position in positions:
            item = self.index[int(position)]
            record = self.records_by_id[item["case_id"]]
            score = float(scores[int(position)])
            results.append(CaseSearchResult(
                case_id=record["case_id"], title=record["title"],
                case_number=record.get("case_number"), database_case_number=record.get("database_case_number"),
                case_type=record.get("case_type"), keywords=record.get("keywords", []),
                basic_facts=record.get("basic_facts"), dispute_focus=record.get("dispute_focus"),
                case_gist=record.get("case_gist"), court_reasoning=record.get("court_reasoning"),
                judgment_result=record.get("judgment_result"), source_name=record.get("source_name", ""),
                source_url=record.get("source_url"), source_file=record.get("source_file"),
                retrieved_at=retrieved_at, retrieval_source="local", score=score,
                semantic_score=score, matched_sources=["local"],
            ))
        return results
