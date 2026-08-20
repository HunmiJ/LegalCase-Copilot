# V0.7.5 Case Retrieval Benchmark Summary

Frozen corpus: 19 main curated cases; benchmark queries: 30; top-k: 10.

| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 | Avg ms | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BM25 | 0.8667 | 1.0000 | 1.0000 | 0.9222 | 0.9059 | 0.49 | 0.47 | 0.76 |
| Semantic | 0.9333 | 1.0000 | 1.0000 | 0.9667 | 0.9613 | 12.46 | 9.68 | 22.77 |

Classification: SUCCESS means the first relevant case is rank 1; RANKING_MISS means relevant appears in ranks 2-5; TOP5_MISS means no relevant case appears in the top 5.

Frozen query SHA-256: `f577de865360e923266ea9975de8ee0b7ef429630be8225a774ba4f797673305`

## Representative failures or disagreements

- **cq05** 外卖平台说我是承揽关系，但一直用规则和算法管我，算劳动关系吗 — BM25 `RANKING_MISS` (primary rank 2), Semantic `SUCCESS` (primary rank 1); relevant `2024-18-2-186-001`.
- **cq12** 单位长期少发工资，我提出解除劳动合同能拿经济补偿吗 — BM25 `RANKING_MISS` (primary rank 3), Semantic `SUCCESS` (primary rank 1); relevant `2023-16-2-186-002`.
- **cq15** 我和公司签的是合作协议，但实际每天受管理，能确认劳动关系吗 — BM25 `RANKING_MISS` (primary rank 2), Semantic `RANKING_MISS` (primary rank 2); relevant `2022-18-2-186-001`.
- **cq25** 公司说员工有问题就辞退，怎样判断属于违法解除 — BM25 `RANKING_MISS` (primary rank 9), Semantic `SUCCESS` (primary rank 1); relevant `2024-18-2-490-003, 2013-18-2-186-001, 2026-07-2-533-003`.
- **cq30** 多年欠薪后解除合同，经济补偿的年限和是否必须仲裁怎么判断 — BM25 `SUCCESS` (primary rank 1), Semantic `RANKING_MISS` (primary rank 2); relevant `2023-07-2-186-010, 2023-16-2-186-002`.
