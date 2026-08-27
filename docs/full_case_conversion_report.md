# Full Case Corpus Conversion Report

## 转换概览

- 输入：`<RELATED_PROJECT_ROOT>\data\processed\cases.jsonl`
- 输出：`<PROJECT_ROOT>\data\processed\full_cases\cases.jsonl`
- 输入记录数：**6492**
- 成功转换数量：**6492**
- 失败数量：**0**
- 转换过程未调用 LLM API。
- 当前 19 条案例库未被读取写入或覆盖。

## 字段完成率

完成率按成功转换记录计算；空字符串、空数组和 null 视为未完成。

| 字段 | 已完成数量 | 完成率 |
| --- | ---: | ---: |
| `case_id` | 6492 | 100.00% |
| `title` | 6492 | 100.00% |
| `court` | 6492 | 100.00% |
| `judgment_date` | 6492 | 100.00% |
| `basic_facts` | 6492 | 100.00% |
| `court_reasoning` | 6492 | 100.00% |
| `judgment_result` | 6492 | 100.00% |
| `legal_basis` | 6492 | 100.00% |
| `dispute_focus` | 6492 | 100.00% |
| `keywords` | 6492 | 100.00% |
| `raw_text` | 6492 | 100.00% |
| `source_file` | 6492 | 100.00% |

## 文本长度

- raw_text 平均长度：**1293.82** 字符
- raw_text 最短长度：**941** 字符
- raw_text 最长长度：**2767** 字符

## 转换规则

- `case_id`、`title`、`court`、`date`、`facts` 按要求映射到标准字段。
- `judgment` 同时保留到 `court_reasoning` 和 `judgment_result`，未对原文做主观拆分。
- `law_articles` 映射为 `legal_basis`。
- `legal_issues` 映射为 `dispute_focus`，并与 `law_articles` 合并生成 `keywords`。
- `raw_text` 按 title、facts、legal_issues、law_articles、judgment 分段组合，并保留字段标签。
- `source_file` 固定标记为 `labor_case_dataset_6492`。

## 失败记录

未发现失败记录。

生成时间：`2026-08-26 00:58:03 +0800`。