# Final Derived Data Provenance Audit

Date: 2026-08-28

## Decision summary

| Dataset | Decision | Basis |
|---|---|---|
| Structured laws | `DO_NOT_PUBLISH` | `data/processed/laws.jsonl` contained 372 complete article texts, while the six source DOCX files had no confirmed redistribution terms and metadata source URLs were empty. |
| Structured 19-case corpus | `DO_NOT_PUBLISH` | Records contained `basic_facts`, `court_reasoning`, `judgment_result`, `case_gist`, `legal_basis`, and full `raw_text`, constituting substantial derived judicial text without confirmed redistribution rights. |
| Synthetic case fixture | `SAFE_TO_PUBLISH` | Fully synthetic, clearly labeled, and used only for contract/schema-level tests. |
| Source manifests and provenance metadata | `PUBLISH_WITH_ATTRIBUTION` | They preserve source identity and URLs but are not a license grant. |
| Evaluation metrics/scripts | `PUBLISH_WITH_ATTRIBUTION` | Retained where they do not embed corpus text; metrics must retain methodology and limitations. |

## Audited derived files

### Structured law data

Before cleanup, `data/processed/laws.jsonl` contained 372 records with fields: `id`, `law_name`, `article_number`, `article_content`, `chapter`, `document_type`, `issuing_authority`, `publish_date`, `effective_date`, `status`, `source_name`, `source_url`, and `source_file`. It contained complete article text. `source_url` was null in the tracked law metadata, and `source_file` pointed to the removed DOCX packages. It is now removed from the tree and history, together with `data/processed/legal.db`, `data/processed/embeddings.npy`, and `data/processed/embedding_index.json`.

The retained `data/law_metadata.json` is metadata only. It records the issuing authorities and source-file identities but does not establish redistribution permission. Users must obtain the current official texts and regenerate local processed records lawfully.

### Structured 19-case data

Before cleanup, `data/processed/cases/cases.jsonl` contained 19 records with fields including `case_id`, `title`, `case_type`, `source_name`, `source_file`, `raw_text`, `case_number`, `court`, `judgment_date`, `keywords`, `basic_facts`, `dispute_focus`, `court_reasoning`, `judgment_result`, `case_gist`, `legal_basis`, `related_index`, `database_case_number`, `case_level`, and `source_url`. The records included extensive derived case text and were removed together with `case_embeddings.npy` and `case_embedding_index.json`.

The retained `data/case_metadata.json`, `data/case_eligibility.json`, and `data/raw/cases/source_urls.csv` are provenance/eligibility metadata, not the case text and not a redistribution license. The repository also includes `tests/fixtures/synthetic_case_fixture.jsonl`; it is entirely synthetic and must not be described as a real judicial case.

## Test boundary

`tests/conftest.py` marks tests requiring excluded law/case corpora as `external-data` skips. Core generation contracts, safety tests, schema tests, Demo integration tests, and other in-memory unit tests remain runnable. Final result: `85 passed, 90 skipped, 1 warning`. The warning is the existing Windows inability to write `.pytest_cache`.

## Final tree and history checks

- Complete structured law records: absent.
- Complete structured 19-case records: absent.
- 6,492 production corpus and full embeddings: absent.
- Raw case PDFs and raw law DOCX: absent.
- Reachable history entries for removed derived/raw corpus paths: 0.
- Sensitive/absolute-path scan: 0 matches.
- `.git` size after cleanup: approximately 3.1 MB.
- Backup: project-external Git bundle created and verified before derived-data cleanup.

## Evaluation artifacts requiring separate review

The repository still retains historical evaluation JSON files that contain `article_content` fields, including query-understanding records and several intermediate retrieval/generation result files. They were intentionally not modified in this phase because the user explicitly prohibited evaluation changes. They are therefore not cleared as `SAFE_TO_PUBLISH`: before a public push, either confirm their redistribution basis or perform a separately authorized evaluation-artifact cleanup.

## README and provenance status

README and `THIRD_PARTY_DATA.md` now state that the repository contains source code, schemas, provenance/metadata, synthetic fixtures, processing scripts, and non-text evaluation artifacts. They explicitly state that complete structured law text, the 19-case derived corpus, raw documents, the 6,492-case corpus, and full embeddings are not included.

## Publication conclusion

The main derived-corpus exposure blocker is resolved. A separate licensing blocker remains for retained evaluation JSON containing article text, plus final review of retained metadata and other derivatives. Public push is not yet fully cleared until that evaluation-artifact decision is made under a separate authorization, alongside the existing MIT-only-for-original-code boundary.
