"""Search the law database using FTS5, with a safe LIKE fallback for short Chinese terms."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def search(database: Path, query: str, limit: int = 10) -> list[sqlite3.Row]:
    connection = sqlite3.connect(database)
    try:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""SELECT l.* FROM laws l
            JOIN laws_fts f ON f.rowid = l.rowid
            WHERE laws_fts MATCH ? LIMIT ?""", (query, limit)).fetchall()
        if not rows:
            like = f"%{query}%"
            rows = connection.execute("""SELECT * FROM laws
                WHERE law_name LIKE ? OR article_number LIKE ? OR article_content LIKE ?
                LIMIT ?""", (like, like, like, limit)).fetchall()
        return rows
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="搜索劳动争议法律条文")
    parser.add_argument("query")
    parser.add_argument("--database", default=str(ROOT / "data/processed/legal.db"))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    rows = search(Path(args.database), args.query, args.limit)
    print(f"查询：{args.query}")
    for index, row in enumerate(rows, 1):
        print(f"\n[{index}]\n{row['law_name']}\n{row['article_number']}\n正文：{row['article_content']}\n来源文件：{row['source_file']}")
    if not rows:
        print("未找到匹配条文")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
