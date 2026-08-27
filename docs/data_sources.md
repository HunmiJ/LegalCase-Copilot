# Case Data Sources

## Formal data source

`labor_case_dataset` is the current formal case-data source for the project.

The source is imported as a structured dataset and normalized into the
existing `CaseRecord` schema. The import path supports:

- structured dataset import;
- provenance and source-file tracking;
- duplicate case-ID and content-hash checks;
- public judgment document parsing through the `public_judgment` adapter;
- conversion to the existing case corpus format before indexing.

The dataset license and redistribution terms must be verified before any
external or commercial distribution of the source data.

## Supported processing

Public judgment documents can be staged locally as PDF, TXT, or HTML files and
processed by the existing `public_judgment` adapter. Text-layered PDFs are
supported directly; documents requiring OCR are reported for separate review.

The adapter produces `CaseRecord`-compatible records containing provenance,
raw text, case metadata, facts, reasoning, judgment results, and legal-basis
references where they can be extracted conservatively.

## Experimental data source

`rmfyalk` (People's Court Case Database) remains an experimental module only.
It is not the formal production data entry. Its detail content may require
authentication, and browser-session or platform-access constraints make it
unsuitable as the project's automated production source.

## Source policy

Some official platforms impose authentication, maintenance, rate, or access
limitations. The project therefore uses a traceable public dataset as its
primary knowledge-base source and keeps experimental official-platform code
isolated from the formal import path.

The project does not use hidden APIs, bypass authentication, or persist browser
credentials as part of the formal data pipeline.
