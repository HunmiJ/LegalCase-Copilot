# Full Case Evaluation Dataset Report

## 数据集概览

- 输入语料：`D:\Project\LegalCase-Copilot\data\processed\full_cases\cases.jsonl`
- full corpus 案例总数：**6492**
- query 数量：**30**
- 对应唯一案例数量：**30**
- 随机种子：`20260826`
- query 来源：原始案例字段 `legal_issues`、`facts`、`judgment` 的匹配片段；在标准化 full corpus 中分别对应 `dispute_focus`、`basic_facts`、`judgment_result`。
- LLM API 调用：0 次。

## 覆盖领域

| 领域 | query 数量 |
| --- | ---: |
| 违法解除 | 4 |
| 经济补偿 | 4 |
| 加班 | 4 |
| 工伤 | 4 |
| 未签劳动合同 | 4 |
| 竞业限制 | 4 |
| 欠薪 | 3 |
| 试用期 | 3 |

## 数据格式

输出文件只包含 `query` 和 `relevant_case_ids` 两个字段。每条 query 对应抽取案例的 `case_id` 作为相关案例标注。
现有 `evaluation/case_retrieval_queries.json` 未被修改。
