"""Validated, cached query-understanding service with safe fallback."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .provider import LLMProvider
from .schema import SchemaValidationError, parse_and_validate


class QueryUnderstandingService:
    def __init__(self, provider: LLMProvider, cache_path: Path | None = None, max_retries: int = 2):
        self.provider = provider
        self.cache_path = cache_path
        self.max_retries = max(0, max_retries)
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        if not self.cache_path or not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_cache(self) -> None:
        if not self.cache_path:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def fallback(original_query: str, reason: str) -> dict:
        return {
            "original_query": original_query,
            "domain": "劳动争议",
            "issue": "劳动争议法律检索",
            "user_intent": "查找适用的劳动争议法律规则",
            "legal_concepts": [],
            "search_queries": [original_query],
            "provider_status": "fallback",
            "fallback_reason": reason[:200],
        }

    def understand(self, original_query: str) -> dict:
        cached = self._cache.get(original_query)
        if cached and cached.get("model") == self.provider.model:
            result = dict(cached["structured_result"])
            result["cache_hit"] = True
            return result
        last_error = "unknown error"
        for _ in range(self.max_retries + 1):
            try:
                result = parse_and_validate(self.provider.generate(original_query), original_query)
                result.update({"provider_status": self.provider.name, "cache_hit": False})
                self._cache[original_query] = {
                    "query": original_query,
                    "model": self.provider.model,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "structured_result": result,
                }
                self._save_cache()
                return result
            except (SchemaValidationError, OSError, ValueError, KeyError) as exc:
                last_error = str(exc)
        return self.fallback(original_query, last_error)
