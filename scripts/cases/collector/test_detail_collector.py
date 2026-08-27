import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.cases.collector.detail_collector import (
    OFFICIAL_DOMAIN,
    probe_fields,
    validate_source_url,
)


class DetailCollectorTests(unittest.TestCase):
    def test_url_domain_validation(self):
        self.assertEqual(
            validate_source_url("https://rmfyalk.court.gov.cn/view/content.html?id=1"),
            "https://rmfyalk.court.gov.cn/view/content.html?id=1",
        )
        with self.assertRaises(ValueError):
            validate_source_url("https://example.com/case")

    def test_output_json_is_readable(self):
        record = {
            "source_url": f"https://{OFFICIAL_DOMAIN}/view/content.html?id=1",
            "title": "测试案例",
            "case_number": "",
            "court": "",
            "judgment_date": "",
            "case_type": "",
            "raw_text": "测试正文",
            "pdf_url": "",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "smoke_test_case.json"
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["source_url"].split("/")[2], OFFICIAL_DOMAIN)

    def test_missing_fields_are_empty_not_fatal(self):
        fields = probe_fields("首页", "人民法院案例库\n正文", [])
        self.assertEqual(fields["title"], "")
        self.assertEqual(fields["case_number"], "")
        self.assertEqual(fields["court"], "")
        self.assertEqual(fields["pdf_url"], "")
        self.assertEqual(fields["raw_text"], "人民法院案例库\n正文")


if __name__ == "__main__":
    unittest.main()
