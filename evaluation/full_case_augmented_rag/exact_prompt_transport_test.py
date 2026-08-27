"""Send the exact production prompt to the provider without RAG validation."""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.llm import OpenAICompatibleProvider
from backend.rag.pipeline import LegalRAGPipeline
from scripts.hybrid_utils import HybridRetriever
from scripts.reranker_utils import load_reranker

QUERY_FILE = ROOT / "evaluation/full_case_augmented_rag/generation_queries.json"
REPORT_FILE = ROOT / "docs/v1.5.7_exact_prompt_transport_analysis.md"


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class PromptCaptureProvider:
    name = "capture"
    model = "capture"

    def __init__(self):
        self.messages = None

    def complete_with_metadata(self, messages, response_format=None, temperature=0):
        if self.messages is None:
            self.messages = messages
        # Pipeline-only capture response; never sent outside the process.
        return {"content": json.dumps({"issue_summary": ["capture"], "legal_analysis": [],
                                        "missing_information": [], "next_steps": [],
                                        "disclaimer": "capture"}),
                "finish_reason": "stop", "response_structure_type": "str",
                "http_api_success": True}


def _error_kind(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP_{exc.code}", False
    if isinstance(exc, urllib.error.URLError):
        reason = str(exc.reason).lower()
        is_timeout = "timeout" in reason or "timed out" in reason
        if is_timeout:
            return "URLError_timeout", True
        if "10013" in reason or "permission" in reason or "access" in reason:
            return "URLError_socket_permission", False
        return "URLError_network", False
    name = type(exc).__name__
    return name, "timeout" in name.lower()


def _estimate_tokens(text: str) -> int:
    return round(len(text) / 2) if text else 0


def capture_production_messages(query: str, include_cases: bool, retriever, reranker):
    capture = PromptCaptureProvider()
    pipeline = LegalRAGPipeline(capture, retriever=retriever, reranker=reranker,
                                include_cases=include_cases,
                                case_corpus_path=ROOT / "data/processed/full_cases")
    result = pipeline.ask(query)
    if capture.messages is None:
        raise RuntimeError("production pipeline did not produce a prompt")
    context = result.get("context") or {}
    messages = capture.messages
    full_prompt = "".join(str(message.get("content") or "") for message in messages)
    return messages, context, len(full_prompt)


def run_direct(provider, messages: list[dict], query_id: int, mode: str, repeat: int,
               context_chars: int, estimated_tokens: int, prompt_chars: int) -> dict:
    started = time.perf_counter()
    row = {"query_id": query_id, "mode": mode, "repeat": repeat,
           "context_chars": context_chars, "prompt_chars": prompt_chars,
           "estimated_tokens": estimated_tokens, "http_status": None,
           "provider_success": False, "exception_class": None,
           "timeout": False, "latency_ms": None, "response_nonempty": False,
           "response_chars": None}
    try:
        outcome = provider.complete_with_metadata(messages, {"type": "json_object"}, 0)
        content = outcome.get("content")
        row["http_status"] = 200 if outcome.get("http_api_success") else None
        row["provider_success"] = bool(outcome.get("http_api_success")) and bool(content)
        row["response_nonempty"] = bool(content)
        row["response_chars"] = len(str(content)) if content else 0
    except Exception as exc:
        row["exception_class"], row["timeout"] = _error_kind(exc)
    finally:
        row["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return row


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, int(0.95 * len(ordered) + 0.999999) - 1)], 2)


