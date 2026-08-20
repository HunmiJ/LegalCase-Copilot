"""Build local BGE embeddings for the curated case corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.cases.search.semantic import case_embedding_text
from scripts.semantic_utils import load_model


def build_case_embeddings(input_path: Path, output_path: Path, index_path: Path, model=None) -> tuple[int, int]:
    records = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise ValueError("case corpus is empty")
    records = sorted(records, key=lambda record: record["case_id"])
    if len({record["case_id"] for record in records}) != len(records):
        raise ValueError("case_id values must be unique")
    model = model or load_model(local_files_only=True)
    embeddings = model.encode([case_embedding_text(record) for record in records], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True)
    if len(embeddings) != len(records) or not np.isfinite(embeddings).all():
        raise RuntimeError("invalid case embedding output")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, embeddings.astype(np.float32))
    index = [{"position": position, "case_id": record["case_id"], "title": record["title"], "source_file": record["source_file"]} for position, record in enumerate(records)]
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(records), int(embeddings.shape[1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "data/processed/cases/cases.jsonl"))
    parser.add_argument("--output", default=str(ROOT / "data/processed/cases/case_embeddings.npy"))
    parser.add_argument("--index", default=str(ROOT / "data/processed/cases/case_embedding_index.json"))
    args = parser.parse_args()
    count, dimension = build_case_embeddings(Path(args.input), Path(args.output), Path(args.index))
    print(f"case_embeddings={count}, dimension={dimension}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
