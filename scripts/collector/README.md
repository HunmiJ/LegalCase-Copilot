# Official Case Collector Scaffold

This scaffold uses a visible Playwright persistent browser profile. It does
not read, print, or export cookies or storage state.

The profile is kept outside the repository:

```text
D:\temp\rmfyalk-playwright-profile\
```

First login manually:

```powershell
python scripts/collector/collector.py --login
```

Then test one official detail-page URL:

```powershell
python scripts/collector/collector.py --url "https://rmfyalk.court.gov.cn/view/content.html?..."
```

New PDFs default to `data/runtime/cases/raw/` so the frozen
`data/raw/cases/` corpus cannot be changed accidentally. The manifest is
written to `data/runtime/cases/case_manifest.json`.

The collector only follows the visible detail-page `下载` control and waits
for the browser download event. It does not call hidden APIs, bypass login,
solve CAPTCHAs, or work around 403/429 responses.
