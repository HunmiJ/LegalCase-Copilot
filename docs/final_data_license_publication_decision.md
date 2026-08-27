# Final Data / License Publication Decision

Date: 2026-08-28

## Decision

The public repository will not distribute the 20 curated raw court-document PDFs or the six original labor-law DOCX packages. Their sources and provenance are recorded, but the available source URLs do not establish permission to redistribute the original files through GitHub.

The repository retains the project source code, parsers, schemas, source URL/provenance tables, eligibility metadata, article-level processed law records, 19-case structured benchmark records, indexes, and evaluation artifacts. The 6,492-case production corpus, full-case embeddings/indexes, and external raw labor dataset remain excluded.

## Artifact decisions

| Artifact | Current public status | Reason / retained substitute |
|---|---|---|
| 20 curated case PDFs | Excluded from tree and history | Original judicial documents; provenance URL is not a redistribution license. Retain structured records, metadata, source list, and parser. |
| Six labor-law DOCX files | Excluded from tree and history | Source-document packaging rights are not established. Retain article-level records, metadata, parser, and official-source provenance. |
| Case source URL and collection CSVs | Retained | Provenance and collection planning only; not a license grant or raw document copy. |
| 19-case processed benchmark | Retained pending provenance review | Small structured benchmark artifact used by tests/evaluation; remains subject to source terms. |
| 6,492-case production corpus | Excluded | Size and provenance/licensing considerations; user must provide lawful external input. |
| Generated full-case embeddings/index | Excluded | Generated from excluded production data and too large for the public repository. |

## Test and fresh-clone behavior

Tests that require original raw PDFs or DOCX files are explicitly skipped when those inputs are absent. Fresh clones can use the tracked article-level law products and structured curated case products; the law-only Demo remains available. The Demo does not claim that the 6,492-case production corpus is installed and does not download unknown-licence data automatically.

## License boundary

The root MIT `LICENSE` covers original LegalCase-Copilot source code only. It does not grant rights to third-party datasets, regulations, court judgments, reference cases, source documents, or generated data. Users must independently verify provenance, copyright/database rights, access restrictions, and redistribution terms before obtaining or publishing external material.

## Publication status

The second history sanitization removed all reachable `data/raw/cases/*.pdf` and `data/raw/laws/*.docx` paths. No remote, tag, release, or push has been created. The remaining publication condition is a final human review of the retained processed benchmark/law artifacts and their source terms.