# Web Demo Pipeline Parity Diagnosis

日期：2026-08-28

## 结论

本次 0/2 浏览器失败的直接根因是 Streamlit 进程运行在受限网络执行环境中。四次 provider 请求均在 HTTP 请求阶段抛出 `URLError`，三次重试后安全 fallback；没有进入 JSON 解析、schema 校验或 citation 校验。

在允许访问已配置 provider 的同一 Python 3.10 环境中，直接调用同一生产 pipeline 成功；将 Streamlit 完全停止并在同样可访问 provider 的环境中重新启动后，浏览器验收恢复成功。因此没有修改 prompt、retrieval、embedding、reranker、TopK、evaluation 或 6492 案例数据。

另一个重要差异是历史 Final 30-query evaluation 的首条问题为“公司无正当理由单方面解除劳动合同，员工可以要求赔偿吗？”，不是本阶段固定测试的“公司无正当理由辞退我，可以要求赔偿吗？”。正式评测指标不保证任意新增问题必然成功；本次对照已直接验证固定问题在正确网络环境下可以成功。

## 环境与实现对照

| 项目 | Final evaluation | Streamlit Demo |
|---|---|---|
| Python | 历史运行记录未保存 executable；当前可复现的 3.12 环境为 `<LOCAL_USER_HOME>\\.conda\\envs\\face312\\python.exe` / 3.12.13 | `<PYTHON_ROOT>\\python\\python3.10\\python.exe` / 3.10.11 |
| 工作目录 | `<PROJECT_ROOT>` | `<PROJECT_ROOT>` |
| provider | `OpenAICompatibleProvider` | `OpenAICompatibleProvider`（真实模式） |
| model | `deepseek-v4-flash` | `deepseek-v4-flash` |
| base URL | 已配置；值未记录 | 已配置；值未记录 |
| temperature | 0 | 0（由 `GroundedGenerator` 调用） |
| timeout | 30 秒 | 30 秒 |
| retry | 2（最多 3 次尝试） | 2（最多 3 次尝试） |
| schema | JSON object + 同一 `GroundedGenerator` 校验 | JSON object + 同一 `GroundedGenerator` 校验 |
| generator | `backend.rag.generator.GroundedGenerator` | `backend.rag.generator.GroundedGenerator`，由同一 `LegalRAGPipeline` 创建 |
| pipeline | 显式共享 retriever/reranker；类案模式显式传入 full corpus 路径 | `LegalRAGPipeline` 同类同默认 full corpus；retriever/reranker 延迟加载，并由 `st.cache_resource` 缓存 |

evaluation 的历史指标文件记录 provider 为 `real_llm`、temperature 0、timeout 30、retry 2；没有记录当时 Python executable/version。当前机器确认存在 Python 3.12.13，但本次 Demo 与直接对照均使用 Python 3.10.11。未发现代码路径、provider、model、schema 或生成器实现差异。

## 失败 taxonomy

受限网络下的 direct pipeline 对固定问题 1、法规-only：

- provider request：失败
- HTTP API：失败
- JSON parse：未发生/失败
- schema validation：未发生/失败
- citation validation：未发生/失败
- attempts：3（retry_count=2）
- exception class：`ProviderError`
- provider error type：`URLError`
- final status：`retrieval_only`
- fallback：`true`

这与旧 Streamlit 浏览器验收的四次 fallback 一致，故前端不是失败源头。

## 同进程对照与修复后浏览器验收

在 Python 3.10.11、同工作目录、同 provider 配置下，直接调用生产 pipeline 的固定问题 1 法规-only 结果：

- provider request / HTTP / JSON / schema / citation：全部成功
- generation status：`success`
- fallback：`false`
- 总耗时：约 20,795 ms；其中 reranker 约 8,853 ms，generation 约 9,445 ms

完全停止旧 Streamlit 进程、清除其进程内 resource cache 并在可访问 provider 的环境中重新启动后，实际浏览器点击结果如下：

| 模式 | 问题 1 | 问题 2 | 浏览器总耗时 |
|---|---:|---:|---:|
| 法规-only | 成功 | 成功 | 约 26.7 s / 22.7 s |
| 法规 + 6492 类案 | 成功 | 成功 | 约 57.5 s / 39.2 s |

第二条类案增强结果实际显示：

- answer
- legal_analysis
- LAW-1、LAW-2、LAW-3 metadata 区域
- CASE-1、CASE-2 metadata 区域
- risk note
- confidence
- 模式与 6,492 案例库状态
- 正式免责声明

问题 1 类案增强回答没有引用 CASE，因此页面按实际引用为空时不强行伪造 CASE citation；问题 2 验证了 CASE metadata 展示路径。

域外问题“请推荐上海明天的天气和附近餐厅。”实际显示 `未生成 AI 结论`，无 AI answer、无伪造 confidence，并保留正式免责声明。页面未发现 raw JSON、Python repr、stack trace 或 debug 字段。

## cache 与性能判断

`frontend_demo/app.py` 的 `_build_pipeline` 已使用 `st.cache_resource`，cache key 包含模式和 provider name；pipeline、retriever/reranker/case service 不会因正常 rerun 重复创建。首次类案请求的主要成本来自 reranker 加载和真实 generation；本次没有证据表明需要降低 retrieval 质量或修改算法。

## 修改文件

- 无 retrieval/RAG/evaluation 核心代码修改。
- 本阶段新增本报告。
- 仅通过完全停止并重启 Streamlit 进程消除了旧进程/旧 resource cache 与受限网络环境影响。

## 发布阻断

真实功能层面不再存在本次 parity 阻断：两种模式均有可验证真实成功页面，fallback 仍安全。

仍需注意：Demo 必须从具备 provider 网络访问权限的运行环境启动；在受限网络环境启动时会可靠地进入安全 fallback。类案模式真实端到端约 39–58 秒，属于明显等待成本，但本次没有发现重复初始化导致的错误，也未擅自改变检索质量。

未执行 commit、push 或 release。
