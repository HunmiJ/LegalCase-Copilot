from __future__ import annotations

import unittest

from collector import extract_case_title_from_dom


class FakeLocator:
    def __init__(self, body: str, headings: list[str] | None = None):
        self.body = body
        self.headings = headings or []

    def inner_text(self, timeout: int) -> str:
        return self.body

class FakePage:
    def __init__(self, body: str, headings: list[str] | None = None):
        self.body_locator = FakeLocator(body, headings)

    def locator(self, selector: str) -> FakeLocator:
        return self.body_locator


class CollectorTitleTest(unittest.TestCase):
    def test_extracts_title_after_official_database_id(self):
        page = FakePage("首页\n正文\n入库编号\n2023-16-2-490-001\n廖某诉某劳务派遣公司确认劳动关系纠纷案\n——确认劳动关系纠纷中的举证责任分配")
        self.assertEqual(extract_case_title_from_dom(page), "廖某诉某劳务派遣公司确认劳动关系纠纷案")

    def test_ignores_ui_title_elements_and_requires_official_database_id(self):
        page = FakePage("请勾选\n已经勾选\n其他 title 元素\n首页\n正文")
        self.assertIsNone(extract_case_title_from_dom(page))

    def test_uses_only_title_after_official_database_id(self):
        page = FakePage("请勾选\n2023-16-2-490-001\n真实劳动争议案\n其他 title 元素")
        self.assertEqual(extract_case_title_from_dom(page), "真实劳动争议案")


if __name__ == "__main__":
    unittest.main()
