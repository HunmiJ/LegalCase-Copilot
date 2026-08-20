"""Metrics and validation helpers for the frozen case benchmark."""

from __future__ import annotations

import math
from typing import Iterable


def metric_for_ranks(ranks: list[int], relevant: set[str], k: int = 10) -> dict[str, float | None]:
    visible = [case_id for case_id in ranks[:k]]
    first = next((i + 1 for i, case_id in enumerate(visible) if case_id in relevant), None)
    ideal_count = min(len(relevant), k)
    dcg = sum(1.0 / math.log2(i + 2) for i, case_id in enumerate(ranks[:k]) if case_id in relevant)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))
    return {
        "recall": float(bool(first)),
        "first_relevant_rank": first,
        "mrr": (1.0 / first) if first else 0.0,
        "ndcg": (dcg / idcg) if idcg else 0.0,
    }


def aggregate(per_query: Iterable[dict[str, float | None]], total: int) -> dict[str, float]:
    rows = list(per_query)
    return {
        "Recall@1": sum(float(row["first_relevant_rank"] == 1) for row in rows) / total,
        "Recall@3": sum(float(row["first_relevant_rank"] is not None and row["first_relevant_rank"] <= 3) for row in rows) / total,
        "Recall@5": sum(float(row["first_relevant_rank"] is not None and row["first_relevant_rank"] <= 5) for row in rows) / total,
        "MRR": sum(float(row["mrr"]) for row in rows) / total,
        "nDCG@5": sum(float(row["ndcg"]) for row in rows) / total,
    }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1))
    return ordered[index]
