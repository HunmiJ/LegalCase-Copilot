"""Chinese tokenization and BM25 retrieval helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Tokenize Chinese text and remove whitespace/punctuation-only pieces."""
    tokens = []
    for token in jieba.lcut(text, cut_all=False):
        tokens.extend(TOKEN_RE.findall(token))
    return tokens


def retrieval_text(record: dict) -> str:
    return " ".join(filter(None, [record.get("law_name"), record.get("chapter"),
                                  record.get("article_number"), record.get("article_content")]))


def load_records(path: Path | None = None) -> list[dict]:
    path = path or ROOT / "data/processed/laws.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class BM25Retriever:
    def __init__(self, records: list[dict]):
        self.records = records
        self.tokenized_corpus = [tokenize(retrieval_text(record)) for record in records]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        query_tokens = tokenize(query)
        scores = self.bm25.get_scores(query_tokens)
        positions = sorted(range(len(scores)), key=lambda pos: (-scores[pos], pos))[:limit]
        results = []
        for rank, position in enumerate(positions, 1):
            result = dict(self.records[position])
            result["bm25_score"] = float(scores[position])
            result["rank"] = rank
            results.append(result)
        return results
