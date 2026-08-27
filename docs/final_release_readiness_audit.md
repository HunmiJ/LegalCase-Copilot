# Final Release Readiness Audit

日期：2026-08-28
状态：Release Candidate 本地冻结前审计

## 总结

Phase 2–4 的 Streamlit Demo 改造、真实 provider 浏览器验收和安全 fallback 已通过；本地测试为 `174 passed, 1 warning`。真实截图已保存到 `docs/images/`。

当前可以创建本地 Release Candidate commit，但仓库尚不适合直接作为“公开 GitHub 最终版”发布。README Finalization 仍需单独完成，主要原因是 README 仍保留旧版本评测标签、缺少当前真实 Demo 截图与 6492 案例说明，且仓库内若干历史文档/脚本含有本机绝对路径。

## 检查结果

### 1. 架构与功能说明

README 已说明或覆盖：

- BM25、embedding 与 hybrid retrieval
- Cross-encoder reranking
- Case-Augmented RAG
- LAW/CASE citation validation 与 provenance
- safety guard 与 evidence-insufficient fallback

需要在 README Finalization 中补充或明确：

- 372 条法规库与 6,492 条 full-case corpus 的当前状态
- Streamlit 单页 Demo、两种分析模式和真实/Mock provider 状态
- 6492 案例 corpus 不随 GitHub 仓库发布
- 数据来源、provenance 与 licensing 限制
- 当前 Final 30-query real evaluation 的真实指标与自动评测局限

### 2. README 发现的问题

- 仍使用 `V0.7.6`、`V0.6`、`V0.9` 等开发阶段评测标签，不适合首页作为最终版本叙述。
- 没有当前真实 Streamlit Demo 截图链接。
- Quick Start 调用 `scripts/run_demo.ps1`，应在 Finalization 中确认并统一到 `scripts/run_web_demo.ps1`。
- Evaluation Results 没有明确列出最终 30-query generation success：law-only 86.67%，law+6492-cases 96.67%。
- 没有清楚说明 full corpus 和 derived embeddings 为外部/本地运行时资产，不进入公开仓库。

### 3. 复现与配置

已确认：

- `.env.example` 不含真实 key，默认 provider 为 mock。
- `frontend_demo/requirements.txt` 声明 Streamlit 依赖。
- `scripts/run_web_demo.ps1` 启动统一 Streamlit Demo。
- 页面明确标注 Mock 不代表真实 AI 结果，并在 provider 不可用时使用安全 fallback。

README Finalization 需要补充真实 provider 的环境变量名称、Demo 启动示例和仅发送本地配置、不提交凭据的说明。

### 4. 隐私、凭据与路径

本次扫描未发现真实 API key、Bearer token、Cookie、密码或 `.env` 内容进入待提交文件；`.env` 已被 `.gitignore` 忽略。

但扫描发现历史文档和脚本中存在 `D:\\Project\\...`、`C:\\Users\\Janet\\...` 等本机绝对路径，例如 full-case conversion/source 报告和若干分析脚本。它们不属于本阶段 Demo 功能修改，但公开 GitHub 前应清理、改为相对路径或泛化示例路径。

### 5. 大文件与生成物

已确认：

- `data/processed/full_cases/` 被精确忽略。
- `*.npy` 被忽略；历史已跟踪文件不因规则自动取消跟踪。
- `.env`、cache、model、`.pytest_cache` 与临时 debug 输出被忽略。
- 当前没有发现待跟踪的大型 full corpus 或 full corpus embedding。
- 本次四张真实截图位于 `docs/images/`，尺寸约 18–21 KB，可作为公开 Demo 资产。

### 6. 验证结果

- `pytest tests`：174 passed，1 warning（既有 `.pytest_cache` 权限 warning）
- `git diff --check`：无内容错误；仅有 LF/CRLF 转换 warning
- Streamlit 真实浏览器验收：law-only 2/2，law+6492-cases 2/2
- fallback 页面：未伪装成 AI 成功，未生成伪造 confidence

## 当前 RC 应纳入的文件

- `frontend_demo/`
- `scripts/run_web_demo.ps1`
- `docs/demo.md`
- `docs/images/demo-home.png`
- `docs/images/demo-law-only-success.png`
- `docs/images/demo-case-augmented-success.png`
- `docs/images/demo-fallback.png`
- `tests/test_demo_integration.py`
- Phase 2–4 UX、provider acceptance、parity diagnosis 与本审计文档

不应纳入：`.env`、full corpus、full corpus embeddings、model/cache、临时日志及真实 provider 凭据。

## 结论

可以开始 README Finalization；完成 README 的当前架构、最终评测、数据来源/licensing、复现方式、截图和路径隐私清理后，再进行公开 GitHub 发布准备。

本审计阶段不执行 push、tag 或 GitHub release。
