# Web Demo Final Productization — UX / Product Audit

审计范围：`frontend_demo/app.py`、`scripts/run_web_demo.ps1`、`frontend_demo/requirements.txt`，并核对 `LegalRAGPipeline`、生成器和案例 corpus 默认配置。

审计结论：当前 Demo 已具备可运行的研究演示闭环，调用的是生产 `LegalRAGPipeline`，并且 Pipeline 的案例默认 corpus 为 `data/processed/full_cases`。但页面展示层仍是最小化版本：没有展示完整的结构化法律分析和 citation metadata，也没有向用户明确显示当前运行模式与 corpus。生成失败的 Pipeline fallback 基本符合安全要求，但 UI 的顶层异常处理无法保留已经检索到的结果。

## A. 当前已正确工作的功能

### 1. 页面与启动方式

- 页面入口为 `frontend_demo/app.py`，使用 Streamlit。
- `scripts/run_web_demo.ps1` 会切换到项目根目录、设置 `PYTHONPATH`，然后执行 `streamlit run frontend_demo/app.py`。
- `frontend_demo/requirements.txt` 声明了 `streamlit` 依赖。
- 页面使用宽布局，包含问题输入框、提交按钮、加载提示、回答区、法规区、案例区、风险提示和可信度展示。

本次审计环境中 Streamlit 未安装，因此未进行浏览器级视觉验收；视觉结论依据页面代码结构，启动命令和依赖声明已核对。

### 2. 生产 Pipeline 调用链

用户点击“提交问题”后，页面执行：

1. `run_query()` 清理输入并调用 `pipeline.ask(query)`。
2. `create_pipeline()` 创建 `LegalRAGPipeline`，没有复制检索或生成逻辑。
3. Pipeline 执行法规 BM25/semantic/hybrid、reranker、案例检索、generation context budget、LLM generation 和 citation validation。
4. 页面从结构化 response 中提取 `legal_basis`、`related_cases`、`risk_note`、`confidence` 并渲染。

### 3. Full corpus 配置

- `backend/rag/pipeline.py` 的 `DEFAULT_CASE_CORPUS` 指向 `data/processed/full_cases`。
- Pipeline 在启用案例时创建 `UnifiedCaseSearchService`，并通过其 hybrid search 获取案例。
- `CASE_CORPUS_PATH` 可以覆盖默认路径；因此当前生产默认是 6492 案例，但运行环境变量可以改变实际 corpus。
- Demo 在真实 provider 下默认启用案例增强；在 mock provider 下默认关闭案例增强。也可以通过 `LEGALCASE_DEMO_CASES=1/0` 覆盖。

### 4. 安全 fallback

- Pipeline 生成器返回 `retrieval_only` 时，页面显示“AI总结生成暂时不可用。”。
- 页面同时保留法规引用，并添加“以上为检索结果，不代表AI生成结论。”。
- 案例增强 fallback 没有被标成 AI 成功答案；页面只使用已存在的 response/context 数据。
- 页面没有把异常堆栈、provider response、retry 明细或内部 validation 字段直接展示给用户。
- 当前页面没有“AI律师”“法律结论保证”等过度承诺用语。

## B. 必须修复的问题

### P0 — 顶层异常会丢失已检索结果

`run_query()` 捕获任意异常后直接返回空的 `legal_basis` 和 `related_cases`。如果异常发生在 Pipeline 已完成检索之后，页面无法展示已经取得的证据，且与“失败时仍展示 retrieval-only 结果”的产品要求不一致。

建议由产品层区分“Pipeline 已返回安全 fallback”和“调用本身异常”两类状态。异常路径不能伪造检索结果；如果没有可安全取得的检索结果，应明确显示不可用，而不是暗示已经完成检索。

### P0 — 法规和案例 metadata 没有完整呈现

当前法规卡片只展示 citation 和正文，忽略了 `law_name`、`article_number`、`source` 等确定性 metadata。案例卡片只展示 citation、title 和 reasoning，忽略了 `court`、`judgment_date`、`dispute_focus` 等字段。

这会削弱 citation verification 的可见性，也无法充分展示 6492 案例增强的价值。展示层应只渲染后端已验证并由真实 citation ID 对应的 metadata，不应由 UI 自行推断。

### P1 — `legal_analysis` 没有展示

最终结构化响应包含 `legal_analysis`，但 `normalize_result()` 没有返回它，页面也没有单独的法律分析区域。当前用户只能看到 answer 和 source 卡片，无法看到模型基于哪些证据形成分析。

### P1 — 模式和 corpus 对用户不可见

页面没有显示当前是法规-only 还是案例增强模式，也没有显示是否使用 full corpus。mock provider 默认法规-only，real provider 默认案例增强；同一个页面在不同环境下的产品行为可能不同。

建议增加非开发者化的状态说明，例如“法规检索”或“法规 + 类案检索”，并明确案例增强是否开启。不要展示 API 配置、路径堆栈或内部 provider 异常。

### P1 — 法律免责声明需要使用明确的正式表述

当前页面 caption 为“劳动法律法规与类案检索辅助演示，不构成法律意见。”，语义正确但不够完整。最终页面应明确加入：

