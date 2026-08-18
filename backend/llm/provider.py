"""Provider abstraction for structured legal query understanding.

The real provider uses an OpenAI-compatible chat-completions endpoint through
the Python standard library. API secrets are read only from environment
variables and are never included in returned records or logs.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(self, original_query: str) -> str:
        """Return a JSON string containing the structured understanding."""


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str | None
    api_key: str | None
    model: str
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        return cls(
            base_url=os.getenv("LEGALCASE_LLM_BASE_URL") or os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LEGALCASE_LLM_API_KEY") or os.getenv("LLM_API_KEY"),
            model=os.getenv("LEGALCASE_LLM_MODEL") or os.getenv("LLM_MODEL") or "configured-model",
            timeout_seconds=float(os.getenv("LEGALCASE_LLM_TIMEOUT", "30")),
        )


class OpenAICompatibleProvider:
    name = "real_llm"

    def __init__(self, config: ProviderConfig | None = None):
        self.config = config or ProviderConfig.from_env()
        self.model = self.config.model
        if not self.config.base_url or not self.config.api_key:
            raise ValueError("real LLM provider requires LEGALCASE_LLM_BASE_URL and LEGALCASE_LLM_API_KEY")

    def complete(self, messages: list[dict], response_format: dict | None = None,
                 temperature: float = 0) -> str:
        return self.complete_with_metadata(messages, response_format, temperature)["content"]

    def complete_with_metadata(self, messages: list[dict], response_format: dict | None = None,
                               temperature: float = 0) -> dict:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": messages,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        choice = body["choices"][0]
        content = choice.get("message", {}).get("content")
        return {
            "content": content,
            "finish_reason": choice.get("finish_reason"),
            "response_structure_type": type(content).__name__,
            "http_api_success": True,
        }

    def generate(self, original_query: str) -> str:
        system = (
            "你是法律检索的查询理解模块。只输出严格 JSON，不回答法律问题，不预测条款号，"
            "不生成法律结论。domain 必须是劳动争议。search_queries 最多 3 条。"
            "字段为 original_query, domain, issue, user_intent, legal_concepts, search_queries。"
        )
        return self.complete([
                {"role": "system", "content": system},
                {"role": "user", "content": original_query},
            ], {"type": "json_object"}, 0)


class MockProvider:
    """Deterministic concept expansion for tests and offline development.

    It maps broad user-language concepts to formal legal vocabulary only; it
    never maps a query to an article number or benchmark answer.
    """

    name = "mock"
    model = "deterministic-mock-v0.5"

    _rules = (
        (re.compile(r"开了|辞退|裁员|解雇|解除|终止"), "解除劳动合同 违法解除 经济补偿 赔偿金"),
        (re.compile(r"补偿|赔偿|拿多少"), "经济补偿 赔偿金 计算标准"),
        (re.compile(r"试用期|转正"), "试用期 录用条件 解除劳动合同"),
        (re.compile(r"加班|晚上|周末|休息日"), "延长工作时间 加班工资 休息日 节假日"),
        (re.compile(r"工资|薪水|不发|拖欠|欠薪"), "劳动报酬 工资支付 拖欠工资"),
        (re.compile(r"签合同|签劳动合同|没签|未签|书面"), "书面劳动合同 未订立劳动合同 双倍工资"),
        (re.compile(r"仲裁|一年|时效|过期"), "劳动争议仲裁 仲裁时效 一年"),
        (re.compile(r"竞业|限制"), "竞业限制 经济补偿 违约"),
        (re.compile(r"社保|社会保险|五险一金"), "社会保险 劳动合同必备条款"),
        (re.compile(r"派遣|劳务"), "劳务派遣 用工单位 派遣单位"),
    )

    def generate(self, original_query: str) -> str:
        concepts: list[str] = []
        expansions: list[str] = []
        for pattern, expansion in self._rules:
            if pattern.search(original_query):
                concepts.extend(expansion.split())
                expansions.append(expansion)
        concepts = list(dict.fromkeys(concepts))[:8]
        search_queries = [original_query]
        if expansions:
            search_queries.append(" ".join(expansions[:2]))
        if len(concepts) >= 2:
            search_queries.append("劳动争议 " + " ".join(concepts[:5]))
        return json.dumps({
            "original_query": original_query,
            "domain": "劳动争议",
            "issue": "、".join(concepts[:3]) or "劳动争议法律检索",
            "user_intent": "查找适用的劳动争议法律规则",
            "legal_concepts": concepts,
            "search_queries": list(dict.fromkeys(search_queries))[:3],
        }, ensure_ascii=False)
