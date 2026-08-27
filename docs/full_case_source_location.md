# Full Case Corpus Source Location

## 定位结论

已找到与“6492 条劳动争议案例”数量吻合的数据源：

```text
<RELATED_PROJECT_ROOT>\data\processed\cases.jsonl
```

- 文件大小：16,343,803 bytes（约 15.59 MiB）
- JSON 记录数量：6,492
- 数据结构：每行一条 JSON object
- 主要字段：`case_id`、`title`、`court`、`date`、`case_type`、`facts`、`legal_issues`、`law_articles`、`judgment`

## 前 3 条案例 title

以下内容为文件中实际读取到的原始值：

1. `�����к��������޹�˾��������Ͷ�����һ�������о���`
2. `κ�߷����������ν������������޹�˾�Ͷ�����һ�������о���`
3. `��������Զ�̽����������޹�˾����Դ�Ͷ�����һ�������о���`

注意：上述 title 中存在大量 `�` 替换字符，说明该数据源的文本编码或历史转换过程存在损坏。记录数量和字段结构可以读取，但在接入前应先进行编码质量专项处理。

## 与当前 19 条案例的重复检查

当前项目案例文件：

```text
<PROJECT_ROOT>\data\processed\cases\cases.jsonl
```

- 当前案例数量：19
- 对比字段：`title + court`
- 重复记录数量：0
- 重复键组数量：0

结论：按当前可读取的 `title+court` 字段，该 6492 条数据源与当前 19 条案例未发现重复。

## 其他高容量案例数据文件

扫描 `<LOCAL_PROJECT_ROOT>` 后还发现以下案例数据文件：

| 文件 | 大小（bytes） | JSON 记录数 | 与当前 19 条重复 |
| --- | ---: | ---: | --- |
| `<EXTERNAL_DATA_ROOT>\json\2021_structure.jsonl` | 201,170,088 | 30,331 | 否 |
| `<EXTERNAL_DATA_ROOT>\json\2022_structure.jsonl` | 515,481,387 | 77,412 | 否 |
| `<EXTERNAL_DATA_ROOT>\json\2023_structure.jsonl` | 211,534,670 | 32,332 | 否 |
| `<EXTERNAL_DATA_ROOT>\json\2024_structure.jsonl` | 43,650,803 | 6,492 | 否 |
| `<EXTERNAL_DATA_ROOT>\json\2024_structure_remain.jsonl` | 35,874,566 | 5,311 | 否 |
| `<EXTERNAL_DATA_ROOT>\json\2024_structure_test.jsonl` | 7,776,237 | 1,181 | 否 |

这些分片文件采用嵌套结构，案例标题位于 `original_data.title`，而不是顶层 `title`。其中 `2024_structure.jsonl` 同样包含 6,492 条记录，但本次定位到的项目历史处理结果是 `legal-rag-system` 下的 `cases.jsonl`。

## 扫描范围与状态

- 扫描范围：`<PROJECT_ROOT>`、`<LOCAL_PROJECT_ROOT>`
- 扫描类型：`*.json`、`*.jsonl`、`cases.jsonl`、`case*.jsonl` 及高容量 JSON 文件
- 未修改任何已有文件
- 未修改 backend、RAG pipeline、retrieval、embedding 或现有 19 条案例库
