from __future__ import annotations

import unittest

import numpy as np

from .case_retriever import RuntimeCaseRetriever


class FakeEmbeddingModel:
    def encode(self, sentences, **kwargs):
        return np.asarray([[float((sum(map(ord, sentence)) + i) % 17) for i in range(4)] for sentence in sentences], dtype=np.float32)


def records():
    return [
        {"case_id": "labor-1", "title": "确认劳动关系案", "dispute_focus": "确认劳动关系", "keywords": ["劳动关系"], "basic_facts": "劳动者主张确认劳动关系", "judgment_result": "确认存在劳动关系", "source_name": "人民法院案例库", "source_file": "runtime/a.pdf", "raw_text": "文本"},
        {"case_id": "labor-2", "title": "违法解除劳动合同案", "dispute_focus": "违法解除", "keywords": ["解除", "赔偿金"], "basic_facts": "公司解除劳动合同", "judgment_result": "解除违法", "source_name": "人民法院案例库", "source_file": "runtime/b.pdf", "raw_text": "文本"},
        {"case_id": "labor-3", "title": "加班费认定案", "dispute_focus": "加班费", "keywords": ["加班费"], "basic_facts": "劳动者主张加班", "judgment_result": "支持部分加班费", "source_name": "人民法院案例库", "source_file": "runtime/c.pdf", "raw_text": "文本"},
        {"case_id": "labor-4", "title": "竞业限制案", "dispute_focus": "竞业限制", "keywords": ["竞业限制"], "basic_facts": "离职后竞业争议", "judgment_result": "支付竞业补偿", "source_name": "人民法院案例库", "source_file": "runtime/d.pdf", "raw_text": "文本"},
    ]


class RuntimeCaseRetrievalTest(unittest.TestCase):
    def setUp(self):
        self.retriever = RuntimeCaseRetriever(records=records(), model=FakeEmbeddingModel())

    def test_keyword_queries_return_expected_cases(self):
        for query, expected in (("确认劳动关系", "labor-1"), ("违法解除", "labor-2"), ("加班认定", "labor-3"), ("竞业限制", "labor-4")):
            result = self.retriever.search(query, 1, "keyword")[0]
            self.assertEqual(result["case_id"], expected)
            self.assertIn("score", result)

    def test_semantic_and_hybrid_result_schema(self):
        for mode in ("semantic", "hybrid"):
            result = self.retriever.search("劳动合同争议", 2, mode)
            self.assertEqual(len(result), 2)
            self.assertTrue({"case_id", "title", "dispute_focus", "judgment_result", "score"}.issubset(result[0]))


if __name__ == "__main__":
    unittest.main()
