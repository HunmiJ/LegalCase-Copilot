# LegalCase Copilot

中文名称：智能法律类案检索与文书生成系统

## 项目简介

LegalCase Copilot 是一个面向法律场景的 AI 项目，目标是帮助用户进行法律法规检索、类案分析，并辅助生成法律文书。

## 当前阶段：V0.1

V0.1 聚焦于劳动争议领域，先建设法律法规数据库的原始资料目录，并为后续的数据处理与关键词检索做好项目结构准备。

当前阶段暂不实现 AI、RAG、Embedding、案例检索、前端界面或数据库代码，也不包含虚假的示例法律数据。

## 项目目标

- 整理劳动争议领域的法律法规原始资料
- 建立可扩展的后端、数据处理脚本和测试目录
- 为后续法律检索与法律智能应用奠定基础

## 后续计划

后续版本将逐步实现：

1. 法律法规数据清洗、解析与结构化
2. 基于关键词的法律检索
3. 类案检索
4. RAG（检索增强生成）能力
5. 法律文书生成与辅助编辑
6. 面向用户的前端界面

## 项目结构

```text
LegalCase-Copilot/
├─ backend/              # 后端代码（当前暂为空）
├─ data/
│  ├─ raw/
│  │  └─ laws/           # 原始法律法规文件
│  └─ processed/         # 处理后的数据（当前暂为空）
├─ scripts/              # 数据处理与维护脚本（当前暂为空）
├─ tests/                # 测试代码（当前暂为空）
├─ docs/                 # 项目文档
├─ .gitignore
├─ README.md
└─ requirements.txt
```

## 开发约定

原始法律法规资料应优先从中国官方法律网站获取，并在后续引入数据时记录来源和获取时间。当前仓库不包含任何虚假的法律法规示例文件。

## Current development status

The stable default retrieval pipeline is the V0.4 pipeline:

```text
BM25 + BGE Semantic Retrieval + Candidate Union + BAAI/bge-reranker-base
```

V0.5 Query Understanding and Query Expansion are retained as optional,
experimental retrieval enhancements. They are not the default retrieval path.
The V0.5.1 Real LLM validation showed complete candidate recall at @50, but
Recall@5 was unchanged and MRR was slightly below V0.4 while adding roughly
eight seconds of LLM latency. The project therefore does not claim a V0.5
final-ranking improvement.

The V0.5 mock benchmark and V0.5.1 Real LLM benchmark are separate artifacts.
Mock results are for deterministic development tests only and must not be
presented as real-model performance results. Real LLM outputs contain model
results and structured query understanding only; API keys are excluded from
source code, caches, reports, and Git.
