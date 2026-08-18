# V0.7 Case Data Specification

## Scope

V0.7.0 只建立真实劳动争议案例语料的可追溯数据边界，不实现案例检索、case embeddings、BM25 case search、Case Reranker 或网页爬虫。

当前优先使用人民法院案例库中的劳动争议参考案例或指导性案例。案例应由人工获取和核验，不能由 LLM 生成或补写。

## Admission rules

允许进入项目的案例必须来自可核验的官方来源，属于劳动争议领域，并保留原始文件和完整 `raw_text`。不能进入项目的内容包括虚构案例、来源无法追溯的转载、只有摘要而没有原文的记录，以及无法确认属于劳动争议的材料。

## Fields

必填字段：`case_id`、`title`、`case_type`、`source_name`、`source_file`、`raw_text`。

可空字段：`case_number`、`court`、`judgment_date`、`basic_facts`、`dispute_focus`、`court_reasoning`、`judgment_result`、`case_level`、`source_url`。`keywords` 与 `legal_basis` 使用空数组表示暂缺。字段不能可靠确认时使用 `null` 或 `[]`，不得猜测。

## Identity and traceability

`case_id` 是跨文件和处理阶段使用的稳定唯一 canonical identity，不能只使用标题。后续应优先依据官方案号、来源标识或经过记录的稳定组合生成，并人工复核。`source_file` 必须对应 `data/raw/cases/` 中的真实文件；`source_url`（如已确认）应能回溯到官方页面。

## Duplicates and processing

同一 `case_id` 不得重复。原始文件只读保存；结构化字段用于后续分析和检索，`raw_text` 与结构化字段分开保存，任何清洗都不能覆盖原文。后续 processed case record 应保留 `case_id` 和 source traceability。

## Future Similar Case Retrieval

后续案例检索可使用 `title`、`keywords`、`basic_facts`、`dispute_focus`、`court_reasoning`、`judgment_result`、`legal_basis` 和 `raw_text` 的经审核版本。V0.7.0 不对这些字段建立索引、BM25 或向量。
