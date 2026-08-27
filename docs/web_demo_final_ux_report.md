# Web Demo Final UX Report

日期：2026-08-28
验收环境：Python 3.10、Streamlit 1.62、Streamlit in-app browser
运行地址：统一页面 `http://localhost:8503`

## 1. 本阶段修改

- `frontend_demo/app.py`
  - 增加法规-only / 法规 + 类案增强模式选择。
  - 增加 provider、法规库和 6,492 案例库状态展示。
  - 增加 Mock / Retrieval-only 明确标识。
  - 增加 5 个可点击示例问题，点击只填入输入框，不自动提交。
  - 增加法律分析、LAW metadata、CASE metadata、风险提示和证据置信度展示。
  - 增加安全 fallback 和域外状态展示。
  - 使用 `st.cache_resource` 缓存 pipeline 构造。
  - 使用 `st.status` 提供真实的 loading 状态，不显示虚假百分比。
- `frontend_demo/requirements.txt`：声明 `streamlit>=1.62,<2`。
- `scripts/run_web_demo.ps1`：改用当前 Python 环境执行 `python -m streamlit`。
- `docs/demo.md`：更新统一页面、模式和安全展示说明。
- `tests/test_demo_integration.py`：增加展示契约、metadata enrichment、provider 状态测试。

未修改 retrieval、embedding、reranker、evaluation、6492 案例数据或真实 provider 配置。

## 2. 浏览器验收

| 项目 | 结果 |
|---|---|
| 首页 | 通过；单页显示模式、provider、法规库和案例库状态 |
| 法规检索模式 | 通过；显示法规检索、案例库未启用 |
| 法规 + 6492 类案模式 | 通过；显示 6,492 条案例库并展示 CASE-1/CASE-2 |
| Loading | 通过；显示“正在检索法规与相关案例，并验证引用…” |
| Mock provider | 通过；明确显示“Mock 演示模式，不代表真实 AI 生成结果” |
| Retrieval-only fallback | 通过；明确显示 AI 未成功，并保留检索证据 |
| 域外问题 | 通过；显示未生成 AI 结论和知识库范围提示 |
| LAW citation | 通过；可展开显示 LAW ID、法规名称、条号和正文 |
| CASE citation | 通过；可展开显示 CASE ID、标题、法院、日期、争议焦点、裁判摘要和法律依据 |
| legal_analysis | 通过展示区域；mock/retrieval-only 时正确提示未生成 |
| risk_note | 通过 |
| confidence | 通过；fallback 固定为 low，未伪造置信度 |
| disclaimer | 通过；页面底部长期显示正式免责声明 |
| 宽屏布局 | 通过；统一页面不再需要访问两个端口 |

真实 AI 成功状态未验收。当前按要求使用本地 mock/retrieval-only 路径，未向 DeepSeek 或其他外部 provider 发送测试问题。

## 3. 性能测量

浏览器实测结果如下，均为本地 mock 路径：

| 模式 | 首次查询 | 第二次 warm query | 观察 |
|---|---:|---:|---|
| 法规检索 | 约 8.1 秒 | 约 9.3 秒 | pipeline 已缓存，但每次查询仍需执行本地检索和重排 |
| 法规 + 6492 类案 | 约 25.0 秒 | 约 22.8 秒 | 案例检索和本地模型推理是主要耗时 |

缓存已避免 Streamlit 每次 rerun 都重新构造 pipeline。当前 pipeline 返回的阶段计时可继续用于后续分析，但本阶段没有通过降低 top-k、跳过 reranker 或修改 embedding 来换取速度。

## 4. 阻断与限制

仍有一个面试演示限制：本地 mock provider 与现有 grounded generator 的成功生成接口不匹配，因此法规-only 和案例增强浏览器验收均呈现为安全 retrieval-only，而不是 AI 成功回答。页面已明确标识这一点，没有伪造成功结果。

如需验收真实成功回答，需要单独授权向 `.env` 配置的真实 provider 发送测试问题；本阶段没有执行。

另一个非功能性限制是现有 `.pytest_cache` 和部分历史数据目录的 Windows 权限导致测试出现一个缓存 warning；不影响测试结果。

## 5. 测试结果

```text
174 passed, 1 warning
```

warning 为 `PytestCacheWarning`，原因是无法写入现有 `.pytest_cache` 目录。

## 6. 截图

- `outputs/web-demo-home.png`
- `outputs/web-demo-law-only.png`
- `outputs/web-demo-case-augmented.png`
- `outputs/web-demo-fallback.png`

本阶段未执行 commit、push 或 release。
