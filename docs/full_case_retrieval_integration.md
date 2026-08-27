# Full Case Retrieval Integration

## 配置方式

案例检索服务通过 `CASE_CORPUS_PATH` 选择 corpus 目录：

```text
CASE_CORPUS_PATH=data/processed/cases
CASE_CORPUS_PATH=data/processed/full_cases
```

也可以在 Python 中传入 `UnifiedCaseSearchService(corpus_path=...)`。

未设置配置时，默认继续使用 benchmark corpus：

```text
data/processed/cases/
```

## 统一 artifact 解析

选定 corpus 目录后，服务自动使用同一目录下的：

- `cases.jsonl`：BM25 与记录加载
- `case_embeddings.npy`：Semantic embedding 矩阵
- `case_embedding_index.json`：Semantic case_id 索引

full corpus 配置对应：

```text
data/processed/full_cases/cases.jsonl
data/processed/full_cases/case_embeddings.npy
data/processed/full_cases/case_embedding_index.json
```

## 兼容性

- 默认行为保持 benchmark corpus，不影响既有调用方式。
- BM25、Semantic、Hybrid、Reranked provider 复用原有检索实现。
- 返回结果继续使用 `CaseSearchResult`。
- 未修改 embedding 算法、法规 RAG 或现有 19 条案例数据和 embedding。
