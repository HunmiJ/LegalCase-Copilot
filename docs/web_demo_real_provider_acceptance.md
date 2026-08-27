# Web Demo Real Provider Browser Acceptance

日期：2026-08-28
运行地址：`http://localhost:8503`
Provider 状态：页面显示“AI生成：DeepSeek”
验收范围：仅发送用户授权的两条测试问题及对应法规/案例 context；未发送 API Key、Authorization、Cookie、token、`.env` 内容或其他配置。

## 1. 测试矩阵

| 模式 | 测试问题 | 结果 | 页面状态 |
|---|---|---|---|
| 法规-only | 公司无正当理由辞退我，可以要求赔偿吗？ | 未生成成功 | AI 分析暂时未生成成功；retrieval-only |
| 法规-only | 工作一个多月还没有签劳动合同怎么办？ | 未生成成功 | AI 分析暂时未生成成功；retrieval-only |
| 法规 + 6492 类案 | 公司无正当理由辞退我，可以要求赔偿吗？ | 未生成成功 | AI 分析暂时未生成成功；保留 CASE-1/CASE-2 |
| 法规 + 6492 类案 | 工作一个多月还没有签劳动合同怎么办？ | 未生成成功 | AI 分析暂时未生成成功；保留 CASE-1/CASE-2 |

真实 provider 没有返回可验证的结构化成功结果，因此没有记录为成功，也没有创建 `real-*-success` 截图。

## 2. 页面检查结果

- `answer`：失败状态显示“AI总结生成暂时不可用”，没有用检索文本拼接伪造回答。
- `legal_analysis`：失败状态明确显示未生成；没有把检索证据冒充法律分析。
- LAW metadata：法规-only和案例增强 fallback 均可展开查看 LAW ID、法规名称、条号和正文。
- CASE metadata：案例增强 fallback 可展开查看 CASE ID、标题、法院、日期、争议焦点、裁判摘要和法律依据。
- `risk_note`：显示真实 fallback 风险提示及“不代表 AI 生成结论”。
- `confidence`：失败状态为 `low`，未伪造置信度。
- raw JSON / Python repr：未发现。
- debug 信息、API key、Authorization、Cookie、token：未发现。
- 文本溢出：未发现结构性横向溢出；长文本通过可折叠卡片展示。
- citation 错位：未发现；LAW 与 CASE 分区和编号正常。
- 过长文本：案例正文较长，但默认折叠，页面可读性可接受。

## 3. 浏览器端耗时

浏览器操作等待窗口设置为 90 秒；页面最终均完成并显示 fallback。页面内部显示的查询耗时为：

| 模式 | 问题 | 浏览器观测 | 页面内部查询耗时 |
|---|---|---:|---:|
| 法规-only | 辞退/赔偿 | 约 90.3 秒 | 12,822 ms |
| 法规-only | 未签劳动合同 | 约 90.3 秒 | 11,630 ms |
| 法规 + 6492 类案 | 辞退/赔偿 | 约 90.3 秒 | 27,728 ms |
| 法规 + 6492 类案 | 未签劳动合同 | 约 90.3 秒 | 33,949 ms |

浏览器观测时间包含等待窗口和 Streamlit 页面刷新，不应解读为纯 pipeline 耗时；页面内部计时更接近实际查询耗时。

## 4. Fallback 验收

真实 provider 失败时，页面同时显示：

> AI 分析暂时未生成成功。

以及：

> 以上为检索结果，不代表AI生成结论。

法规引用和案例引用仍来自本次真实检索 context，confidence 为 `low`，没有伪装成 AI 成功回答。

## 5. 截图

由于没有真实成功回答，以下是实际保存的真实 provider fallback 截图：

- `outputs/real-law-only-fallback.png`
- `outputs/real-case-augmented-fallback.png`
- `outputs/real-fallback.png`

没有生成 `real-law-only-success` 或 `real-case-augmented-success` 文件，以避免把失败结果误标为成功。

## 6. 测试与发布阻断

最终完整测试：

```text
174 passed, 1 warning
```

warning 是现有 `.pytest_cache` 目录写权限导致的 `PytestCacheWarning`。

当前仍存在一个发布阻断：真实 DeepSeek provider 在本次四条测试中均未产生可验证成功结果，因此无法完成“真实 AI 成功页面”的最终验收。前端安全 fallback 正常，不建议在未确认 provider 可用性前将页面宣称为完整 AI 成功 Demo。

本阶段未修改 retrieval、embedding、reranker、evaluation 或 6492 案例数据；未执行 commit、push 或 release。
