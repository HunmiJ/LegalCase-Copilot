"""Streamlit presentation layer for LegalCase-Copilot."""

from __future__ import annotations

import os
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))

try:
    import streamlit as st
except ModuleNotFoundError:  # Keep unit-test imports safe without the optional UI dependency.
    st = None

from backend.llm import MockProvider, OpenAICompatibleProvider
from backend.rag.pipeline import LegalRAGPipeline

AI_UNAVAILABLE_MESSAGE = "AI总结生成暂时不可用。"
RETRIEVAL_ONLY_NOTE = "以上为检索结果，不代表AI生成结论。"


def _load_local_env() -> None:
    """Load simple KEY=VALUE entries without printing or overriding env vars."""
    env_path = os.path.join(ROOT, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except OSError:
        return


def create_provider():
    """Create the configured provider; mock mode is the offline default."""
    _load_local_env()
    provider_name = os.getenv("LEGALCASE_LLM_PROVIDER", "mock").lower()
    if provider_name == "real":
        return OpenAICompatibleProvider()
    return MockProvider()


def create_pipeline():
    """Build the existing pipeline without changing its implementation."""
    provider = create_provider()
    default_cases = "1" if getattr(provider, "name", "") == "real_llm" else "0"
    include_cases = os.getenv("LEGALCASE_DEMO_CASES", default_cases) == "1"
    return LegalRAGPipeline(provider, include_cases=include_cases)


def _law_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    return response.get("legal_basis") or response.get("relevant_laws") or []


def _case_items(response: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    if response.get("related_cases"):
        return response["related_cases"]
    return [
        {"citation": item.get("citation_id", ""), "title": item.get("title", ""),
         "reasoning": item.get("judgment") or item.get("legal_issue", "")}
        for item in result.get("context", {}).get("case_items", [])
    ]


def normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return the stable fields consumed by the UI, including safe defaults."""
    response = result.get("response") or {}
    answer = response.get("answer") or " ".join(response.get("issue_summary") or []) or "无法基于当前法律数据库提供可靠回答。"
    generation_status = response.get("generation_status")
    generation_meta = result.get("generation_meta") or {}
    generation_failed = generation_status == "retrieval_only" or (
        generation_meta.get("fallback") and generation_status not in {"evidence_insufficient", "out_of_domain"}
    )
    risk_note = response.get("risk_note") or response.get("disclaimer") or "请结合完整事实和证据核验。"
    if generation_failed:
        answer = AI_UNAVAILABLE_MESSAGE
        risk_note = f"{risk_note}\n\n{RETRIEVAL_ONLY_NOTE}"
    return {
        "answer": answer,
        "legal_basis": _law_items(response),
        "related_cases": _case_items(response, result),
        "risk_note": risk_note,
        "confidence": response.get("confidence") or "low",
    }


def run_query(pipeline: Any, query: str) -> dict[str, Any]:
    """Call the existing pipeline and normalize its structured response."""
    if not query or not query.strip():
        return {
            "answer": "请输入劳动法律问题。",
            "legal_basis": [],
            "related_cases": [],
            "risk_note": "未执行检索。",
            "confidence": "low",
        }
    try:
        return normalize_result(pipeline.ask(query.strip()))
    except Exception:
        return {
            "answer": AI_UNAVAILABLE_MESSAGE,
            "legal_basis": [],
            "related_cases": [],
            "risk_note": f"演示服务暂时不可用，请稍后重试或咨询专业人士。\n\n{RETRIEVAL_ONLY_NOTE}",
            "confidence": "low",
        }


def main() -> None:
    if st is None:
        raise RuntimeError("Streamlit is required. Install frontend_demo/requirements.txt first.")

    st.set_page_config(page_title="LegalCase-Copilot", page_icon="⚖️", layout="wide")
    st.title("LegalCase-Copilot")
    st.subheader("AI Labor Law RAG Assistant")
    st.caption("劳动法律法规与类案检索辅助演示，不构成法律意见。")

    query = st.text_area(
        "请输入劳动法律问题",
        placeholder="例如：公司下班后要求我在微信处理工作，是否属于加班？",
        height=110,
    )
    submitted = st.button("提交问题", type="primary", use_container_width=True)

    if not submitted:
        st.info("请输入问题后点击“提交问题”。")
        return
    if not query.strip():
        st.warning("请输入劳动法律问题。")
        return

    with st.spinner("正在检索法规与相关证据..."):
        result = run_query(create_pipeline(), query)

    st.markdown("### AI回答")
    st.write(result["answer"])

    left, right = st.columns(2)
    with left:
        st.markdown("### 法规引用")
        if result["legal_basis"]:
            for item in result["legal_basis"]:
                citation = item.get("citation", "")
                content = item.get("content") or item.get("text", "")
                with st.container(border=True):
                    st.markdown(f"**{citation or 'LAW'}**")
                    st.write(content or "未提供法规正文。")
        else:
            st.info("本次回答没有可展示的法规 citation。")

    with right:
        st.markdown("### 案例引用")
        if result["related_cases"]:
            for item in result["related_cases"]:
                with st.container(border=True):
                    st.markdown(f"**{item.get('citation', 'CASE')} · {item.get('title', '相关案例')}**")
                    st.write(item.get("reasoning") or "该案例仅作为类案参考。")
        else:
            st.info("本次回答没有可展示的案例 citation。")

    st.markdown("### 风险提示")
    st.warning(result["risk_note"])
    st.metric("可信度", result["confidence"])


if __name__ == "__main__":
    main()
