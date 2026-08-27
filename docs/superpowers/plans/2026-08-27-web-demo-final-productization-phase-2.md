# Web Demo Final Productization Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Streamlit presentation layer into a single interview-ready demo with explicit modes, safe provider status, structured citations, cached pipeline resources, measurable latency, and browser-verified UX.

**Architecture:** Keep `LegalRAGPipeline` and all retrieval/generation internals unchanged. Add presentation-layer helpers for mode configuration, provider/corpus labels, safe normalization, citation metadata, and timing; cache only the constructed pipeline with `st.cache_resource`, and render status-aware result sections from validated response/context data.

**Tech Stack:** Python 3.10, Streamlit 1.62, unittest/pytest, existing LegalRAGPipeline, browser acceptance.

**Spec:** User-approved Phase 2 requirements in the conversation.

## Global Constraints

- Do not modify retrieval, embedding, reranker, evaluation, or 6,492-case data.
- Mock and retrieval-only results must be explicitly labeled and never presented as real AI success.
- Use the local mock/retrieval-only path for implementation and browser verification.
- Do not commit, push, or create a release.
- Do not display secrets, prompts, stack traces, debug JSON, or internal filesystem paths.

---

### Task 1: Define safe presentation contract with tests

**Files:**
- Modify: `tests/test_demo_integration.py`
- Modify: `frontend_demo/app.py`

**Interfaces:**
- `normalize_result(raw_result, mode="law_and_cases") -> dict`
- `presentation_status(result, provider_name, mode) -> dict`
- `extract_cited_items(...) -> list[dict]`

- [ ] **Step 1: Add failing tests** for `legal_analysis`, provider labels, mode labels, deterministic LAW/CASE metadata, and retrieval-only status.
- [ ] **Step 2: Run the focused tests and confirm they fail because the new fields/helpers do not exist.**
- [ ] **Step 3: Implement the minimal normalization and metadata extraction helpers without changing pipeline behavior.**
- [ ] **Step 4: Run the focused tests and confirm they pass.**
- [ ] **Step 5: Run the existing demo integration tests to catch regressions.**

### Task 2: Add cached pipeline construction and timing

**Files:**
- Modify: `frontend_demo/app.py`
- Modify: `tests/test_demo_integration.py`

**Interfaces:**
- `create_pipeline(include_cases: bool) -> LegalRAGPipeline`
- `run_query(pipeline, query) -> dict`
- `run_query_timed(pipeline, query) -> tuple[dict, dict]`

- [ ] **Step 1: Add tests for explicit `include_cases`, timing keys, and safe exception status.**
- [ ] **Step 2: Run focused tests and confirm the timing/cache contract fails.**
- [ ] **Step 3: Add `st.cache_resource` around presentation-owned pipeline construction, keyed by mode, and measure initialization/query phases without touching core algorithms.**
- [ ] **Step 4: Run focused tests and confirm they pass.**

### Task 3: Rebuild the Streamlit page

**Files:**
- Modify: `frontend_demo/app.py`
- Modify: `frontend_demo/requirements.txt`
- Modify: `scripts/run_web_demo.ps1`
- Modify: `docs/demo.md`

**Interfaces:**
- Single page with a mode selector, provider/corpus status, clickable example buttons, safe loading status, structured answer/analysis/citations/risk/confidence sections, and persistent disclaimer.

- [ ] **Step 1: Add presentation tests for example labels, mode labels, disclaimer text, and forbidden overclaiming phrases.**
- [ ] **Step 2: Run focused tests and confirm the page contract fails.**
- [ ] **Step 3: Implement the page using native Streamlit containers, columns, expanders, status/spinner messaging, and no deprecated `use_container_width`.**
- [ ] **Step 4: Run focused tests and compile the app.**

### Task 4: Measure cold and warm behavior

**Files:**
- Create: `docs/web_demo_final_ux_report.md`
- Modify: `frontend_demo/app.py` only if timing labels need presentation fixes.

- [ ] **Step 1: Run controlled local mock law-only and case-augmented queries twice each, recording initialization, law retrieval, case retrieval, reranking, and generation timings.**
- [ ] **Step 2: Confirm cache reuse by comparing first and second runs and inspect Streamlit logs for repeated initialization.**
- [ ] **Step 3: Record actual bottlenecks and any remaining limitations without reducing retrieval quality.**

### Task 5: Browser acceptance and final verification

**Files:**
- Modify: `docs/web_demo_final_ux_report.md`
- Create: `outputs/web-demo-home.png`, `outputs/web-demo-law-only.png`, `outputs/web-demo-case-augmented.png`, `outputs/web-demo-fallback.png`

- [ ] **Step 1: Start one unified Streamlit app and use the browser to verify home, both modes, loading, fallback, domain guard, citations, analysis, risk note, confidence, disclaimer, and wide layout.**
- [ ] **Step 2: Save the four required screenshots.**
- [ ] **Step 3: Run the complete `pytest` suite.**
- [ ] **Step 4: Verify only allowed files changed and no commit/push occurred.**
- [ ] **Step 5: Complete the UX report with modifications, acceptance results, timings, blockers, and screenshot paths.**
