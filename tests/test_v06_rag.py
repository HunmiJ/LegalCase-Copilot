from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.rag.citation_validator import validate_citations
from backend.rag.context_builder import build_context
from backend.rag.generator import GroundedGenerator, MockRAGProvider
from backend.rag.pipeline import LegalRAGPipeline, scope_guard
from backend.rag.schemas import RAGSchemaError, validate_response


def context():
    return build_context([{
        "id": "law-a-1", "law_name": "劳动合同法", "article_number": "第一条",
        "chapter": "第一章", "article_content": "为了完善劳动合同制度，明确双方权利和义务。",
        "source_file": "a.docx",
    }])


def valid_response(citation="[1]"):
    return {
        "issue_summary": ["劳动争议问题"],
        "legal_analysis": [{"claim": "该条文提供相关法律依据。", "citations": [citation]}],
        "relevant_laws": [], "missing_information": ["事实仍需补充"],
        "next_steps": ["保存证据"], "disclaimer": "仅供检索参考。",
    }


class V06RAGTest(unittest.TestCase):
    def test_default_context_depth_is_top8_after_real_ab_decision(self):
        pipeline = LegalRAGPipeline(MockRAGProvider())
        self.assertEqual(pipeline.context_top_k, 8)

    def test_context_has_top5_unique_citations_and_required_fields(self):
        built = build_context([{
            "id": str(index), "law_name": "劳动合同法", "article_number": f"第{index}条",
            "article_content": "正文", "source_file": "a.docx"} for index in range(1, 8)], max_articles=5)
        self.assertEqual(built["article_count"], 5)
        self.assertEqual([item["citation_id"] for item in built["items"]], ["[1]", "[2]", "[3]", "[4]", "[5]"])
        self.assertEqual(len({item["canonical_id"] for item in built["items"]}), 5)
        self.assertTrue(all({"law_name", "article_number", "article_content", "source_file", "canonical_id"} <= item.keys() for item in built["items"]))

    def test_valid_citations_pass(self):
        result = validate_citations(valid_response(), context())
        self.assertTrue(result["valid"])
        self.assertEqual(result["unsupported_citation_rate"], 0.0)

    def test_unsupported_and_fabricated_citations_fail(self):
        unsupported = valid_response("[9]")
        self.assertFalse(validate_citations(unsupported, context())["valid"])
        fabricated = valid_response("[1]")
        fabricated["legal_analysis"][0]["claim"] = "劳动合同法第九百九十九条规定了赔偿。"
        self.assertFalse(validate_citations(fabricated, context())["valid"])

    def test_claim_without_citation_is_rejected(self):
        response = valid_response()
        response["legal_analysis"][0]["citations"] = []
        with self.assertRaises(RAGSchemaError):
            validate_response(response)

    def test_law_name_and_article_mismatch_is_rejected(self):
        response = valid_response()
        response["relevant_laws"] = [{"citation": "[1]", "law_name": "劳动法", "article_number": "第一条", "text": "正文"}]
        result = validate_citations(response, context())
        self.assertFalse(result["valid"])
        self.assertTrue(any("law_name mismatch" in error for error in result["errors"]))

    def test_malformed_generation_retries_then_retrieval_only(self):
        class BadProvider:
            def __init__(self): self.calls = 0
            def complete(self, messages, response_format=None, temperature=0):
                self.calls += 1
                return "not-json"

        provider = BadProvider()
        response, meta = GroundedGenerator(provider, max_retries=2).generate("问题", context())
        self.assertEqual(provider.calls, 3)
        self.assertTrue(meta["fallback"])
        self.assertEqual(response["generation_status"], "retrieval_only")

    def test_out_of_domain_mock_does_not_use_labor_law(self):
        response, meta = GroundedGenerator(MockRAGProvider()).generate("我租房押金不退怎么办？", context())
        self.assertFalse(meta["fallback"])
        self.assertEqual(response["legal_analysis"], [])
        self.assertTrue(response["missing_information"])

    def test_insufficient_information_mock_requests_more_facts(self):
        response, _ = GroundedGenerator(MockRAGProvider()).generate("公司对我这样合法吗？", context())
        self.assertTrue(response["missing_information"])
        self.assertEqual(response["legal_analysis"], [])

    def test_scope_guard_rejects_out_of_domain_and_unverifiable_article(self):
        records = [{"article_number": "第一条"}]
        out_of_domain = scope_guard("我租房押金不退怎么办？", records)
        nonexistent = scope_guard("劳动合同法第999条规定了什么？", records)
        self.assertEqual(out_of_domain["generation_status"], "out_of_domain")
        self.assertEqual(nonexistent["generation_status"], "unverifiable_article")

    def test_rag_dataset_has_20_queries_and_frozen_retrieval_is_untouched(self):
        dataset = json.loads((ROOT / "evaluation/rag_queries.json").read_text(encoding="utf-8"))
        self.assertEqual(len(dataset), 20)
        diff = subprocess.run(["git", "diff", "--name-only", "--", "data/raw/laws", "data/processed/legal.db", "data/processed/laws.jsonl", "data/processed/embeddings.npy", "data/processed/embedding_index.json", "evaluation/retrieval_queries.json"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(diff.stdout.strip(), "")

    def test_api_key_not_in_v06_sources(self):
        for directory in (ROOT / "backend/rag", ROOT / "scripts", ROOT / "evaluation", ROOT / "tests"):
            for source in directory.rglob("*.py"):
                self.assertNotIn("sk-" + "test-secret", source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
