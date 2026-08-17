"""Shared helpers for BGE semantic retrieval."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
MODEL_NAME = "BAAI/bge-small-zh-v1.5"
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


def load_records(path: Path | None = None) -> list[dict]:
    path = path or ROOT / "data/processed/laws.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def embedding_text(record: dict) -> str:
    parts = [record["law_name"]]
    if record.get("chapter"):
        parts.append(record["chapter"])
    parts.extend([record["article_number"], record["article_content"]])
    return " ".join(parts)


def load_model(local_files_only: bool = False) -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME, device="cpu", local_files_only=local_files_only)


def encode_query(model: SentenceTransformer, query: str) -> np.ndarray:
    return model.encode([QUERY_INSTRUCTION + query], normalize_embeddings=True,
                        convert_to_numpy=True, show_progress_bar=False)[0]


def cosine_scores(query_vector: np.ndarray, embeddings: np.ndarray) -> np.ndarray:
    query_vector = query_vector / np.linalg.norm(query_vector)
    matrix = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    return matrix @ query_vector
