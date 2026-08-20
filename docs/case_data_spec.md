# V0.7 Case Data Specification

## Scope

V0.7.0 只建立真实劳动争议案例语料的可追溯数据边界，不实现案例检索、case embeddings、BM25 case search、Case Reranker 或网页爬虫。

当前优先使用人民法院案例库中的劳动争议参考案例或指导性案例。案例应由人工获取和核验，不能由 LLM 生成或补写。

原始案例文件与主语料资格分开管理。所有人工取得的官方 PDF 都可以进入审计范围，但只有通过资格审查的民事劳动争议案例才进入 `data/processed/cases/cases.jsonl` 及其 BM25/semantic 主索引。刑事、主题明显不属于劳动民事类案检索的材料可保留为 `AUXILIARY_ONLY`，不进入主索引。

## Admission rules

允许进入项目的案例必须来自可核验的官方来源，属于劳动争议领域，并保留原始文件和完整 `raw_text`。不能进入项目的内容包括虚构案例、来源无法追溯的转载、只有摘要而没有原文的记录，以及无法确认属于劳动争议的材料。

## Fields

必填字段：`case_id`、`title`、`case_type`、`source_name`、`source_file`、`raw_text`。

可空字段：`case_number`、`court`、`judgment_date`、`basic_facts`、`dispute_focus`、`court_reasoning`、`judgment_result`、`case_gist`、`case_level`、`source_url`、`database_case_number`。`keywords`、`legal_basis` 与 `related_index` 使用空数组表示暂缺。官方案例库中稳定存在的裁判要旨、关联索引和入库编号分别保存为 `case_gist`、`related_index` 和 `database_case_number`；字段不能可靠确认时使用 `null` 或 `[]`，不得猜测。

## Corpus eligibility

`data/case_eligibility.json` 按 `source_file` 记录资格状态和理由。`corpus_status` 目前使用：

- `ELIGIBLE_MAIN_CORPUS`：进入正式 curated corpus、案例搜索和 case embeddings。
- `AUXILIARY_ONLY`：保留官方原始文件和审计信息，但不进入主语料或主索引。
- `REJECT`：不满足来源、完整性或范围要求；不得进入正式语料。

`data/case_metadata.json` 同步保存每条已审计记录的 `corpus_status` 与 `eligibility_reason`。缺少计划中的案例不创建空记录；例如没有取得 PDF 的编号仍只保留在收集计划中。

## Identity and traceability

`case_id` 是跨文件和处理阶段使用的稳定唯一 canonical identity，不能只使用标题。后续应优先依据官方案号、来源标识或经过记录的稳定组合生成，并人工复核。`source_file` 必须对应 `data/raw/cases/` 中的真实文件；`source_url`（如已确认）应能回溯到官方页面。

## Duplicates and processing

同一 `case_id` 不得重复。原始文件只读保存；结构化字段用于后续分析和检索，`raw_text` 与结构化字段分开保存，任何清洗都不能覆盖原文。Parser 可以审计全部 PDF，但正式输出只写入 `ELIGIBLE_MAIN_CORPUS` 记录；`AUXILIARY_ONLY` 不得混入 `cases.jsonl`。后续 processed case record 应保留 `case_id` 和 source traceability。

## Future Similar Case Retrieval

后续案例检索可使用 `title`、`keywords`、`basic_facts`、`dispute_focus`、`court_reasoning`、`judgment_result`、`legal_basis` 和 `raw_text` 的经审核版本。V0.7.0 不对这些字段建立索引、BM25 或向量。
