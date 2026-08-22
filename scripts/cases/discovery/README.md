# V0.8.1 Automated Case Discovery — Phase 1

This directory contains the Phase 2-A foundation for automated discovery of
official case detail URLs.

The Phase 2-A browser path is intentionally limited to one keyword and the
first result page. It does not:

- perform multi-keyword or multi-page collection;
- read or print cookies, tokens, or browser storage;
- download PDFs;
- modify the collector, parser, retrieval, or RAG pipeline.

The module provides configuration loading, official URL validation,
relative-to-absolute URL normalization, candidate construction, URL
deduplication, schema checks, JSON output, and a persistent-profile browser
entry point for the single-page test.

Example with an offline fixture file:

```text
python scripts/cases/discovery/discovery.py --input discovery_fixture.json
```

Single-keyword browser test command:

```text
python scripts/cases/discovery/discovery.py --keyword "违法解除劳动合同" --max-pages 1 --headful
```

This command reads visible result links only. It does not download PDFs or
call the collector.
