import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.cases.discovery.discovery import (
    DEFAULT_CONFIG,
    RESULT_LIST_SELECTOR,
    SEARCH_BUTTON_SELECTOR,
    SEARCH_INPUT_SELECTOR,
    clean_title,
    deduplicate_candidates,
    load_config,
    make_candidate,
    normalize_url,
    validate_candidate,
    validate_official_url,
    write_candidates,
)


class DiscoveryTests(unittest.TestCase):
    def test_candidate_schema_supports_both_statuses(self):
        schema = json.loads(Path(__file__).with_name("discovery_candidates.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["items"]["properties"]["status"]["enum"], ["candidate", "discovered"])

    def test_title_cleaning_removes_em_markup(self):
        title = clean_title("某公司<em>确认</em><em>劳动关系</em>案")
        self.assertEqual(title, "某公司确认劳动关系案")
        self.assertNotIn("<em>", title)

    def test_search_selectors(self):
        self.assertEqual(SEARCH_INPUT_SELECTOR, "input.keyword")
        self.assertEqual(SEARCH_BUTTON_SELECTOR, "button.general-search-submit")
        self.assertEqual(RESULT_LIST_SELECTOR, ".al-list")

    def test_config_reading(self):
        config = load_config(DEFAULT_CONFIG)
        self.assertEqual(config["max_pages_per_keyword"], 5)
        self.assertIn("违法解除劳动合同", config["keywords"])

    def test_url_normalization_and_validation(self):
        url = normalize_url("/view/content.html?id=abc")
        self.assertTrue(url.startswith("https://rmfyalk.court.gov.cn/"))
        self.assertEqual(validate_official_url(url), url)
        with self.assertRaises(ValueError):
            validate_official_url("https://example.com/case")

    def test_duplicate_url_keeps_first_record(self):
        first = make_candidate("/view/content.html?id=one", "第一条", "劳动关系", 1, "t1")
        second = make_candidate("https://rmfyalk.court.gov.cn/view/content.html?id=one", "第二条", "劳动关系", 2, "t2")
        unique = deduplicate_candidates([first, second])
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0]["title"], "第一条")
        self.assertEqual(unique[0]["page"], 1)

    def test_schema_shape_validation(self):
        candidate = make_candidate("/view/content.html?id=schema", "测试案例", "工伤待遇", 1, "t")
        validate_candidate(candidate)
        invalid = dict(candidate)
        invalid["status"] = "downloaded"
        with self.assertRaises(ValueError):
            validate_candidate(invalid)

    def test_json_output_deduplicates(self):
        candidates = [make_candidate("/view/content.html?id=out", "输出案例", "加班工资", 1, "t")]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "discovery_candidates.json"
            written = write_candidates(output, candidates + candidates)
            self.assertEqual(len(written), 1)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))[0]["status"], "candidate")


if __name__ == "__main__":
    unittest.main()
