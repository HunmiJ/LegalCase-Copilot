"""Isolated real-generation diagnostics with a fixed legal context."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import OpenAICompatibleProvider
from backend.rag.context_builder import build_context
from backend.rag.generator import GroundedGenerator
from hybrid_utils import HybridRetriever


def load_dotenv():
    for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"LEGALCASE_LLM_BASE_URL", "LEGALCASE_LLM_API_KEY", "LEGALCASE_LLM_MODEL"}:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def main():
    load_dotenv()
    provider = OpenAICompatibleProvider()
    retriever = HybridRetriever()
    wanted = {"第四十七条", "第四十八条", "第三十一条", "第八十七条"}
    selected = [record for record in retriever.records
                if record.get("article_number") in wanted and "劳动合同法" in record.get("law_name", "")]
    if len(selected) < 2:
        selected = [record for record in retriever.records if record.get("article_number") in {"第四十七条", "第四十八条"}]
    context = build_context(selected, max_articles=5)
    generator = GroundedGenerator(provider, max_retries=2)
    queries = [
        "公司工作两年突然辞退我，没有提前通知，也不给补偿怎么办？",
        "公司工作两年突然辞退我，没有提前通知，也不给补偿怎么办？",
        "公司一直让我加班但是不给加班费怎么办？",
    ]
    rows = []
    for query in queries:
        start = time.perf_counter()
        response, meta = generator.generate(query, context)
        rows.append({"query": query, "context": context, "response": response,
                     "generation_meta": meta, "wall_clock_ms": (time.perf_counter() - start) * 1000})
        print("DIAGNOSTIC completed", meta.get("retry_count"), meta.get("fallback"))
    output = ROOT / "evaluation/results/v0.6_generation_diagnostics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"model": provider.model, "fixed_context_article_count": context["article_count"], "runs": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
