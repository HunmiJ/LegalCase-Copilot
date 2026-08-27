"""Shared corpus path configuration for local case providers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_DIR = ROOT / "data" / "processed" / "cases"


@dataclass(frozen=True)
class CaseCorpusConfig:
    """Resolve all local artifacts from one corpus directory."""

    directory: Path

    @classmethod
    def from_env(cls, corpus_path: Path | str | None = None) -> "CaseCorpusConfig":
        configured = corpus_path or os.getenv("CASE_CORPUS_PATH")
        path = Path(configured) if configured else DEFAULT_CORPUS_DIR
        if not path.is_absolute():
            path = ROOT / path
        if path.suffix.lower() == ".jsonl":
            path = path.parent
        return cls(path.resolve())

    @property
    def corpus_path(self) -> Path:
        return self.directory / "cases.jsonl"

    @property
    def embeddings_path(self) -> Path:
        return self.directory / "case_embeddings.npy"

    @property
    def index_path(self) -> Path:
        return self.directory / "case_embedding_index.json"


def resolve_case_corpus(corpus_path: Path | str | None = None) -> CaseCorpusConfig:
    return CaseCorpusConfig.from_env(corpus_path)
