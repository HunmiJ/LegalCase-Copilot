"""Phase 2-J single-case detail-page collector.

This smoke collector probes the visible official detail page only. It does
not download PDFs, invoke the existing parser, or process more than one
candidate per run.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, unquote, urljoin, urlparse


ROOT = Path(__file__).resolve().parents[3]
OFFICIAL_DOMAIN = "rmfyalk.court.gov.cn"
DEFAULT_INPUT = ROOT / "scripts/cases/discovery/discovery_candidates.json"
DEFAULT_PROFILE = Path(r"<LOCAL_BROWSER_PROFILE>")
DEFAULT_OUTPUT = ROOT / "data/raw/cases/smoke_render_case.json"
DEFAULT_DEBUG_DIR = Path(__file__).with_name("debug")
DETAIL_NETWORK_DEBUG = DEFAULT_DEBUG_DIR / "detail_network.json"
CONTENT_API_PATH = "/cpws_al_api/api/cpwsAl/content"
CONTENT_API_URL = f"https://{OFFICIAL_DOMAIN}{CONTENT_API_PATH}"
DATE_RE = re.compile(r"\d{4}年\d{1,2}月\d{1,2}日")
CASE_NUMBER_RE = re.compile(r"[（(]\d{4}[）)][^，。；：:]{2,50}?号")
DATABASE_ID_RE = re.compile(r"^\d{4}-\d+-\d+-\d+-\d+$")


def validate_source_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != OFFICIAL_DOMAIN:
        raise ValueError(f"source_url must belong to {OFFICIAL_DOMAIN}")
    return url


def extract_gid(source_url: str) -> str:
    """Extract the API gid while preserving the encoding expected by the site."""
    validate_source_url(source_url)
    raw_id = next(
        (part.split("=", 1)[1] for part in urlparse(source_url).query.split("&") if part.startswith("id=")),
        "",
    )
    if not raw_id:
        raise ValueError("source_url is missing the id query parameter")
    decoded = unquote(raw_id)
    return decoded if "%" in decoded else quote(decoded, safe="")


def load_candidates(path: Path = DEFAULT_INPUT) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        raise ValueError("candidate input must be a non-empty JSON list")
    candidates = []
    for item in value:
        if isinstance(item, dict) and item.get("source_url"):
            validate_source_url(item["source_url"])
            candidates.append(item)
    if not candidates:
        raise ValueError("candidate input contains no valid official URLs")
    return candidates


def prepare_profile(profile: Path) -> None:
    """Remove only stale Chromium Singleton markers; preserve profile data."""
    profile.mkdir(parents=True, exist_ok=True)
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        marker = profile / name
        if not marker.exists() and not marker.is_symlink():
            continue
        print(f"WARNING: found persistent-profile marker: {marker}", flush=True)
        try:
            marker.unlink()
        except OSError as exc:
            raise RuntimeError("Profile is occupied by another Chromium instance") from exc
        print(f"WARNING: removed marker only; profile data preserved: {marker}", flush=True)


def choose_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose exactly one candidate for the smoke run."""
    return random.choice(candidates)


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _string_for_alias(payload: Any, aliases: tuple[str, ...]) -> str:
    if isinstance(payload, dict):
        for alias in aliases:
            value = payload.get(alias)
            if isinstance(value, str) and value.strip():
                return value
        for value in payload.values():
            result = _string_for_alias(value, aliases)
            if result:
                return result
    elif isinstance(payload, list):
        for value in payload:
            result = _string_for_alias(value, aliases)
            if result:
                return result
    return ""


def _strip_markup(value: str) -> str:
    return clean_text(re.sub(r"<[^>]+>", " ", value))


