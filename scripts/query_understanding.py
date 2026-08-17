"""Public query-understanding API and CLI for V0.5."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.llm import MockProvider, OpenAICompatibleProvider, QueryUnderstandingService

ROOT = Path(__file__).resolve().parents[1]


def create_provider(kind: str | None = None):
    kind = (kind or os.getenv("LEGALCASE_LLM_PROVIDER", "mock")).lower()
    if kind == "mock":
        return MockProvider()
    if kind in ("real", "openai", "openai_compatible"):
        return OpenAICompatibleProvider()
    raise ValueError(f"unsupported provider: {kind}")


def understand_query(query: str, provider_kind: str | None = None, cache_path: Path | None = None) -> dict:
    provider = create_provider(provider_kind)
    cache_path = cache_path if cache_path is not None else ROOT / ".cache/query_understanding.json"
    return QueryUnderstandingService(provider, cache_path=cache_path).understand(query)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--provider", choices=("mock", "real"), default=None)
    args = parser.parse_args()
    print(json.dumps(understand_query(args.query, args.provider), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
