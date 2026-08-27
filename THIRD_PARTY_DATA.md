# Third-Party Data and Provenance Boundary

This repository's MIT License applies only to original project source code. It does not grant redistribution rights for third-party datasets, regulations, court judgments, reference case materials, source documents, or generated data artifacts.

## Excluded production data

The 6,492-case production corpus, its generated embeddings and indexes, and any external raw labor-case dataset are not distributed with this repository. They must be obtained and prepared by the user from a lawful source with appropriate redistribution and processing rights.

## Curated case benchmark

The 19-case curated benchmark structured records are not distributed. The repository retains only eligibility metadata, source URL/provenance tables, collection planning, processing code, and a clearly labeled synthetic fixture. The source list in `data/raw/cases/source_urls.csv` is provenance information, not a license grant.

Case parser and corpus tests requiring original PDFs or derived corpora are external-data tests and are skipped when excluded inputs are absent. Contract tests use only the synthetic fixture and never describe it as a real case.

## Law materials

The original DOCX packaging and complete article-level derived law text are excluded for the same reason: public availability does not by itself establish a redistribution license. The repository retains law schema, metadata, parsing code, and provenance documentation. Users who regenerate records must obtain source texts from an appropriate official source and comply with its terms.

## Provenance and responsibility

The project records source URLs where available and distinguishes source provenance from permission to redistribute. Users are responsible for verifying current source terms, copyright, database rights, access restrictions, and any applicable law before obtaining, processing, or publishing external material.

## Evaluation artifact boundary

Public evaluation artifacts retain code, project-authored query definitions, aggregate metrics, sanitized per-query metadata, and failure taxonomy. They do not retain third-party statutory or case text, retrieved full context, or raw prompts/responses containing that material. This sanitization preserves the reported metrics while respecting provenance and redistribution uncertainty; see `docs/evaluation_data_policy.md`.
