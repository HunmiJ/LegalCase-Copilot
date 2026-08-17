"""Generate BGE embeddings for every article in laws.jsonl."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from semantic_utils import ROOT, embedding_text, load_model, load_records


def build_embeddings(input_path: Path, output_path: Path, index_path: Path) -> tuple[int, int]:
    records = load_records(input_path)
    if not records:
        raise ValueError("laws.jsonl is empty")
    model = load_model()
    texts = [embedding_text(record) for record in records]
    embeddings = model.encode(texts, batch_size=16, normalize_embeddings=True,
                              convert_to_numpy=True, show_progress_bar=True)
    if len(embeddings) != len(records):
        raise RuntimeError("embedding count does not match laws.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, embeddings.astype(np.float32))
    index = []
    for position, record in enumerate(records):
        index.append({"position": position, "id": record["id"],
                      "law_name": record["law_name"],
                      "article_number": record["article_number"],
                      "source_file": record["source_file"]})
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(records), int(embeddings.shape[1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "data/processed/laws.jsonl"))
    parser.add_argument("--output", default=str(ROOT / "data/processed/embeddings.npy"))
    parser.add_argument("--index", default=str(ROOT / "data/processed/embedding_index.json"))
    args = parser.parse_args()
    count, dimension = build_embeddings(Path(args.input), Path(args.output), Path(args.index))
    print(f"已生成 {count} 条 embedding，维度 {dimension}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