def extract_api_fields(payload: Any) -> dict[str, str]:
    """Map known and common API field names without guessing missing values."""
    aliases = {
        "title": ("cpws_al_title", "title", "case_title"),
        "case_number": ("cpws_al_ajzh", "case_number", "caseNo", "case_no"),
        "court": ("cpws_al_court", "court", "court_name", "slfy"),
        "judgment_date": ("cpws_al_zs_date", "judgment_date", "cprq", "date"),
        "case_type": ("cpws_al_case_sort_name", "case_type", "caseType", "cpws_al_case_sort"),
        "raw_text": ("cpws_al_content", "content", "raw_text", "text", "body"),
    }
    fields = {
        name: _string_for_alias(payload, names)
        for name, names in aliases.items()
    }
    fields["title"] = _strip_markup(fields["title"])
    fields["raw_text"] = _strip_markup(fields["raw_text"])
    return fields


def save_content_api_response(payload: Any, debug_dir: Path = DEFAULT_DEBUG_DIR) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "content_api_response.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_auth_context_report(report: dict[str, Any], debug_dir: Path = DEFAULT_DEBUG_DIR) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "auth_context_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def extract_labeled_value(lines: list[str], labels: Iterable[str]) -> str:
    labels = tuple(labels)
    for index, line in enumerate(lines):
        for label in labels:
            if line == label and index + 1 < len(lines):
                return clean_text(lines[index + 1])
            prefix = label + "："
            if line.startswith(prefix):
                return clean_text(line[len(prefix):])
    return ""


def probe_fields(title: str, body_text: str, links: list[dict[str, str]]) -> dict[str, str]:
    """Extract only fields supported by visible text/links; otherwise empty."""
    lines = [clean_text(line) for line in body_text.splitlines() if clean_text(line)]
    detected_title = clean_text(title)
    if detected_title in {"首页", "法院案例", "人民法院案例库"}:
        detected_title = ""
    if not detected_title:
        for index, line in enumerate(lines[:-1]):
            if DATABASE_ID_RE.fullmatch(line):
                detected_title = lines[index + 1]
                break

    case_number = ""
    date = ""
    for line in lines:
        if not case_number:
            match = CASE_NUMBER_RE.search(line)
            if match:
                case_number = match.group(0)
        if not date:
            match = DATE_RE.search(line)
            if match:
                date = match.group(0)

    return {
        "title": detected_title,
        "case_number": case_number,
        "court": extract_labeled_value(lines, ("法院", "审理法院", "裁判法院")),
        "judgment_date": date or extract_labeled_value(lines, ("裁判日期", "审判日期")),
        "case_type": extract_labeled_value(lines, ("案件类型", "案由")),
        "raw_text": body_text,
        "pdf_url": next((link["href"] for link in links if link.get("is_pdf")), ""),
    }


def relevant_links(page: Any) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for link in page.locator("a[href]").all():
        href = link.get_attribute("href", timeout=5000) or ""
        text = clean_text(link.inner_text(timeout=5000))
        marker = f"{href} {text}".lower()
        if any(token in marker for token in ("pdf", "download", "content", "file")):
            results.append({
                "href": urljoin(page.url, href),
                "text": text,
                "is_pdf": ".pdf" in href.lower() or "pdf" in text.lower(),
            })
    return results


def install_page_network_diagnostics(page: Any) -> list[dict[str, Any]]:
    """Capture request/response metadata without headers or browser storage."""
    records: list[dict[str, Any]] = []
    markers = ("api", "content", "detail", "case", "pdf")

    def is_relevant(url: str) -> bool:
        lowered = url.lower()
        return any(marker in lowered for marker in markers)

    def on_request(request: Any) -> None:
        if is_relevant(request.url) or request.resource_type in {"xhr", "fetch"}:
            records.append({
                "event": "request",
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type,
                "post_data": request.post_data,
            })

    def on_response(response: Any) -> None:
        request = response.request
        if is_relevant(response.url) or request.resource_type in {"xhr", "fetch"}:
            records.append({
                "event": "response",
                "url": response.url,
                "method": request.method,
                "resource_type": request.resource_type,
                "post_data": request.post_data,
                "status": response.status,
            })

    page.on("request", on_request)
    page.on("response", on_response)
    return records


