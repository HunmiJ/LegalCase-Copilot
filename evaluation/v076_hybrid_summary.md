# V0.7.6 Hybrid Case Retrieval

Selection uses Dev=20 only. Test=10 is evaluated only after configuration freeze.

## Frozen configuration

```json
{
  "method": "weighted",
  "rrf_k": null,
  "semantic_weight": 0.8,
  "bm25_top_k": 10,
  "semantic_top_k": 10,
  "selection_split": "dev",
  "selection_priority": [
    "Recall@1",
    "MRR",
    "nDCG@5",
    "prefer_rrf_on_tie"
  ]
}
```

## Dev baseline

| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 | Avg ms | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bm25 | 0.8000 | 1.0000 | 1.0000 | 0.8833 | 0.8782 | 0.64 | 0.58 | 0.87 |
| semantic | 0.9500 | 1.0000 | 1.0000 | 0.9750 | 0.9572 | 10.88 | 10.21 | 11.89 |

## Test baseline

| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 | Avg ms | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bm25 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9613 | 0.67 | 0.67 | 0.90 |
| semantic | 0.9000 | 1.0000 | 1.0000 | 0.9500 | 0.9693 | 10.79 | 11.12 | 12.31 |

## Held-out Test

| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 | Avg ms | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bm25 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9613 | 0.67 | 0.67 | 0.90 |
| semantic | 0.9000 | 1.0000 | 1.0000 | 0.9500 | 0.9693 | 10.79 | 11.12 | 12.31 |
| hybrid | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9920 | 11.60 | 12.07 | 13.01 |

## Full-30 descriptive result

| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 | Avg ms | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bm25 | 0.8667 | 1.0000 | 1.0000 | 0.9222 | 0.9059 | 0.65 | 0.59 | 0.90 |
| semantic | 0.9333 | 1.0000 | 1.0000 | 0.9667 | 0.9613 | 10.85 | 10.40 | 12.31 |
| hybrid | 0.9667 | 1.0000 | 1.0000 | 0.9833 | 0.9718 | 11.65 | 11.13 | 13.03 |

## Limitations

Semantic V0.7.5 already has Full-30 Recall@1=0.9333, so the improvement ceiling is small. This benchmark does not use query-specific rules, LLM expansion, reranking, or frozen-label changes. Full-30 is descriptive after Dev selection, not an independent held-out test.

## Failure/disagreement audit

- `cq05` 外卖平台说我是承揽关系，但一直用规则和算法管我，算劳动关系吗: BM25 rank 2, Semantic rank 1; Top1 disagreement or miss; relevant candidate remains in top10
- `cq12` 单位长期少发工资，我提出解除劳动合同能拿经济补偿吗: BM25 rank 3, Semantic rank 1; Top1 disagreement or miss; relevant candidate remains in top10
- `cq15` 我和公司签的是合作协议，但实际每天受管理，能确认劳动关系吗: BM25 rank 2, Semantic rank 2; Top1 disagreement or miss; relevant candidate remains in top10
- `cq23` 公司让我休息日工作，既有考勤又在手机上处理事情，应该按哪种加班判断: BM25 rank 1, Semantic rank 1; Top1 disagreement or miss; relevant candidate remains in top10
- `cq24` 签了竞业限制并拿了补偿，普通员工去了竞争单位被索赔: BM25 rank 1, Semantic rank 1; Top1 disagreement or miss; relevant candidate remains in top10
- `cq25` 公司说员工有问题就辞退，怎样判断属于违法解除: BM25 rank 3, Semantic rank 1; Top1 disagreement or miss; relevant candidate remains in top10
- `cq27` 公司少交社保让我权益受损，我能否解除并要求补偿或待遇差额: BM25 rank 1, Semantic rank 1; Top1 disagreement or miss; relevant candidate remains in top10
- `cq30` 多年欠薪后解除合同，经济补偿的年限和是否必须仲裁怎么判断: BM25 rank 1, Semantic rank 2; Top1 disagreement or miss; relevant candidate remains in top10
