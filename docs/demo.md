# Web Demo

## Start

From the project root, install the optional UI dependency:

```powershell
python -m pip install -r frontend_demo/requirements.txt
```

Then start the demo:

```powershell
.\scripts\run_web_demo.ps1
```

The default offline mode uses the existing deterministic mock provider. To use a configured OpenAI-compatible provider, set the variables in `.env` and start with:

```powershell
$env:LEGALCASE_LLM_PROVIDER = "real"
$env:LEGALCASE_DEMO_CASES = "1"
.\scripts\run_web_demo.ps1
```

The UI does not change the RAG pipeline. It calls `backend.rag.pipeline.LegalRAGPipeline` and renders its structured response.

## Page features

- Question input and submit button
- AI answer panel
- Verified law-basis citations
- Related-case citations when case augmentation is enabled and cases are cited
- Risk note and confidence display
- Safe handling when the answer contains no citations or the pipeline returns an evidence-insufficient response

## Example questions

- 公司下班后要求我在微信处理工作，是否属于加班？
- 公司没有签订书面劳动合同，可以要求二倍工资吗？
- 怀孕期间被辞退，可以要求哪些救济？
- 普通员工签订竞业限制协议是否有效？

The demo is for research and product presentation only. It does not constitute legal advice.
