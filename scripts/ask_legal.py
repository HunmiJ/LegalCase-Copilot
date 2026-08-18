"""CLI for V0.6 grounded legal RAG using the default V0.4 retrieval path."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import OpenAICompatibleProvider
from backend.rag import LegalRAGPipeline, MockRAGProvider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--provider", choices=("real", "mock"), default="real")
    args = parser.parse_args()
    provider = OpenAICompatibleProvider() if args.provider == "real" else MockRAGProvider()
    result = LegalRAGPipeline(provider).ask(args.query)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
