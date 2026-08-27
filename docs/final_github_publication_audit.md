# Final GitHub Publication Audit

日期：2026-08-28
审计范围：当前仓库、当前 Git history、公开 README 与 fresh-clone 静态复现条件

## Executive Summary

当前分支为 \`main\`，HEAD 为 \`d1bf02e\`，上一个后端基线 \`3f29c76\` 仍在历史中。当前唯一工作区修改是未提交的 \`README.md\`。未配置 Git remote，因此当前不存在 push 目标，也没有执行 remote 创建、push、tag 或 release。

当前 RC 可以进入 Final Cleanup，但还不能直接进行公开 GitHub Publication，原因见 BLOCKER。

## 1. Repository State

- Branch：\`main\`
- HEAD：\`d1bf02e feat: finalize production-ready Streamlit demo\`
- Backend baseline：\`3f29c76\`
- Remote：未配置（\`git remote -v\` 无输出）
- 工作区：仅 \`README.md\` modified，未 staged
- 近期 history：包含 \`d1bf02e\`、\`3f29c76\` 及此前带 tag 的开发提交
- 没有向第三方仓库 \`221130217/labor_case_dataset\` push 的配置或操作记录

## 2. Current Tracked Files and Credential Audit

当前 tracked 文件约 379 个。未发现 tracked 的 \`.env\`、私钥文件或凭据文件名。

当前内容扫描未发现已确认的真实：

- API key
- DeepSeek/OpenAI key
- token
- Cookie
- JWT
- password
- private key

代码中的 \`Authorization\` 仅用于 provider 请求头实现，API key 从环境变量读取，不是已提交 credential。README、验收报告和 provider 代码均未发现真实凭据值。

### Git history

- \`.env\` 从未出现在 Git history 文件路径中。
- 未发现已确认的历史真实 secret。
- 历史 pattern 扫描命中的是正常 provider/header 实现和测试占位文本，不足以认定为 credential。
- 未执行 filter-repo、filter-branch 或任何 history rewrite。

## 3. Local Privacy and Absolute Paths

tracked 仓库中发现本机绝对路径，主要位于历史分析文档和数据处理脚本：

- \`docs/full_case_source_location.md\`
- \`docs/full_case_conversion_report.md\`
- \`docs/full_case_schema_analysis.md\`
- \`docs/case_encoding_analysis.md\`
- \`evaluation/results/*.json\` 中的历史绝对路径
- \`scripts/analyze_case_encoding.py\`
- \`scripts/build_full_case_corpus.py\`
- \`scripts/inspect_full_case_schema.py\`
- 若干 collector/discovery 脚本

这些路径包含 \`<LOCAL_PROJECT_ROOT>\\\\...\`、\`<LOCAL_USER_HOME>\\\\...\` 或用户名/开发环境信息。README 当前已清理，不含这些路径；但它们仍存在于 tracked 文件中。

建议分类：

- README：已清理，适合保留。
- 架构、最终评测、Demo 文档：适合公开。
- 历史数据位置/转换报告：建议改为相对路径或泛化路径后公开。
- 内部 collector/debug/阶段性分析：建议作为 engineering notes 保留在单独位置，或从公开仓库排除。
- 不应直接删除；先做隐私清理清单并人工复核。

## 4. Repository Size and Large Objects

当前工作树约 85.9 MB，其中包含本地忽略的 full corpus 等运行时资产；Git 数据目录约 39.5 MB。

### Current tracked larger files

当前 tracked 文件中较大的主要是历史评测 JSON：

- \`evaluation/results/case_augmented_rag_metrics.json\`：约 2.99 MB
- \`evaluation/results/v0.4_reranker_results.json\`：约 2.87 MB
- \`evaluation/results/v0.5_query_understanding_results.json\`：约 1.79 MB
- \`evaluation/results/v0.3_retrieval_results.json\`：约 1.07 MB

当前 tracked 的小型运行资产包括：

- \`data/processed/embeddings.npy\`：约 0.76 MB
- \`data/processed/legal.db\`：约 0.59 MB
- 19-case \`cases.jsonl\`：约 0.27 MB
- 19-case embeddings：约 0.04 MB

当前没有发现 tracked 的 PDF 文件。

### Git history

Git history 仍包含：

- \`data/processed/full_cases/cases.jsonl\`：约 39.7 MB
- \`data/processed/full_cases/case_embeddings.npy\`：约 13.3 MB

当前版本已通过 \`.gitignore\` 排除这些路径，但它们仍可从 history 获取。公开仓库应在 push 前决定是否进行经授权的 history cleanup；本次未执行 rewrite。

## 5. 6,492-Case Corpus

当前版本没有 tracked 的：

- \`data/processed/full_cases/cases.jsonl\`
- full-case embeddings
- external raw \`labor_case_dataset\`

README 已说明 6,492 corpus 的公开数据来源、provenance/licensing 限制，以及原始 corpus/embeddings 不随 GitHub 发布。

但 fresh clone 缺少 full corpus 时，\`LegalRAGPipeline\` 的类案模式会在本地 provider 打开缺失文件时抛出错误；Demo 顶部状态仍按模式显示“6,492 条”，异常层可能只转成通用不可用/fallback 提示。需要在公开发布前确认并修复为明确的“full corpus 未安装/需配置 CASE_CORPUS_PATH”提示，避免产生 corpus 已存在的印象。

## 6. License and Provenance

- 根目录没有 \`LICENSE\` 文件。
- 项目源代码 license：未声明。
- 6 份法规文本：有来源/元数据文档，但未见统一的第三方再发布许可声明。
- 19-case curated corpus：有 provenance 字段和相关文档，但应逐项确认公开与再分发条件。
- 6,492 public dataset：README 已采用谨慎表述，并明确不随仓库发布；但外部数据 license/terms 仍需由发布者确认。

项目源代码 license 不应自动扩展到第三方法规或案例数据。建议在公开发布前选择并添加一个适用于源代码的 license，同时单独记录第三方数据使用边界；本次不自行添加。

## 7. README Consistency and Reproducibility

README 已正确覆盖：

- 372 条法规
- 6,492 案例
- 19-case curated benchmark
- BGE embedding retrieval
- \`BAAI/bge-reranker-base\` cross-encoder
- DeepSeek-compatible provider
- Final retrieval metrics
- Final generation metrics
- Streamlit Demo、截图和 8503 启动示例
- data availability、provenance 与 limitations

README 当前未明确写出 \`174 passed\` 测试结果，建议在最终发布文档中补充。README 的 Quick Start 依赖：

- Python environment
- \`requirements.txt\`
- \`frontend_demo/requirements.txt\`
- 本地模型下载或可用 cache
- 法规 embedding/index 与 19-case 小型数据
- 类案模式下另行配置 6,492 full corpus 及其 embeddings/index

README 已说明 full corpus 不随仓库发布，但还应在最终复现说明中写清所需外部文件和缺失 corpus 的行为。

相对链接检查通过；README 图片文件均存在：

- \`docs/images/demo-home.png\`
- \`docs/images/demo-law-only-success.png\`
- \`docs/images/demo-case-augmented-success.png\`
- \`docs/images/demo-fallback.png\`

## 8. Documentation Classification

建议公开仓库优先保留：

- \`docs/architecture.md\`
- \`docs/evaluation_report.md\`
- \`docs/final_30_query_real_evaluation.md\`
- \`docs/demo.md\`
- \`docs/data_sources.md\`
- \`docs/case_data_spec.md\`
- final UX/provider/parity/release reports

建议作为 engineering notes 集中归档或减少首页曝光：

- \`docs/v1.5*.md\`
- \`docs/v0.6*.md\`
- \`docs/full_case_*_analysis.md\`
- provider stability、context stress、exact prompt transport 等阶段性 diagnosis
- collector/discovery 的内部操作说明

这不是为了隐藏失败，而是避免公开首页和主文档充斥流水账；最终评测和安全限制应保留。

## 9. Severity

### BLOCKER

1. Git history 仍包含不应公开的 6,492 full corpus 和 full-corpus embeddings。公开 push 前必须由仓库所有者决定并授权 history cleanup，或明确接受这些历史对象可被 clone 恢复的风险。
2. Fresh clone 缺少 full corpus 时，类案 Demo 的状态文案/异常路径需要确认不会让用户误以为 6,492 corpus 已可用；当前静态代码显示存在“显示已启用但实际文件缺失”的风险。

### SHOULD FIX

1. 添加适用于项目源代码的 LICENSE，并单独说明第三方数据不受项目 license 覆盖。
2. 清理或泛化 tracked 历史文档、脚本和 JSON 中的本机绝对路径及用户名。
3. 核验 19-case curated artifacts、法规文本和 raw/source metadata 的再分发条件。
4. README 补充 174 tests、模型下载/cache、法规 embedding/index 和外部 full corpus 的复现前置条件。
5. 对旧 V0/V1.5 阶段性诊断文档进行 engineering-notes 归档或公开范围整理。
6. 当前没有 remote；创建 remote 前必须由用户提供并确认自己的 GitHub repository URL。
7. 评测历史 JSON 体积偏大，可考虑保留最终指标与摘要，降低公开仓库体积。

### ACCEPTABLE LIMITATION

1. 自动评测不等价于专业律师人工法律正确性审查。
2. full-corpus retrieval 主要基于弱监督/自动指标。
3. 类案增强延迟较高。
4. 真实 provider 需要网络访问和本地凭据配置。
5. 6,492 corpus 与 embeddings 不随仓库发布，只要 README 保持当前 provenance/licensing 说明即可。
6. 小型 19-case benchmark、法规 embeddings 和 \`legal.db\` 可以作为可复现实验资产保留，但仍需遵守各自来源条款。

## Final Recommendation

当前不建议直接公开 push。可以进入 Final Cleanup + Commit，但在 GitHub Publication 前必须先处理两个 BLOCKER，并建议完成 SHOULD FIX 项。

当前未执行 commit、push、tag、release 或 history rewrite。

## Post-cleanup update

本报告原始结论形成后，已完成以下授权清理：

- 使用项目外本地 Git bundle 完成备份并验证可读。
- 使用 `git-filter-repo` 从可达 history 移除 `data/processed/full_cases/` 下的 cases、embeddings、index。
- 删除 4 个未被重写的内部 checkpoint refs；上述 full-corpus blobs 经 GC 后已不再存在于可达或本地对象库。
- 从公开 history/tree 移除 raw case PDF；因既有 19-case 回归测试依赖这些小型 curated fixtures，已从备份恢复到当前 tree，作为待许可核验的测试资产保留。
- 添加 MIT `LICENSE`，并明确其仅适用于原创源代码，不扩展到第三方数据、法规或裁判文书。
- Demo 增加 full-corpus availability check；缺少 6,492 corpus 时仅保留法规-only，并显示明确提示。
- tracked 文本中的本机绝对路径已替换为占位符。

验证结果：`pytest tests` 为 `175 passed, 1 warning`；fresh-clone 静态模拟的 `full_case_corpus_available` 为 `False`。

rewrite 后的 Git 对象库约 2.96 MB，`git rev-list --objects --all` 不再包含 full corpus 或 raw case PDF 路径。当前仍需在公开发布前确认 curated raw PDF 与法规文件的第三方再分发条款，并决定是否进一步归档阶段性 engineering notes。

## Final cleanup state

- History sanitization：成功；原 full corpus 三个 blob 已不可达，并在 GC 后从本地对象库清除。
- Current tree：未包含 `data/processed/full_cases/`；未包含 6,492 full-corpus embeddings；未包含 external 6,492 raw dataset。
- Curated fixtures：恢复并保留 20 个小型 curated raw case PDFs，因为现有 19-case regression tests 依赖其输入；其公开再分发许可仍是 SHOULD FIX。
- Fresh-clone UX：缺少 full corpus 时，Demo 只暴露法规-only 并显示明确未安装提示。
- LICENSE：已添加 MIT，明确不覆盖第三方数据和法律原文。
- README：已补充外部 corpus 前置条件、指标解释、截图和启动方式。
- pytest：`175 passed, 1 warning`。
- 当前没有 remote，未执行 commit、push、tag 或 release。

Remaining publication recommendation：在公开 push 前完成 curated fixtures 的许可核验、阶段性 docs 归档和用户 GitHub remote 确认。历史大对象和本机路径两个 BLOCKER 已处理。

## Final verification after cleanup commit

- Cleanup commit：当前 HEAD，提交说明为 `chore: prepare repository for public release`
- Workspace：clean
- Current branch：`main`
- Remote：未配置
- `pytest tests`：`175 passed, 1 warning`
- `git diff --check`：通过；仅保留 LF/CRLF 转换提示
- Reachable full-corpus paths：0
- Old full-corpus blob IDs：经 GC 后未发现
- Current curated raw PDFs：20 个小型 benchmark fixtures；不包含 6,492 production corpus
- Current `.git` directory：约 9.25 MB（包含 Git metadata/logs；pack object store 约 2.96 MB）

Effective BLOCKER count：0。Remaining SHOULD FIX items are third-party fixture/licensing confirmation, optional engineering-notes curation, and confirmation of the user-owned GitHub remote URL. Do not push until those publication decisions are made.
