"""Build the SQLite law database and FTS5 index from laws.jsonl."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["id", "law_name", "article_number", "article_content", "chapter",
          "document_type", "issuing_authority", "publish_date", "effective_date",
          "status", "source_name", "source_url", "source_file"]


def build_database(input_path: Path, database_path: Path) -> int:
    records = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("DROP TABLE IF EXISTS laws_fts")
        connection.execute("DROP TABLE IF EXISTS laws")
        connection.execute("""CREATE TABLE laws (
            id TEXT PRIMARY KEY, law_name TEXT NOT NULL, article_number TEXT NOT NULL,
            article_content TEXT NOT NULL, chapter TEXT, document_type TEXT,
            issuing_authority TEXT, publish_date TEXT, effective_date TEXT, status TEXT,
            source_name TEXT, source_url TEXT, source_file TEXT NOT NULL
        )""")
        placeholders = ",".join("?" for _ in FIELDS)
        connection.executemany(f"INSERT INTO laws ({','.join(FIELDS)}) VALUES ({placeholders})",
                               [tuple(record.get(field) for field in FIELDS) for record in records])
        connection.execute("""CREATE VIRTUAL TABLE laws_fts USING fts5(
            law_name, article_number, article_content, content='laws', content_rowid='rowid',
            tokenize='trigram'
        )""")
        connection.execute("INSERT INTO laws_fts(laws_fts) VALUES('rebuild')")
        connection.execute("CREATE INDEX idx_laws_law_name ON laws(law_name)")
        connection.commit()
    finally:
        connection.close()
    print(f"已建立数据库 {database_path}，写入 {len(records)} 条条文")
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "data/processed/laws.jsonl"))
    parser.add_argument("--database", default=str(ROOT / "data/processed/legal.db"))
    args = parser.parse_args()
    build_database(Path(args.input), Path(args.database))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
