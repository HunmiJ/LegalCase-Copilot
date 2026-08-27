# Public Evaluation Data Policy

The public repository retains the evaluation code, project-authored query definitions, aggregate metrics, sanitized per-query metadata, and failure taxonomy needed to understand and reproduce the evaluation design.

Evaluation artifacts are sanitized before publication. Third-party statutory text, court-case full text, retrieved full context, and raw prompts or model responses containing that material are not distributed. Public JSON artifacts retain audit-friendly fields such as query identifiers, query text, modes, citation identifiers, labels, status, latency, provider/model metadata, and failure reasons when available.

This boundary is based on provenance, redistribution rights, and repository hygiene. It is not intended to hide failures or alter results. Sanitization removes text payloads only; frozen aggregate metrics and the evaluation definitions remain unchanged. Automatic metrics are not legal advice, expert legal correctness judgments, or guarantees for arbitrary questions.

The 6,492-case production corpus and its generated embeddings remain external. Raw law documents, raw court materials, complete derived law records, and complete derived case records are also excluded unless redistribution rights are clear. Users must obtain external material lawfully and prepare it according to the documented schemas and processing pipeline.

The checked-in synthetic case fixture is fully synthetic and is used only for public-clone tests. It is not a real judicial case and must not be interpreted as one.

Tests that require excluded external data are explicitly skipped when those inputs are absent. Unit tests and synthetic-fixture contract tests remain runnable from a public clone.
