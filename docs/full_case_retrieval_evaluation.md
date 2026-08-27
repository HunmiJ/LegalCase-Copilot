# Full Case Corpus Retrieval Evaluation

## 评测设置

- full corpus：`data/processed/full_cases/cases.jsonl`
- corpus 数量：**6492**
- ground truth：`evaluation/full_case_retrieval/full_case_queries.json`
- query 数量：**30**
- 每种方法返回 top-10 候选。
- 所有 ground-truth case_id 均存在于 full corpus，Recall 为真实计算结果。

## Full Corpus 指标

| Method | Recall@1 | Recall@3 | Recall@5 | 平均检索耗时（ms） | 平均候选数量 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.8667 | 0.9333 | 0.9333 | 137.11 | 10.00 |
| Semantic | 0.5333 | 0.5667 | 0.6000 | 29.25 | 10.00 |
| Hybrid | 0.9000 | 0.9333 | 0.9333 | 166.40 | 10.00 |
| Reranker | 0.8333 | 0.9333 | 0.9333 | 1056.98 | 3.00 |

## 与 19 条 Benchmark Corpus 对比

以下 benchmark 数值来自上一阶段同一 30 条 benchmark 测试集；full corpus 使用本阶段独立 ground truth，因此两者用于结果参考，不能视为同一标注集上的严格因果对比。

| Corpus | Method | Recall@1 | Recall@3 | Recall@5 | 平均耗时（ms） | 平均候选数量 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| benchmark-19 | BM25 | 0.8667 | 1.0000 | 1.0000 | 0.62 | 10.00 |
| full-6492 | BM25 | 0.8667 | 0.9333 | 0.9333 | 137.11 | 10.00 |
| benchmark-19 | Semantic | 0.9333 | 1.0000 | 1.0000 | 11.25 | 10.00 |
| full-6492 | Semantic | 0.5333 | 0.5667 | 0.6000 | 29.25 | 10.00 |
| benchmark-19 | Hybrid | 0.9667 | 1.0000 | 1.0000 | 12.25 | 10.00 |
| full-6492 | Hybrid | 0.9000 | 0.9333 | 0.9333 | 166.40 | 10.00 |
| benchmark-19 | Reranker | 0.9667 | 1.0000 | 1.0000 | 887.03 | 3.00 |
| full-6492 | Reranker | 0.8333 | 0.9333 | 0.9333 | 1056.98 | 3.00 |

## 说明

本阶段使用独立 full corpus ground truth，所有无法召回的情况均保留为真实未命中并计入分母，没有将其过滤或改写为不可评估。
未修改 retrieval、embedding、RAG pipeline、19 条 benchmark 数据或 6492 条 corpus 数据。
