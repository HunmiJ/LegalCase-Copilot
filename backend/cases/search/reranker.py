"""Cross-Encoder reranking for a small, fixed local case candidate set."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
from sentence_transformers import CrossEncoder

MODEL_NAME = "BAAI/bge-reranker-base"
DEFAULT_CANDIDATE_DEPTH = 3


class RerankerUnavailableError(RuntimeError):
    """Raised when the optional cross-encoder cannot be loaded or used."""


def load_case_reranker(local_files_only: bool = True) -> CrossEncoder:
    try:
        return CrossEncoder(MODEL_NAME, device="cpu", local_files_only=local_files_only)
    except Exception as exc:  # pragma: no cover - exercised by fallback tests
        raise RerankerUnavailableError(str(exc)) from exc


def _field(value: Any, limit: int | None = None) -> str:
    if isinstance(value, list):
        text = "、".join(str(item) for item in value)
    else:
        text = str(value or "")
    return text[:limit] if limit else text


def case_reranker_text(record: Any) -> str:
    """Build bounded relevance text; provenance never enters the pair."""
    get = record.get if isinstance(record, dict) else lambda name, default=None: getattr(record, name, default)
    parts = [
        f"标题：{_field(get('title'))}",
        f"关键词：{_field(get('keywords'))}",
        f"基本案情：{_field(get('basic_facts'), 900)}",
        f"争议焦点：{_field(get('dispute_focus'), 500)}",
        f"裁判要旨：{_field(get('case_gist'), 900)}",
        f"裁判理由：{_field(get('court_reasoning'), 600)}",
    ]
    return "\n".join(part for part in parts if not part.endswith("："))


def rerank(model: CrossEncoder, query: str, candidates: list, top_k: int = 3, max_length: int = 512) -> list:
    if not candidates:
        return []
    unique = {}
    for rank, candidate in enumerate(candidates, 1):
        unique.setdefault(candidate.case_id, (rank, candidate))
    ordered = list(unique.values())
    pairs = [(query, case_reranker_text(candidate)) for _, candidate in ordered]
    try:
        scores = model.predict(pairs, batch_size=16, max_length=max_length, show_progress_bar=False, convert_to_numpy=True)
    except Exception as exc:  # pragma: no cover - exercised by fallback tests
        raise RerankerUnavailableError(str(exc)) from exc
    scores = np.asarray(scores, dtype=float).reshape(-1)
    if len(scores) != len(ordered) or not np.isfinite(scores).all():
        raise RerankerUnavailableError("reranker returned invalid scores")
    ranked = []
    for (original_rank, candidate), score in zip(ordered, scores):
        ranked.append(replace(candidate, reranker_score=float(score), original_hybrid_rank=original_rank))
    ranked.sort(key=lambda item: (-float(item.reranker_score), item.case_id))
    return [replace(candidate, final_rank=rank, rank=rank) for rank, candidate in enumerate(ranked[:top_k], 1)]
