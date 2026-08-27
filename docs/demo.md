# Web Demo

## Start

From the project root, install the optional UI dependency in the Python environment used by the project:

```powershell
python -m pip install -r frontend_demo/requirements.txt
```

Then start the demo:

```powershell
.\scripts\run_web_demo.ps1
```

The single page opens at `http://localhost:8501` and provides both `法规检索` and `法规 + 类案增强` modes. The default offline mode uses the existing deterministic mock provider and is visibly labeled as mock/retrieval-only; it must not be presented as a real AI answer.

To use a configured OpenAI-compatible provider, set the variables in `.env` and start with:

```powershell
$env:LEGALCASE_LLM_PROVIDER = "real"
$env:LEGALCASE_DEMO_CASES = "1"
.\scripts\run_web_demo.ps1
```

The UI does not change the RAG pipeline. It calls `backend.rag.pipeline.LegalRAGPipeline` and renders its structured response.

## Page features

- Explicit law-only / 6,492-case augmented mode selection
- Provider and corpus status labels
- Clickable example questions that do not auto-submit
- Structured answer, legal analysis, verified law metadata, and related-case metadata
- Risk note and evidence-based confidence display
- Safe retrieval-only fallback with no fabricated AI answer
- Cached pipeline resources so Streamlit reruns do not reconstruct the pipeline each time

## Example questions

- 公司下班后要求我在微信处理工作，是否属于加班？
- 公司没有签订书面劳动合同，可以要求二倍工资吗？
- 怀孕期间被辞退，可以要求哪些救济？
- 普通员工签订竞业限制协议是否有效？

The demo is for research and product presentation only. It does not constitute legal advice.
