import json
import sqlite3
import sys
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_database import build_database
from parse_laws import inspect_file, parse_articles, load_metadata
from search_laws import search


class LawsPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.laws_dir = ROOT / "data/raw/laws"
        cls.metadata = load_metadata(ROOT / "data/law_metadata.json")
        cls.jsonl = ROOT / "data/processed/laws.jsonl"
        cls.database = ROOT / "data/processed/legal.db"

    def test_six_docx_are_readable_and_have_articles(self):
        files = sorted(self.laws_dir.glob("*.docx"))
        self.assertEqual(len(files), 6)
        for path in files:
            inspection = inspect_file(path)
            self.assertTrue(inspection["readable"], inspection)
            self.assertGreater(inspection["paragraphs"], 0)
            self.assertGreater(inspection["articles"], 0)

    def test_articles_are_nonempty_and_have_numbers(self):
        total = 0
        for path in sorted(self.laws_dir.glob("*.docx")):
            records = parse_articles(path, self.metadata[path.relative_to(ROOT).as_posix()])
            total += len(records)
            self.assertTrue(records)
            for record in records:
                self.assertTrue(record["article_number"])
                self.assertTrue(record["article_content"])
        self.assertGreater(total, 0)

    def test_jsonl_and_database_have_real_source_files(self):
        records = [json.loads(line) for line in self.jsonl.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(records)
        parsed_by_key = {}
        for path in sorted(self.laws_dir.glob("*.docx")):
            metadata = self.metadata[path.relative_to(ROOT).as_posix()]
            for parsed in parse_articles(path, metadata):
                parsed_by_key[(parsed["source_file"], parsed["article_number"])] = parsed["article_content"]
        for record in records:
            source = ROOT / record["source_file"]
            self.assertTrue(source.is_file())
            self.assertEqual(record["article_content"], parsed_by_key[(record["source_file"], record["article_number"])])

    def test_database_and_fts_search(self):
        with TemporaryDirectory() as temporary:
            temporary_database = Path(temporary) / "legal_test.db"
            build_database(self.jsonl, temporary_database)
            connection = sqlite3.connect(temporary_database)
            try:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM laws").fetchone()[0],
                                 len(self.jsonl.read_text(encoding="utf-8").splitlines()))
                self.assertTrue(connection.execute("SELECT 1 FROM sqlite_master WHERE name='laws_fts'").fetchone())
            finally:
                connection.close()
            self.assertTrue(search(temporary_database, "劳动合同"))
            self.assertTrue(search(temporary_database, "经济补偿"))


if __name__ == "__main__":
    unittest.main()