> 本系统用于法律信息检索和类案辅助分析，不构成正式法律意见。

该声明应在页面标题附近持续可见，并在结果区风险提示中保持一致。

## C. 推荐的最终页面结构

```text
LegalCase-Copilot
AI Labor Law RAG Assistant
用途声明 + 当前模式/数据源状态

问题输入区
  输入框
  提交按钮

结果摘要区
  AI回答
  法律分析
  可信度

证据区
  法规依据
    LAW-1 ...
    法规名称 / 条号 / 正文 / 来源
  类案参考
    CASE-1 ...
    标题 / 法院 / 日期 / 争议焦点 / 类案说明

风险与限制区
  风险提示
  事实和证据限制
  正式法律意见免责声明
```

生成失败时，结果摘要区应改为清晰的不可用状态；证据区仍只展示实际返回且可验证的检索结果，并明确标注“以上为检索结果，不代表AI生成结论”。

## D. 推荐的 UI/UX 改进

### 信息层级

- 保持标题、问题输入、回答、证据、风险提示的顺序。
- 将“AI回答”和“法律分析”分开，避免把 source 正文误认为模型结论。
- 在回答区顶部显示当前模式和结果状态：AI generated、retrieval-only 或 evidence insufficient。

### 法规和案例卡片

- 法规卡片优先显示 `LAW-*`、法规名称、条号，再显示正文和来源。
- 案例卡片优先显示 `CASE-*`、标题、法院、日期、争议焦点，再显示类案 reasoning。
- 长法规正文和长案例说明使用折叠区域，默认显示摘要，避免页面纵向过长。
- LAW 与 CASE 使用不同的视觉标签，但不要使用容易造成法律效力误解的颜色或措辞。

### 加载和错误状态

- 加载文案应覆盖“检索法规、检索类案、生成回答”三个阶段，或使用一个不泄露内部实现的统一文案。
- 空输入、证据不足、AI生成失败和系统异常应使用不同的用户提示。
- 不显示 Python exception、HTTP 状态详情、retry prompt、模型原始输出或内部路径。

### 可信度和限制

- 不建议只显示裸的 `low` 或 `0.8`；应配合“基于当前检索证据的模型置信度”说明。
- 不把 confidence 解释为法律正确率、胜诉概率或法院裁判预测。
- 风险提示应靠近回答和证据，而不是只放在页面底部。

### 启动与公开展示

- `requirements.txt` 当前只有未锁定版本的 `streamlit`，可在公开展示前考虑使用经过验证的版本约束。
- 启动脚本当前依赖 PowerShell 当前用户可找到 `streamlit` 命令；公开演示说明中应明确虚拟环境和安装步骤。
- 页面应在启动时明确 offline/mock 与 real provider 的状态，但不得展示 API key 或配置值。

## E. 不应修改的后端逻辑

本阶段不应为了 UI 展示而修改：

- BM25、semantic、hybrid retrieval 或 reranker 算法；
- embedding 模型、向量索引或 6492 案例原始数据；
- citation validator 的严格 namespace 和真实性校验；
- generation context budget 和安全 fallback 规则；
- 真实 provider 的敏感配置读取逻辑；
- evaluation dataset、正式评测结果或评测指标定义。

UI 只应消费 Pipeline 已验证的结构化结果。法规名称、条号、法规正文、案例标题、法院和日期必须继续来自真实 retrieval metadata，不能由页面或模型补写。

## F. 最终人工验收 checklist

- [ ] 从项目根目录按文档命令可以启动页面。
- [ ] 页面标题为 `LegalCase-Copilot`，并显示 `AI Labor Law RAG Assistant`。
- [ ] 页面持续显示正式用途声明：“本系统用于法律信息检索和类案辅助分析，不构成正式法律意见。”。
- [ ] 输入劳动争议问题后，确实调用 `LegalRAGPipeline`。
- [ ] 页面明确显示当前法规-only或法规+案例模式。
- [ ] 案例增强模式实际使用 `data/processed/full_cases`，除非明确配置了其他 corpus。
- [ ] 正常回答同时展示 answer、legal_analysis、confidence、LAW citation 和 CASE citation。
- [ ] LAW citation 展示法规名称、条号、正文和来源 metadata。
- [ ] CASE citation 展示标题、法院、日期、争议焦点和类案说明 metadata。
- [ ] 不存在或未被模型引用的 citation 不会被展示为已引用依据。
- [ ] AI 生成失败时显示“AI总结生成暂时不可用。”。
- [ ] AI 生成失败时保留可安全展示的检索结果，并显示“以上为检索结果，不代表AI生成结论。”。
- [ ] evidence insufficient、空输入和系统异常有清晰且不同的提示。
- [ ] 页面不显示 API key、Authorization、Cookie、token、异常堆栈、完整 prompt 或原始模型响应。
- [ ] 页面不出现“AI律师”“保证法律结论”“保证胜诉”等表述。
- [ ] 长法规和案例文本不会造成首屏过度拥挤。
- [ ] loading、success、retrieval-only、error 四类状态均完成一次人工验收。
- [ ] 运行 `pytest tests` 通过，且 UI 变更没有改动 retrieval、embedding、reranker、evaluation 或数据文件。
