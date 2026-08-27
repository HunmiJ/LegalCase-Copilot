# Full Case-Augmented RAG Evaluation

## 评测设置

- 测试集：`evaluation/case_augmented_rag/integrated_queries.json`（20 条）
- before：19 条 benchmark cases
- after：6492 条 full cases
- 检索和 context 构建使用真实 corpus；未调用 LLM API。

## 指标

| 模式 | law_recall | case_recall | citation_validity | grounded_claim_rate | unsupported_claim_rate | case label coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| before_19_cases | 0.9750 | 0.9750 | 1.0000 | 1.0000 | 0.0000 | 20/20 |
| after_6492_cases | 0.9750 | — | 1.0000 | 1.0000 | 0.0000 | 0/20 |

## 解释

`case_recall` 只对 expected case_id 出现在当前 corpus 的 query 计算；没有可对应标注的 query 显示为 `—`，不将标注缺失误判为检索失败。full corpus 的独立真实召回结果见 `docs/full_case_retrieval_evaluation.md`。
`citation_validity`、`grounded_claim_rate` 和 `unsupported_claim_rate` 是 context evidence 层指标：检查 LAW/CASE namespace、context 文本完整性和无证据 context 比例，不冒充 LLM 生成质量。
