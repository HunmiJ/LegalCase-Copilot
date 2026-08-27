# Third-Party Data and Provenance Boundary

This repository's MIT License applies only to original project source code. It does not grant redistribution rights for third-party datasets, regulations, court judgments, reference case materials, source documents, or generated data artifacts.

## Excluded production data

The 6,492-case production corpus, its generated embeddings and indexes, and any external raw labor-case dataset are not distributed with this repository. They must be obtained and prepared by the user from a lawful source with appropriate redistribution and processing rights.

## Curated case benchmark

The 19-case curated benchmark is represented in the repository by structured processed records, metadata, source URL/provenance tables, and processing code. The original court-document PDFs are intentionally excluded because the repository does not establish a license permitting GitHub redistribution. The source list in `data/raw/cases/source_urls.csv` is provenance information, not a license grant.

Case parser tests that require original PDFs are integration-only and are skipped when the excluded raw inputs are absent. The remaining tests exercise the checked-in structured records, schemas, retrieval behavior, and safety contracts.

## Law materials

The original DOCX packaging of six labor-law materials is excluded for the same reason: public availability does not by itself establish a redistribution license. The repository retains article-level processed records, metadata, indexes, database artifacts, parsing code, and provenance documentation needed for the project pipeline. Users who regenerate these records must obtain the source texts from an appropriate official source and comply with its terms.

## Provenance and responsibility

The project records source URLs where available and distinguishes source provenance from permission to redistribute. Users are responsible for verifying current source terms, copyright, database rights, access restrictions, and any applicable law before obtaining, processing, or publishing external material.