def main() -> None:
    load_dotenv()
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))[:5]
    provider = OpenAICompatibleProvider()
    retriever = HybridRetriever()
    reranker = load_reranker(local_files_only=True)
    records = []
    for query_id, item in enumerate(queries, 1):
        for mode, include_cases in (("law-only", False), ("law+6492-cases", True)):
            messages, context, prompt_chars = capture_production_messages(item["query"], include_cases, retriever, reranker)
            context_chars = len(context.get("context_text", ""))
            estimated_tokens = _estimate_tokens("".join(str(m.get("content") or "") for m in messages))
            for repeat in range(1, 4):
                records.append(run_direct(provider, messages, query_id, mode, repeat,
                                           context_chars, estimated_tokens, prompt_chars))
    latencies = [r["latency_ms"] for r in records]
    successes = [r for r in records if r["provider_success"]]
    failures = [r for r in records if not r["provider_success"]]
    error_counts = {}
    for row in failures:
        kind = row["exception_class"] or "unsuccessful_response"
        error_counts[kind] = error_counts.get(kind, 0) + 1
    by_mode = {}
    for mode in ("law-only", "law+6492-cases"):
        rows = [r for r in records if r["mode"] == mode]
        mode_latencies = [r["latency_ms"] for r in rows]
        by_mode[mode] = {"calls": len(rows), "success": sum(r["provider_success"] for r in rows),
                         "success_rate": sum(r["provider_success"] for r in rows) / len(rows),
                         "average_latency_ms": round(statistics.mean(mode_latencies), 2),
                         "p95_latency_ms": p95(mode_latencies),
                         "timeouts": sum(r["timeout"] for r in rows)}
    report = f"""# V1.5.7 Exact-Prompt Transport Analysis

## Test method

- 5 fixed queries × 2 modes × 3 repeats = {len(records)} direct provider calls.
- Each message was first captured from the production pipeline in memory, then sent directly to DeepSeek without JSON parser, schema validator, citation validator, or retry feedback.
- No complete prompt, context, response body, API Key, Authorization, Cookie or token was saved.
- `estimated_tokens` is a rough character/2 estimate.

## Provider configuration (read-only)

- HTTP client: Python standard library `urllib.request`.
- `connect timeout` / `read timeout` / `total timeout`: provider exposes one `LEGALCASE_LLM_TIMEOUT` value and passes it as `urlopen(timeout=...)`; separate connect/read/total values are not configured.
- Provider retry/backoff: none.
- RAG generator retry count: 2 retries after the first attempt; this direct test does not use those retries.
- max output tokens: not set in the provider payload.
- temperature: 0.
- streaming: not used.

## Summary

- Total provider success: {len(successes)}/{len(records)} ({len(successes) / len(records):.4f})
- Average latency: {round(statistics.mean(latencies), 2) if latencies else '—'} ms
- P95 latency: {p95(latencies) if latencies else '—'} ms
- Transport/provider failures: {len(failures)}
- Exception distribution: `{json.dumps(error_counts, ensure_ascii=False)}`

| mode | calls | success | success rate | avg latency ms | P95 latency ms | timeouts |
|---|---:|---:|---:|---:|---:|---:|
""" + "\n".join(f"| {mode} | {value['calls']} | {value['success']} | {value['success_rate']:.4f} | {value['average_latency_ms']} | {value['p95_latency_ms']} | {value['timeouts']} |" for mode, value in by_mode.items()) + """

## Per-call safe metadata

| query id | mode | repeat | context chars | prompt chars | est. tokens | HTTP | success | exception | timeout | latency ms | response nonempty | response chars |
|---:|---|---:|---:|---:|---:|---:|---|---|---|---:|---|---:|
""" + "\n".join(f"| {r['query_id']} | {r['mode']} | {r['repeat']} | {r['context_chars']} | {r['prompt_chars']} | {r['estimated_tokens']} | {r['http_status'] or '—'} | {r['provider_success']} | {r['exception_class'] or '—'} | {r['timeout']} | {r['latency_ms']} | {r['response_nonempty']} | {r['response_chars'] if r['response_chars'] is not None else '—'} |" for r in records) + """

## Interpretation

If exact production prompts succeed at ≥90%, provider/transport is unlikely to be the primary cause of `generation_failed_after_retries`; the next focus should be model output contract and citation compliance. If success is lower, compare failures against prompt/context length and timeout distribution before changing timeout values. This test itself does not change timeout or retry settings.

No full 30-query RAG evaluation was run.
"""
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(json.dumps({"calls": len(records), "success": len(successes), "failure": len(failures),
                      "success_rate": len(successes) / len(records), "average_latency_ms": round(statistics.mean(latencies), 2),
                      "p95_latency_ms": p95(latencies), "error_distribution": error_counts,
                      "by_mode": by_mode}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
