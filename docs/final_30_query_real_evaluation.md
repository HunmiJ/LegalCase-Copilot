# Final 30-Query Real Generation Evaluation

## 实验环境

- 固定测试问题：30 条；模式：法规-only、法规+6492 cases；总 production generation：60 次。
- 当前最终链路：retrieval → reranker → generation context budget → DeepSeek → JSON parser → schema normalization → article sanitizer → citation validator → deterministic citation metadata rendering。
- provider：`real_llm`；model：`deepseek-v4-flash`。
- 生成参数：temperature `0`，timeout `30.0s`，retry `2`，stream `False`。

## 指标对比

| 指标 | law-only | law+6492-cases |
|---|---:|---:|
| generation_success_rate | 0.8667 | 0.9667 |
| citation_validity | 1.0 | 1.0 |
| unsupported_citation_count | 0 | 0 |
| unsupported_citation_rate | 0.0 | 0.0 |
| schema_failure_count（underlying） | 4 | 1 |
| schema_failure_rate（underlying） | 0.1333 | 0.0333 |
| article_sanitation_count | 4 | 1 |
| article_sanitation_rate | 0.1333 | 0.0333 |
| generation_failed_after_retries_count | 4 | 1 |
| generation_failed_after_retries_rate | 0.1333 | 0.0333 |
| average_latency_ms | 16912.15 | 36511.08 |
| p50_latency_ms | 14898.03 | 35335.82 |
| p95_latency_ms | 29102.47 | 48347.41 |
| legal_basis_accuracy | 0.6154 | 0.6552 |
| case_reference_accuracy | 0.0 | 0.2126 |
| unsupported_claim_rate | 0.0 | 0.0 |

所有失败样本均保留在分母中。`citation_validity` 仅对成功响应求均值；无成功响应时显示为 `—`。

案例增强相对 law-only：generation success rate 增加 0.1000；平均延迟增加 19,598.93 ms（约 115.89%）；P50 增加 20,437.79 ms；P95 增加 19,244.94 ms。条号 sanitation 从 4 个事件降至 1 个事件。underlying schema failure 从 4 次降至 1 次。

`generation_failed_after_retries` 是最终用户可见失败分类；schema failure 同时作为 retry 过程中的 underlying failure 统计，因此两者不是同一组互斥计数。

## Failure taxonomy

### law-only

- final taxonomy：`{"generation_failed_after_retries": 4}`
- underlying taxonomy：`{"schema_failure": 4}`

### law+6492-cases

- final taxonomy：`{"generation_failed_after_retries": 1}`
- underlying taxonomy：`{"schema_failure": 1}`

## 结果解释

报告不预设案例增强一定改善结果。应重点比较成功率、citation validity、条号 sanitation、失败类型和延迟；案例是否进入答案仅以模型实际选择并通过 validator 的 CASE citation 及其确定性 metadata 为准，未被模型引用的案例不会计入引用。

## 自动评测限制

- legal_basis_accuracy 仅验证引用法规与expected_laws名称的自动匹配，不是人工法律正确率。
- case_reference_accuracy 仅验证被引用案例元数据/文本与expected_case_topics的自动词项匹配，不是专家判定的类案相似度。
- unsupported_claim_rate 来自自动citation/claim validator，不是人工逐句事实核验。
- 本评测未保存完整prompt、context或LLM response，也未使用mock、人工补写或失败样本排除。

逐问题安全摘要保存在 `evaluation/full_case_augmented_rag/final_generation_metrics.json`，不包含完整模型输出或完整 context。
