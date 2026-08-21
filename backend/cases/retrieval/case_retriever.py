"""Keyword and semantic retrieval over the isolated runtime case corpus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
from rank_bm25 import BM25Okapi

from ..search.semantic import case_embedding_text
from ..search.bm25 import tokenize
from .case_loader import DEFAULT_RUNTIME_CASES, load_runtime_cases


class EmbeddingModel(Protocol):
    def encode(self, sentences: list[str], **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class RuntimeCaseResult:
    case_id: str
    title: str
    dispute_focus: str | None
    judgment_result: str | None
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "dispute_focus": self.dispute_focus,
            "judgment_result": self.judgment_result,
            "score": self.score,
        }


def _retrieval_text(record: dict[str, Any]) -> str:
    values: list[str] = []
    for field in ("title", "dispute_focus", "keywords", "basic_facts", "judgment_result"):
        value = record.get(field)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    return " ".join(values)


class RuntimeCaseRetriever:
    def __init__(self, corpus_path=DEFAULT_RUNTIME_CASES, records: list[dict[str, Any]] | None = None, model: EmbeddingModel | None = None):
        self.records = records if records is not None else load_runtime_cases(corpus_path)
        if not self.records:
            raise ValueError("runtime case corpus is empty")
        self.bm25 = BM25Okapi([tokenize(_retrieval_text(record)) for record in self.records])
        self.model = model
        self._semantic_embeddings: np.ndarray | None = None

    def _ensure_semantic_index(self) -> np.ndarray:
        if self._semantic_embeddings is None:
            if self.model is None:
                from scripts.semantic_utils import load_model
                self.model = load_model(local_files_only=True)
            vectors = self.model.encode([case_embedding_text(record) for record in self.records], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
            matrix = np.asarray(vectors, dtype=np.float32)
            if matrix.ndim != 2 or len(matrix) != len(self.records) or not np.isfinite(matrix).all():
                raise ValueError("invalid runtime case semantic embeddings")
            self._semantic_embeddings = matrix / np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)
        return self._semantic_embeddings

    def _result(self, index: int, score: float) -> RuntimeCaseResult:
        record = self.records[index]
        return RuntimeCaseResult(record["case_id"], record["title"], record.get("dispute_focus"), record.get("judgment_result"), float(score))

    def search(self, query: str, top_k: int = 10, mode: str = "keyword") -> list[dict[str, Any]]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be positive")
        if mode not in {"keyword", "semantic", "hybrid"}:
            raise ValueError("mode must be keyword, semantic, or hybrid")
        keyword_scores = np.asarray(self.bm25.get_scores(tokenize(query)), dtype=np.float32)
        if mode == "keyword":
            scores = keyword_scores
        else:
            from scripts.semantic_utils import encode_query
            matrix = self._ensure_semantic_index()
            query_vector = np.asarray(encode_query(self.model, query), dtype=np.float32)
            query_vector = query_vector / max(float(np.linalg.norm(query_vector)), 1e-12)
            semantic_scores = matrix @ query_vector
            scores = semantic_scores if mode == "semantic" else 0.2 * keyword_scores + 0.8 * semantic_scores
        positions = sorted(range(len(self.records)), key=lambda i: (-float(scores[i]), i))[:top_k]
        return [self._result(index, scores[index]).to_dict() for index in positions]
