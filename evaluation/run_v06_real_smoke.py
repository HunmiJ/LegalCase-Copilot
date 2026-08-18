"""Run the four explicitly requested V0.6 real-provider smoke tests."""

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
from backend.rag import LegalRAGPipeline


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        raise RuntimeError("root .env is missing")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in {"LEGALCASE_LLM_BASE_URL", "LEGALCASE_LLM_API_KEY", "LEGALCASE_LLM_MODEL"}:
            os.environ[key] = value.strip().strip('"').strip("'")
    for key in ("LEGALCASE_LLM_BASE_URL", "LEGALCASE_LLM_API_KEY", "LEGALCASE_LLM_MODEL"):
        if not os.environ.get(key):
            raise RuntimeError("missing required real provider configuration")


def main() -> int:
    load_dotenv()
    provider = OpenAICompatibleProvider()
    pipeline = LegalRAGPipeline(provider)
    queries = [
        {"smoke_id": "s01", "query": "公司工作两年突然把我辞退了，没有提前通知，也不给补偿怎么办？"},
        {"smoke_id": "s02", "query": "公司一直让我加班但是不给加班费怎么办？"},
        {"smoke_id": "s03", "query": "我租房押金不退怎么办？"},
        {"smoke_id": "s04", "query": "劳动合同法第999条规定了什么？"},
    ]
    rows = []
    for item in queries:
        start = time.perf_counter()
        try:
            result = pipeline.ask(item["query"])
            rows.append({"smoke_id": item["smoke_id"], "query": item["query"],
                         "model": provider.model, "status": "success", "result": result,
                         "wall_clock_ms": (time.perf_counter() - start) * 1000})
            print(f"SMOKE {item['smoke_id']} success")
        except Exception:
            # Do not expose provider exception text; the result remains auditable as failed.
            rows.append({"smoke_id": item["smoke_id"], "query": item["query"],
                         "model": provider.model, "status": "failed", "error_type": "provider_or_pipeline_error",
                         "wall_clock_ms": (time.perf_counter() - start) * 1000})
            print(f"SMOKE {item['smoke_id']} failed")
    output = ROOT / "evaluation/results/v0.6_real_smoke_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"provider": "real_llm", "model": provider.model, "smoke_tests": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {output}")
    return 0 if all(row["status"] == "success" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
