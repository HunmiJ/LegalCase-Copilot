# Final Schema Simplification Report

## 1. 变更范围

本阶段只调整 generation schema 的解析与安全适配，没有修改 retrieval、embedding、reranker、context budget、6492 案例数据、citation validator、article sanitizer 或 Web Demo。

## 2. 真实输出形态诊断

使用固定 5 条问题、法规-only 与法规+6492 案例两种模式，各重复 3 次；共 30 次真实 production generation。诊断仅记录结构摘要，不保存完整模型响应。

| 模式 | 记录到的 legal_analysis 形态 | provider/JSON 成功 attempt 数 |
|---|---|---:|
| law-only | string | 21 |
| law+6492-cases | string | 18 |

此前失败的代表性问题是：模型返回 `legal_analysis` 字符串，而旧适配器按 claim object 列表调用 `.get()`，导致结构契约失败。该路径现已改为明确的 schema failure，并支持 canonical string。

## 3. 唯一 canonical generation schema

```json
{
  "answer": "string",
  "legal_analysis": "string",
  "law_citations": ["LAW-1"],
  "case_citations": ["CASE-1"],
  "risk_note": "string",
  "confidence": 0.0
}
```

- `answer`、`legal_analysis`、`risk_note`：非空字符串。
- `law_citations`、`case_citations`：只允许当前 context 中真实存在的对应 namespace ID；law-only 允许 `case_citations: []`。
- `confidence`：0 到 1 的数字。
- 模型不生成法规名称、法条号、案例标题、法院或日期。
- citation validator 仍使用内存中的安全适配结构完成严格验证；该结构不作为模型契约暴露。

允许的安全 normalization 只有：

- `list[string]` → 用换行合并为一个分析字符串。
- 唯一字段的 `{"analysis": "..."}` → 提取为分析字符串。

无法无歧义解释的 nested object、缺失 `legal_analysis` 或非法 citation 仍拒绝。

## 4. 真实重复 smoke 结果

| 指标 | V1.5.8 基线 | law-only | law+6492-cases |
|---|---:|---:|---:|
| generation runs | 15 | 15 | 15 |
| final generation success rate | 0/15 | 14/15 = 0.9333 | 15/15 = 1.0000 |
| citation validity（成功响应） | — | 1.0000 | 1.0000 |
| sanitation events | — | 5 | 13 |
| unsupported citation failures | — | 0 | 0 |
| required/schema failure | 主要瓶颈 | 1 | 0 |
| generation_failed_after_retries | 15 | 1 | 0 |

阶段统计：

- law-only：provider/JSON 21 次成功，schema/citation 14 次成功。
- law+6492-cases：provider/JSON 18 次成功，schema/citation 15 次成功。
- `legal_analysis` shape 统计中全部为 `string`，本次没有发生 list/object normalization；支持的 normalization 分支已由回归测试覆盖。
- 失败响应没有被标记为成功；没有创建不存在的 citation。

## 5. 生成参数

- temperature：0
- timeout：30 秒
- retry count：2（每次 production generation 最多 3 次尝试）
- stream：false
- provider model：`deepseek-v4-flash`

## 6. 测试

新增和更新测试覆盖 canonical string、list[string] normalization、唯一 analysis object、nested object 拒绝、缺失字段、合法/非法 LAW/CASE ID、law-only fallback、真实 metadata 渲染和 sanitizer 不创建 citation。

最终完整 pytest：170 passed，1 warning。

## 7. 结论

schema failure 已从主要瓶颈显著下降；成功响应的 citation validity 保持 1.0，非法 citation 仍严格拒绝。两种模式均出现稳定成功结果，具备进入最终 30-query 正式评测的条件。

本阶段没有运行最终 30-query 正式评测；下一步应在用户确认后运行，并继续保留真实 provider 结果，不使用 mock 或人工伪造指标。
