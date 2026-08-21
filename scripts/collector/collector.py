"""Visible Playwright persistent-profile collector for one official case.

The script intentionally uses a persistent browser profile rather than
serializing storage_state.json. It never reads or prints cookies.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = Path(r"D:\temp\rmfyalk-playwright-profile")
DEFAULT_DOWNLOAD_DIR = ROOT / "data/runtime/cases/raw"
DEFAULT_MANIFEST = ROOT / "data/runtime/cases/case_manifest.json"
HOME_URL = "https://rmfyalk.court.gov.cn/"
OFFICIAL_HOST = "rmfyalk.court.gov.cn"
DATABASE_ID_RE = re.compile(r"^\d{4}-\d+-\d+-\d+-\d+$")


def safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    return value or "official_case"


def load_urls(args: argparse.Namespace) -> list[str]:
    urls = list(args.url or [])
    if args.input:
        values = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(values, list):
            raise ValueError("--input JSON must contain a list")
        for value in values:
            urls.append(value if isinstance(value, str) else value.get("source_url") or value.get("url"))
    if args.urls_file:
        urls.extend(line.strip() for line in args.urls_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#"))
    return list(dict.fromkeys(url for url in urls if url))


def validate_url(url: str) -> None:
    if not url.startswith(f"https://{OFFICIAL_HOST}/"):
        raise ValueError("case URL must be an HTTPS URL on rmfyalk.court.gov.cn")


def load_manifest(path: Path) -> list[dict]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("case_manifest.json must contain a list")
    return value


def save_manifest(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_case_title_from_dom(page) -> str | None:
    """Extract the official case title from detail-page DOM text, not page.title()."""
    body_text = page.locator("body").inner_text(timeout=30000)
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    for index, line in enumerate(lines[:-1]):
        if DATABASE_ID_RE.fullmatch(line):
            candidate = lines[index + 1]
            if candidate and candidate not in {"首页", "正文", "人民法院案例库"}:
                return candidate
    return None


def collect_one(page, url: str, download_dir: Path, manifest: list[dict]) -> dict:
    validate_url(url)
    try:
        existing = next((row for row in manifest if row.get("source_url") == url and row.get("status") == "downloaded"), None)
        if existing and existing.get("pdf_path") and (ROOT / existing["pdf_path"]).exists():
            return {"source_url": url, "status": "already_downloaded", "pdf_path": existing["pdf_path"], "bytes": existing.get("bytes")}
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        dom_title = extract_case_title_from_dom(page)
        download_dir.mkdir(parents=True, exist_ok=True)
        with page.expect_download(timeout=30000) as download_info:
            page.get_by_role("link", name="下载", exact=True).click(timeout=15000)
        download = download_info.value
        filename = safe_name(download.suggested_filename or dom_title or "official_case")
        target = download_dir / filename
        download.save_as(str(target))
    except Exception as exc:
        row = {"source_url": url, "title": locals().get("dom_title") or "official_case", "status": "failed", "error": f"{type(exc).__name__}: {exc}", "timestamp": datetime.now(timezone.utc).isoformat()}
        manifest.append(row)
        return row

    title = dom_title or Path(filename).stem
    timestamp = datetime.now(timezone.utc).isoformat()
    row = {"source_url": url, "title": title, "status": "downloaded", "pdf_path": str(target.relative_to(ROOT)).replace("\\", "/"), "bytes": target.stat().st_size, "timestamp": timestamp, "downloaded_at": timestamp}
    manifest.append(row)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect official case PDFs through a visible persistent browser profile")
    parser.add_argument("--login", action="store_true", help="open the visible official site for manual login")
    parser.add_argument("--url", action="append", help="official case detail URL; may be repeated")
    parser.add_argument("--input", type=Path, help="JSON file containing official case detail URLs")
    parser.add_argument("--urls-file", type=Path, help="UTF-8 file containing one official detail URL per line")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--download-dir", type=Path, default=DEFAULT_DOWNLOAD_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--delay", type=float, default=3.0, help="seconds to wait after each case (default: 3)")
    args = parser.parse_args()
    if args.delay < 0:
        raise SystemExit("--delay must be non-negative")
    urls = load_urls(args)
    profile_path = args.profile.resolve()
    profile_path.mkdir(parents=True, exist_ok=True)
    print(f"profile path: {profile_path}", flush=True)
    manifest = load_manifest(args.manifest)
    results = []
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(str(profile_path), headless=False, accept_downloads=True)
        print("browser context started", flush=True)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
            if args.login:
                print("请在可见浏览器中手动登录人民法院案例库；完成后回到终端按 Enter。", flush=True)
                input()
                print("login mode finished; closing context to flush persistent profile", flush=True)
                return 0
            if not urls:
                print("浏览器已打开；未提供案例 URL，未下载文件。")
                return 0
            total = len(urls)
            for index, url in enumerate(urls, start=1):
                result = None
                for attempt in range(1, 4):
                    manifest[:] = [row for row in manifest if not (row.get("source_url") == url and row.get("status") == "failed")]
                    result = collect_one(page, url, args.download_dir, manifest)
                    save_manifest(args.manifest, manifest)
                    print(json.dumps({"progress": f"{index}/{total}", "attempt": attempt, **{key: result.get(key) for key in ("source_url", "title", "status", "pdf_path", "bytes", "error") if key in result}}, ensure_ascii=False), flush=True)
                    if result.get("status") in {"downloaded", "already_downloaded"}:
                        break
                results.append(result)
                if index < total and args.delay:
                    print(f"waiting {args.delay:g}s before next case", flush=True)
                    time.sleep(args.delay)
        except KeyboardInterrupt:
            save_manifest(args.manifest, manifest)
            print("Ctrl+C received; manifest saved, exiting safely.", flush=True)
            return 130
        finally:
            context.close()
            print("browser context closed", flush=True)
    return 0 if all(result.get("status") in {"downloaded", "already_downloaded"} for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
