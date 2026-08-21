"""Initialize and inspect the isolated V0.7.8 runtime corpus workspace."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.cases.runtime_builder import RuntimePaths, write_collection_plan, write_stats


def main() -> int:
    root = ROOT / "data/runtime/cases"
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=root)
    args = parser.parse_args()
    paths = RuntimePaths(args.root)
    paths.raw.mkdir(parents=True, exist_ok=True)
    paths.processed.mkdir(parents=True, exist_ok=True)
    if not paths.plan.exists(): write_collection_plan(paths)
    stats = write_stats(paths)
    print(f"runtime_root={paths.root}")
    print(f"main={stats['current']['main']} target={stats['target_main_cases']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
