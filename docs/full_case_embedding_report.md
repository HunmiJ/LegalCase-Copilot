# Full Case Corpus Embedding Report

## 构建结果

- 输入语料：`data/processed/full_cases/cases.jsonl`
- 向量文件：`data/processed/full_cases/case_embeddings.npy`
- 索引文件：`data/processed/full_cases/case_embedding_index.json`
- 案例数量：**6492**
- 成功数量：**6492**
- 失败数量：**0**
- embedding 模型：`BAAI/bge-small-zh-v1.5`
- embedding 维度：**512**
- embedding 矩阵形状：`(6492, 512)`

## 性能

- 总耗时：**286.22 秒**
- 平均每案例耗时：**约 44.08 毫秒**
- 运行环境：CPU，本地模型文件

## 实现复用

本次直接复用现有 `scripts/build_case_embeddings.py`，通过命令行参数指定 full corpus 的输入、输出和索引路径；没有复制 embedding 逻辑，也没有修改 19 条案例的 embedding 文件。

embedding 文本构建继续使用 `backend.cases.search.semantic.case_embedding_text`，模型加载继续使用 `scripts.semantic_utils.load_model(local_files_only=True)`。

## 校验结果

- embedding 文件包含 6492 行向量。
- 向量维度为 512。
- 索引包含 6492 条记录。
- 索引 position 从 0 到 6491 连续。
- full corpus 的 case_id 与 embedding index 一一对应。
- 原有 `data/processed/cases/` 目录下的 19 条案例及其 embedding 未修改。
