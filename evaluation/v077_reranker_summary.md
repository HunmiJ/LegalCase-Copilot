# V0.7.7 Cross-Encoder Case Reranker

Model: `BAAI/bge-reranker-base`; candidate depth: 3; validation queries: 12.

## Blind validation

| Method | Recall@1 | Recall@3 | MRR | nDCG@3 | Avg ms | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| hybrid | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 11.88 | 10.76 | 23.43 |
| reranked | 0.9167 | 1.0000 | 0.9583 | 0.9626 | 741.43 | 715.16 | 847.97 |

Fixed: 0; broken: 1; unchanged: 11; net Top1 gain: -1.

## Full-30 descriptive comparison

| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 | Avg total ms |
|---|---:|---:|---:|---:|---:|---:|
| hybrid | 0.9667 | 1.0000 | 1.0000 | 0.9833 | 0.9673 | 10.58 |
| reranked | 0.9667 | 1.0000 | 1.0000 | 0.9833 | 0.9466 | 733.97 |

The V0.7.6 held-out Test is not relabeled as a new V0.7.7 independent test. No query-specific rule, label change, or corpus change was used.
