# Final Generation Contract Refactor Report

## 运行范围

- 固定问题：5 条；每种模式重复：3 次；总 production generation runs：30。
- 模式：法规-only、法规+6492案例。
- 完整链路：provider → JSON parser → schema → sanitizer → 严格 citation validator → deterministic metadata rendering。
- 真实provider配置仅摘要记录：real_llm，不写入密钥或完整响应。

## 修改前后 smoke 对比

| 指标 | V1.5.8基线 | law-only本次 | law+6492本次 |
|---|---:|---:|---:|
| generation success rate | 0.0000 | 0.9333 | 1.0 |
| citation validity（成功响应） | — | 1.0 | 1.0 |
| sanitation events | — | 5 | 13 |
| unsupported citation failures | — | 0 | 0 |
| required field failures | — | 1 | 0 |
| generation failed after retries | — | 1 | 0 |
| average latency (ms) | — | 18782.3 | 34928.35 |

基线说明：V1.5.8 最近一次正常重试 smoke：law-only 0/5，law+6492-cases 0/5；该基线未使用本次确定性元数据渲染。

## 契约与安全结论

- 模型只选择已在当前 context 中存在的 LAW-* / CASE-* ID；法规名称、条号、案例标题、法院和日期由真实 retrieval metadata 确定性渲染。
- 不存在的 citation ID 仍被拒绝；未被模型引用的 source 不展示为引用。
- 不支持的正文具体条号仅在可安全替换时记录 sanitation event 并重新校验；范围/嵌套条款等无法安全处理的内容仍拒绝。
- citation validator 的严格规则未放宽，失败响应未标记为成功。

## legal_analysis shape 与阶段统计

### law-only

- shape frequency：`{"string": 21}`
- stage success counts：`{"provider_success": 21, "json_parse_success": 21, "schema_success": 14, "citation_validation_success": 14}`

### law+6492-cases

- shape frequency：`{"string": 18}`
- stage success counts：`{"provider_success": 18, "json_parse_success": 18, "schema_success": 15, "citation_validation_success": 15}`

## pytest

本报告由 smoke 运行器生成；完整 pytest 结果在运行结束后补录。

## 限制与下一步

本次是5条固定问题的重复 smoke，不是最终30条正式评测。只有当两种模式在重复运行中保持稳定成功、成功响应的 citation validity 为1.0且不再由 context外条号主导失败时，才建议进入最终正式评测；否则应停止继续堆叠版本并保留失败样本供后续分析。