def save_detail_network_diagnostics(page: Any, records: list[dict[str, Any]], debug_dir: Path = DEFAULT_DEBUG_DIR) -> None:
    """Save script URLs and relevant XHR/fetch metadata for source analysis."""
    debug_dir.mkdir(parents=True, exist_ok=True)
    scripts = [
        urljoin(page.url, script.get_attribute("src", timeout=5000) or "")
        for script in page.locator("script[src]").all()
    ]
    scripts = list(dict.fromkeys(url for url in scripts if url))
    payload = {"scripts": scripts, "requests": records}
    (debug_dir / "detail_network.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("detail page script src:", flush=True)
    for script in scripts:
        print(script, flush=True)
    print("detail page relevant xhr/fetch and API requests:", flush=True)
    for record in records:
        print(json.dumps(record, ensure_ascii=False), flush=True)


def save_detail_debug(page: Any, debug_dir: Path = DEFAULT_DEBUG_DIR) -> str:
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "detail_page.html").write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(debug_dir / "detail_page.png"), full_page=True)
    text = clean_text(page.locator("body").inner_text(timeout=10000))
    print(f"detail URL: {page.url}", flush=True)
    print(f"detail title: {page.title()}", flush=True)
    print(f"detail text (first 3000 chars): {text[:3000]}", flush=True)
    links = relevant_links(page)
    for link in links:
        print(f"related link href={link['href']} text={link['text']}", flush=True)
    print(f"related links: {len(links)}", flush=True)
    return text


def extract_rendered_body(page: Any) -> str:
    """Prefer the largest visible content-like DOM region over the page shell."""
    selectors = (
        "#content",
        ".detail-content",
        ".case-content",
        ".article-content",
        ".cpws-content",
        "main",
        "[class*='content']",
    )
    candidates: list[str] = []
    for selector in selectors:
        for locator in page.locator(selector).all():
            try:
                if locator.is_visible(timeout=2000):
                    text = clean_text(locator.inner_text(timeout=5000))
                    if text:
                        candidates.append(text)
            except Exception:
                continue
    if candidates:
        return max(candidates, key=len)
    try:
        return clean_text(page.locator("body").inner_text(timeout=10000))
    except Exception:
        return ""


def save_render_detail_debug(page: Any, debug_dir: Path = DEFAULT_DEBUG_DIR) -> str:
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "render_detail_page.html").write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(debug_dir / "render_detail_page.png"), full_page=True)
    body_text = extract_rendered_body(page)
    print(f"render detail URL: {page.url}", flush=True)
    print(f"render detail title: {page.title()}", flush=True)
    print(f"render detail text (first 3000 chars): {body_text[:3000]}", flush=True)
    return body_text


def collect_smoke(candidate: dict[str, Any], profile: Path = DEFAULT_PROFILE, output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    source_url = validate_source_url(candidate["source_url"])
    from playwright.sync_api import sync_playwright

    prepare_profile(profile)
    with sync_playwright() as playwright:
        try:
            context = playwright.chromium.launch_persistent_context(str(profile), headless=False, accept_downloads=False)
        except Exception as exc:
            report = {
                "status": "profile_occupied",
                "profile": str(profile),
                "error": "Profile is occupied by another Chromium instance",
                "api_called": False,
            }
            save_auth_context_report(report)
            print("Profile is occupied by another Chromium instance", flush=True)
            raise RuntimeError("Profile is occupied by another Chromium instance") from exc
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(source_url, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_load_state("networkidle", timeout=60000)
            except Exception:
                print("render detail networkidle timeout; continuing", flush=True)
            page.wait_for_timeout(3000)
            body_text = save_render_detail_debug(page)
            fields = probe_fields(page.title(), body_text, [])
            record = {
                "title": fields["title"],
                "case_number": fields["case_number"],
                "court": fields["court"],
                "judgment_date": fields["judgment_date"],
                "case_type": fields["case_type"],
                "raw_text": body_text,
                "source_url": source_url,
            }
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return record
        finally:
            context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect one official case detail-page smoke record")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    candidates = load_candidates(args.input)
    selected = choose_candidate(candidates)
    print(f"selected one candidate from {len(candidates)}", flush=True)
    record = collect_smoke(selected, args.profile, args.output)
    print(json.dumps({"output": str(args.output), "title": record["title"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
