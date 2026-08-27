"""Minimal DeepSeek provider/network stability probe.

This script intentionally does not import or load any project corpus, RAG,
retrieval, embedding, reranker, or citation code. It sends only a fixed,
non-sensitive JSON prompt and stores status metadata, never response bodies or
credentials.
"""

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

from backend.llm import OpenAICompatibleProvider

REPORT = ROOT / "docs/v1.5.4_provider_stability_report.md"
CALLS = 20
PROMPT = '请只返回 JSON：{"status":"ok"}'


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, int(0.95 * len(ordered) + 0.999999) - 1)
    return round(ordered[rank], 2)


def _error_kind(exc: Exception) -> str:
    if isinstance(exc, TimeoutError) or isinstance(exc, TimeoutError):
        return "TimeoutError"
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTPError_{exc.code}"
    if isinstance(exc, urllib.error.URLError):
        reason = str(exc.reason).lower()
        if "timed out" in reason or "timeout" in reason:
            return "URLError_timeout"
        if "10013" in reason or "permission" in reason or "access" in reason:
            return "URLError_socket_permission"
        return "URLError_network"
    return type(exc).__name__


def main() -> None:
    _load_dotenv()
    started = time.perf_counter()
    records = []
    try:
        provider = OpenAICompatibleProvider()
    except Exception as exc:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(
            "# V1.5.4 Provider Stability Report\n\n"
            "Provider initialization failed before any request was sent.\n\n"
            f"- exception_type: `{_error_kind(exc)}`\n"
            "- API Key/Authorization/response body: not recorded\n",
            encoding="utf-8",
        )
        raise

    for index in range(1, CALLS + 1):
        call_start = time.perf_counter()
        record = {"call": index, "success": False, "http_status": None,
                  "exception_type": None, "timeout": False,
                  "latency_ms": None, "valid_json": False}
        try:
            result = provider.complete_with_metadata(
                [{"role": "user", "content": PROMPT}],
                {"type": "json_object"}, 0,
            )
            content = result.get("content")
            record["success"] = bool(result.get("http_api_success")) and bool(content)
            record["http_status"] = 200 if result.get("http_api_success") else None
            if content:
                try:
                    parsed = json.loads(str(content).strip())
                    record["valid_json"] = isinstance(parsed, dict)
                except (TypeError, json.JSONDecodeError):
                    record["valid_json"] = False
        except Exception as exc:
            record["exception_type"] = _error_kind(exc)
            record["timeout"] = "timeout" in record["exception_type"].lower()
            if isinstance(exc, urllib.error.HTTPError):
                record["http_status"] = exc.code
        finally:
            record["latency_ms"] = round((time.perf_counter() - call_start) * 1000, 2)
            records.append(record)

    success = [record for record in records if record["success"]]
    latencies = [record["latency_ms"] for record in records if record["latency_ms"] is not None]
    failures = [record for record in records if not record["success"]]
    error_counts: dict[str, int] = {}
    for record in failures:
        kind = record["exception_type"] or "provider_unsuccessful_response"
        error_counts[kind] = error_counts.get(kind, 0) + 1
    valid_json_count = sum(record["valid_json"] for record in records)
    report = f"""# V1.5.4 Provider Stability Report

## Test scope

- Calls: {CALLS}
- Prompt: fixed short non-sensitive JSON request; no law, case, RAG, retrieval, embedding, reranker, or citation context loaded.
- Provider: `{provider.name}`
- Model: `{provider.model}`
- Total wall time: {round(time.perf_counter() - started, 2)} seconds
- API Key, Authorization, cookies, tokens and full response bodies: not recorded.

## Summary

- Success: {len(success)}/{CALLS}
- Success rate: {len(success) / CALLS:.4f}
- Provider/transport failures: {len(failures)}
- Valid JSON responses: {valid_json_count}/{CALLS}
- Average latency: {round(statistics.mean(latencies), 2) if latencies else '—'} ms
- P95 latency: {_p95(latencies) if latencies else '—'} ms

## Exception distribution

| exception/status | count |
|---|---:|
""" + "\n".join(f"| `{kind}` | {count} |" for kind, count in sorted(error_counts.items())) + f"""

## Per-call safe metadata

| call | success | HTTP status | exception type | timeout | latency (ms) | valid JSON |
|---:|---|---:|---|---|---:|---|
""" + "\n".join(
        f"| {r['call']} | {r['success']} | {r['http_status'] or '—'} | {r['exception_type'] or '—'} | {r['timeout']} | {r['latency_ms']} | {r['valid_json']} |"
        for r in records
    ) + "\n"
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    print(json.dumps({"calls": CALLS, "success": len(success),
                      "failure": len(failures), "valid_json": valid_json_count,
                      "average_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
                      "p95_latency_ms": _p95(latencies),
                      "exception_distribution": error_counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
