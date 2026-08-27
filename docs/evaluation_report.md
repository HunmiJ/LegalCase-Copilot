# Evaluation Report

## Purpose

This report consolidates the project's retrieval, reranking, grounded-generation, case-augmented RAG and safety experiments. Results are research evidence for the frozen corpora and query sets; they are not a guarantee of production legal accuracy.

## Data and benchmark scale

| Area | Corpus / queries | Notes |
|---|---:|---|
| Law retrieval | 372 law articles / 30 queries | Frozen law benchmark |
| Case retrieval | 19 curated cases / 30 queries | 19 main cases; one auxiliary case excluded |
| Case reranker | 19 cases / 12 blind validation queries | Cross-encoder validation |
| Grounded RAG | 20 queries | Deterministic mock evaluation |
| Case-Augmented RAG | 20 integrated queries | Law-only versus law-plus-case |
| Safety | 4 deterministic scenarios | Normal, empty context, out-of-domain, unsupported citation |

## Metric definitions

- **Recall@k**: proportion of queries with at least one relevant item in the first k results.
- **MRR**: mean reciprocal rank of the first relevant result.
- **Citation validity**: proportion of cited identifiers that resolve to the actual retrieved context and pass consistency checks.
- **Grounded claim rate**: proportion of generated legal claims carrying valid evidence citations.
- **Unsupported claim rate**: proportion of citations that do not resolve to the supplied context.
- **Refusal accuracy**: proportion of cases where the system refuses exactly when evidence is insufficient or the question is outside the supported domain.
- **Law/case recall**: recall measured independently against expected law names and expected case IDs.

## Law retrieval results

V0.7.6 held-out test, 10 queries:

| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 |
|---|---:|---:|---:|---:|---:|
| BM25 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9613 |
| Semantic | 0.9000 | 1.0000 | 1.0000 | 0.9500 | 0.9693 |
| Hybrid | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9920 |

The Full-30 descriptive hybrid result was Recall@1 0.9667, Recall@3 1.0000 and Recall@5 1.0000.

## Case retrieval results

V0.7.6 Full-30 descriptive benchmark:

| Method | Recall@1 | Recall@3 | Recall@5 | MRR | nDCG@5 |
|---|---:|---:|---:|---:|---:|
| BM25 | 0.8667 | 1.0000 | 1.0000 | 0.9222 | 0.9059 |
| Semantic | 0.9333 | 1.0000 | 1.0000 | 0.9667 | 0.9613 |
| Hybrid | 0.9667 | 1.0000 | 1.0000 | 0.9833 | 0.9718 |

The V0.7.7 blind reranker validation found hybrid Recall@1 1.0000 versus reranked Recall@1 0.9167 on 12 queries. Reranking improved no Top-1 result in that blind sample and broke one, so it remains an optional ranking component rather than an unconditional quality claim.

## Grounded RAG results

V0.6 deterministic evaluation:

| Metric | Result |
|---|---:|
| Citation validity | 1.0000 |
| Citation precision | 1.0000 |
| Grounded claim rate | 1.0000 |
| Unsupported citation rate | 0.0000 |
| Refusal / insufficient-evidence accuracy | 1.0000 |
| Grounded-query retrieval coverage | 0.6667 |

The real-LLM smoke artifact is kept separate from deterministic results. It reported 6/6 in-domain generation successes and 0 fallback among those in-domain queries, but it is a limited smoke test, not a broad performance benchmark.

## Case-Augmented RAG results

The V0.8 integrated evaluation used 20 labor-dispute questions:

| Mode | Law recall | Case recall | Citation validity | Grounded claim rate | Unsupported claim rate |
|---|---:|---:|---:|---:|---:|
| Law-only | 0.9750 | 0.0000 | 1.0000 | 1.0000 | 0.0000 |
| Law + case | 0.9750 | 0.9750 | 1.0000 | 1.0000 | 0.0000 |

The case-augmented mode added case recall without reducing law recall or citation validity. The generation component in this comparison is deterministic; human review is still required for substantive legal quality.

## Safety results

V0.9 deterministic safety smoke evaluation:

| Metric | Result |
|---|---:|
| Refusal accuracy | 1.0000 |
| Citation accuracy | 1.0000 |
| Unsupported claim rate | 0.0000 |

Scenarios cover a normal labor-law question, empty context, an out-of-domain question, and an unsupported citation. Safe refusal is intentionally conservative: the system states that it cannot provide a reliable answer from the current legal database.

## Limitations

- The legal corpus is limited to the collected and eligibility-approved materials.
- Case similarity is not legal authority and cannot establish a universal rule.
- Several benchmarks are small and frozen; descriptive full-set results are not independent test evidence.
- Deterministic providers evaluate orchestration and validation, not general language-model quality.
- Real legal use requires current-law verification, complete facts, evidence review and professional judgment.
