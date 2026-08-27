"""Streamlit presentation layer for LegalCase-Copilot."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
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
FORMAL_DISCLAIMER = "本系统用于劳动法律信息检索和类案辅助分析，不构成正式法律意见。"
MODE_LAW_ONLY = "law_only"
MODE_LAW_AND_CASES = "law_and_cases"
MODE_LABELS = {
    MODE_LAW_ONLY: "法规检索",
    MODE_LAW_AND_CASES: "法规 + 类案增强",
}
EXAMPLE_QUESTIONS = (
    "公司无正当理由辞退我，可以要求赔偿吗？",
    "工作一个多月还没有签劳动合同怎么办？",
    "公司长期拖欠工资，我可以采取哪些措施？",
    "下班后一直在微信处理工作算加班吗？",
    "公司没有支付竞业补偿，我还需要履行竞业限制吗？",
)
FULL_CASE_REQUIRED_FILES = ("cases.jsonl", "case_embeddings.npy", "case_embedding_index.json")


def full_case_corpus_available() -> bool:
    """Return whether the external production case artifacts are installed."""
    configured = os.getenv("CASE_CORPUS_PATH")
    corpus_dir = Path(configured) if configured else Path(ROOT) / "data" / "processed" / "full_cases"
    if corpus_dir.suffix.lower() == ".jsonl":
        corpus_dir = corpus_dir.parent
    return all((corpus_dir / filename).is_file() for filename in FULL_CASE_REQUIRED_FILES)


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


def _configured_provider_name() -> str:
    _load_local_env()
    return os.getenv("LEGALCASE_LLM_PROVIDER", "mock").lower()


def create_provider(provider_name: str | None = None):
    """Create the configured provider; mock mode is the offline default."""
    provider_name = provider_name or _configured_provider_name()
    if provider_name == "real":
        return OpenAICompatibleProvider()
    return MockProvider()


def _build_pipeline(include_cases: bool, provider_name: str):
    provider = create_provider(provider_name)
    return LegalRAGPipeline(provider, include_cases=include_cases)


if st is not None:
    _build_pipeline = st.cache_resource(show_spinner=False)(_build_pipeline)


def create_pipeline(include_cases: bool = True):
    """Build the existing pipeline without changing its implementation."""
    provider_name = _configured_provider_name()
    return _build_pipeline(include_cases, provider_name)


def _law_items(response: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    selected = response.get("legal_basis") or response.get("relevant_laws") or []
    context_by_id = {
        item.get("citation_id"): item
        for item in result.get("context", {}).get("items", [])
        if item.get("citation_id")
    }
    enriched = []
    for item in selected:
        citation = item.get("citation") or item.get("citation_id", "")
        source = context_by_id.get(citation, {})
        merged = dict(source)
        merged.update(item)
        merged["citation"] = citation
        merged.setdefault("law_name", source.get("law_name", ""))
        merged.setdefault("article_number", source.get("article_number", ""))
        merged.setdefault("text", item.get("content") or source.get("article_content", ""))
        merged.setdefault("source", source.get("source", ""))
        enriched.append(merged)
    return enriched


def _case_items(response: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    if response.get("related_cases"):
        return response["related_cases"]
    return [
        {"citation": item.get("citation_id", ""), "case_id": item.get("case_id", ""),
         "title": item.get("title", ""), "court": item.get("court", ""),
         "judgment_date": item.get("date") or item.get("judgment_date", ""),
         "dispute_focus": item.get("dispute_focus") or item.get("legal_issue", ""),
         "judgment_summary": item.get("judgment") or item.get("judgment_summary", ""),
         "legal_basis": item.get("legal_basis", []),
         "reasoning": item.get("judgment") or item.get("legal_issue", "")}
        for item in result.get("context", {}).get("case_items", [])
    ]


def _analysis_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                claim = str(item.get("claim") or item.get("text") or "").strip()
                if claim:
                    parts.append(claim)
            elif item:
                parts.append(str(item).strip())
        return "\n\n".join(parts)
    return ""


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
    legal_analysis = _analysis_text(response.get("legal_analysis"))
    generation_status = generation_status or "unknown"
    generation_failed = generation_status == "retrieval_only" or bool(generation_meta.get("fallback"))
    if generation_failed:
        answer = AI_UNAVAILABLE_MESSAGE
        risk_note = f"{risk_note}\n\n{RETRIEVAL_ONLY_NOTE}"
    return {
        "answer": answer,
        "legal_analysis": legal_analysis,
        "legal_basis": _law_items(response, result),
        "related_cases": _case_items(response, result),
        "risk_note": risk_note,
        "confidence": (response.get("confidence") or "low") if not generation_failed else "low",
        "generation_status": generation_status,
        "generation_failed": generation_failed,
        "generation_meta": generation_meta,
    }


def presentation_status(result: dict[str, Any], provider_name: str, mode: str) -> dict[str, str]:
    """Return user-facing status labels without exposing provider internals."""
    non_generation_statuses = {"out_of_domain", "evidence_insufficient", "unverifiable_article", "unknown"}
    no_ai_result = result.get("generation_status") in non_generation_statuses
    if provider_name == "real_llm":
        provider_label = "AI生成：DeepSeek"
        provider_note = "已配置真实 AI provider。"
        generation_label = "未生成 AI 结论" if no_ai_result else ("AI generated" if not result.get("generation_failed") else "Retrieval-only")
    else:
        provider_label = "Mock 演示模式"
        provider_note = "Mock 演示模式，不代表真实 AI 生成结果。"
        generation_label = "未生成 AI 结论" if no_ai_result else ("Mock 输出（不代表真实 AI 生成结果）" if not result.get("generation_failed") else "Retrieval-only")
    return {
        "provider_label": provider_label,
        "provider_note": provider_note,
        "mode_label": MODE_LABELS.get(mode, MODE_LABELS[MODE_LAW_AND_CASES]),
        "generation_label": generation_label,
    }


def run_query_timed(pipeline: Any, query: str) -> tuple[dict[str, Any], dict[str, float]]:
    start = time.perf_counter()
    result = run_query(pipeline, query)
    elapsed = (time.perf_counter() - start) * 1000
    raw = getattr(pipeline, "last_result", None)
    breakdown = raw.get("latency_breakdown_ms", {}) if isinstance(raw, dict) else {}
    timings = {key: float(value) for key, value in breakdown.items() if isinstance(value, (int, float))}
    timings["query_total"] = elapsed
    return result, timings


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
        raw_result = pipeline.ask(query.strip())
        try:
            pipeline.last_result = raw_result
        except Exception:
            pass
        return normalize_result(raw_result)
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
    st.caption("劳动法律信息检索与类案辅助分析 · LegalTech / AI engineering portfolio")

    case_corpus_available = full_case_corpus_available()
    mode_options = [MODE_LAW_ONLY]
    if case_corpus_available:
        mode_options.append(MODE_LAW_AND_CASES)
    mode = st.radio(
        "分析模式",
        options=mode_options,
        index=0,
        format_func=lambda value: MODE_LABELS[value],
        horizontal=True,
    )
    include_cases = mode == MODE_LAW_AND_CASES
    provider = create_provider()
    status_probe = {"generation_failed": True}
    status = presentation_status(status_probe, getattr(provider, "name", "mock"), mode)
    case_count = "6,492 条" if case_corpus_available and include_cases else "未启用"
    law_count = "372 条"
    with st.container(border=True):
        st.markdown("**当前运行状态**")
        st.write(f"当前模式：{status['mode_label']}　·　法规库：{law_count}　·　案例库：{case_count}")
        st.caption(f"{status['provider_label']}　·　{status['provider_note']}")
    if not case_corpus_available:
        st.info("6,492案例生产语料未安装，本地当前仅可使用法规检索。请按文档准备并配置 full corpus 后再启用类案增强。")

    if "selected_example" not in st.session_state:
        st.session_state.selected_example = ""
    query_default = st.session_state.pop("selected_example", "")
    query = st.text_area(
        "请输入劳动法律问题",
        value=query_default,
        placeholder="例如：公司下班后要求我在微信处理工作，是否属于加班？",
        height=110,
    )
    st.caption("示例问题（点击后仅填入输入框，不会自动提交）")
    example_columns = st.columns(2)
    for index, example in enumerate(EXAMPLE_QUESTIONS):
        with example_columns[index % 2]:
            if st.button(example, key=f"example_{index}"):
                st.session_state.selected_example = example
                st.rerun()
    submitted = st.button("开始分析", type="primary")

    if not submitted:
        st.info("请输入问题后点击“提交问题”。")
        return
    if not query.strip():
        st.warning("请输入劳动法律问题。")
        return

    with st.status("正在检索法规与相关案例，并验证引用…", expanded=True) as progress:
        st.write("正在检索法规与相关证据…")
        pipeline = create_pipeline(include_cases=include_cases)
        result, timings = run_query_timed(pipeline, query)
        progress.update(label="分析完成", state="complete", expanded=False)

    final_status = presentation_status(result, getattr(pipeline.provider, "name", "mock"), mode)
    if result["generation_failed"]:
        st.warning("AI 分析暂时未生成成功。")
        st.info(RETRIEVAL_ONLY_NOTE)
    else:
        st.success(final_status["generation_label"])

    st.markdown("### 结论摘要")
    st.write(result["answer"])

    st.markdown("### 法律分析")
    if result["legal_analysis"] and not result["generation_failed"]:
        st.write(result["legal_analysis"])
    elif result["generation_failed"]:
        st.info("AI 分析未生成；下方仅展示检索证据。")
    else:
        st.info("本次回答没有可展示的法律分析。")

    left, right = st.columns(2)
    with left:
        st.markdown("### 法律依据")
        if result["legal_basis"]:
            for item in result["legal_basis"]:
                citation = item.get("citation", "LAW")
                with st.expander(f"{citation} · {item.get('law_name') or '法规'}", expanded=False):
                    st.write(f"法规名称：{item.get('law_name') or '未提供'}")
                    st.write(f"条号：{item.get('article_number') or '未提供'}")
                    st.write(item.get("text") or item.get("content") or "未提供法规正文。")
                    if item.get("source"):
                        st.caption(f"来源：{item['source']}")
        else:
            st.info("本次回答没有可展示的法规 citation。")

    with right:
        st.markdown("### 相关案例")
        if result["related_cases"]:
            for item in result["related_cases"]:
                citation = item.get("citation", "CASE")
                with st.expander(f"{citation} · {item.get('title') or '相关案例'}", expanded=False):
                    st.write(f"案例 ID：{item.get('case_id') or '未提供'}")
                    st.write(f"法院：{item.get('court') or '未提供'}")
                    st.write(f"日期：{item.get('judgment_date') or item.get('date') or '未提供'}")
                    st.write(f"争议焦点：{item.get('dispute_focus') or item.get('legal_issue') or '未提供'}")
                    st.write(item.get("judgment_summary") or item.get("reasoning") or "该案例仅作类案参考。")
                    if item.get("legal_basis"):
                        st.caption("法律依据：" + "；".join(map(str, item["legal_basis"])))
        else:
            st.info("本次回答没有可展示的案例 citation。")

    st.markdown("### 风险提示")
    st.warning(result["risk_note"])
    st.metric("基于当前证据的置信度", result["confidence"])
    if timings.get("query_total"):
        st.caption(f"本次查询耗时：{timings['query_total']:.0f} ms")
    st.divider()
    st.caption(FORMAL_DISCLAIMER + "\n具体争议请结合完整证据并咨询专业法律人士。")


if __name__ == "__main__":
    main()
