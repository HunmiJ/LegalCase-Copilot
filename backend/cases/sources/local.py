"""Working Local provider backed by the curated three-case JSONL corpus."""

from __future__ import annotations

from pathlib import Path

from ..corpus_config import resolve_case_corpus
from ..search.bm25 import CaseBM25Index
from ..search.models import CaseSearchResult
from .base import CaseSourceSearchRequest


class LocalCuratedCaseProvider:
    name = "curated_local_case_corpus"
    search_available = True
    provider_status = "available"

    def __init__(self, corpus_path: Path | None = None) -> None:
        self.corpus_path = resolve_case_corpus(corpus_path).corpus_path
        self.index = CaseBM25Index.from_jsonl(self.corpus_path)

    def search(self, request: CaseSourceSearchRequest | str, top_k: int = 10) -> list[CaseSearchResult]:
        if isinstance(request, str):
            query, limit = request, top_k
        else:
            query, limit = request.query, request.limit
        return self.index.search(query, limit)
