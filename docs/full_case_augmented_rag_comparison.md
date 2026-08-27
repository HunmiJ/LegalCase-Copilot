# V1.4.1 Full Corpus Augmented RAG Evaluation

## 实验设置

- 评测问题：32 条，来自 `full_case_rag_queries.json`，覆盖八类劳动争议，每类4条。
- A：19条 benchmark cases；B：6492条 full cases。
- 两种模式使用相同问题、法规检索器和案例检索配置；full corpus 使用已生成的优化向量配置（`CASE_SEMANTIC_WEIGHT=0.2`）。

## 指标对比

| 指标 | 19 cases | 6492 cases |
|---|---:|---:|
| law_recall | 0.5365 | 0.5365 |
| case_recall | — | 0.0 |
| citation_validity | 1.0 | 1.0 |
| grounded_claim_rate* | 1.0 | 1.0 |
| unsupported_claim_rate* | 0.0 | 0.0 |
| generation_success_rate | — | — |

`*` `grounded_claim_rate` 和 `unsupported_claim_rate` 是证据上下文覆盖率代理指标：统计构建出的 context item 是否有非空证据文本，**不是**对最终 LLM 句子逐条核验。

## 公平性与限制

本次 query 的 `expected_cases` 来自 full corpus 的真实 `case_id`。因此 19-case benchmark 对这些标签没有覆盖，A 的 `case_recall` 显示为 `—`（而不是伪造为0）；A/B 的案例召回不能直接比较。full corpus 的案例标签覆盖数为 32/32，benchmark 为 0/32。

`generation_success_rate` 显示为 `—`。本评测没有调用真实 LLM provider，也没有人工/标准参考答案；用 mock 或规则拼接会掩盖真实生成失败，不能代表最终回答质量。因此本报告只报告法规召回、案例标签覆盖下的案例召回和 context/citation 完整性。要完成最终 RAG 质量比较，需要固定 provider/model、记录真实结构化响应，并为每条问题建立参考答案或人工标注。

## 结果解读

法规检索两组共享同一法规检索器，理论上法规指标应基本一致；案例库扩大后只能在有 full-corpus 标注覆盖的问题上评估 case recall。citation validity 反映 LAW/CASE namespace 是否隔离，不等同于法律结论正确性。任何“6492案例提升了最终回答质量”的结论，需在补齐真实生成和人工标注后再下结论。

原始指标 JSON：`evaluation/full_case_augmented_rag/full_case_rag_metrics.json`。
