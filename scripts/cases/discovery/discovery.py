"""V0.8.1 official case URL discovery.

The browser entry point is intentionally limited to one keyword and one
visible result page in Phase 2-A. Pure URL and candidate logic remains usable
without Playwright or network access.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
OFFICIAL_DOMAIN = "rmfyalk.court.gov.cn"
DEFAULT_CONFIG = Path(__file__).with_name("discovery_config.json")
DEFAULT_OUTPUT = Path(__file__).with_name("discovery_candidates.json")
DEFAULT_PROFILE = Path(r"<LOCAL_BROWSER_PROFILE>")
HOME_URL = f"https://{OFFICIAL_DOMAIN}/"
DEFAULT_DEBUG_DIR = Path(__file__).with_name("debug")
NETWORK_DEBUG_PATH = DEFAULT_DEBUG_DIR / "network_requests.json"
SEARCH_INPUT_SELECTOR = "input.keyword"
SEARCH_BUTTON_SELECTOR = "button.general-search-submit"
RESULT_LIST_SELECTOR = ".al-list"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    keywords = config.get("keywords")
    max_pages = config.get("max_pages_per_keyword")
    if not isinstance(keywords, list) or not keywords or not all(isinstance(item, str) and item.strip() for item in keywords):
        raise ValueError("config.keywords must be a non-empty list of strings")
    if not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("config.max_pages_per_keyword must be a positive integer")
    return {"keywords": [item.strip() for item in keywords], "max_pages_per_keyword": max_pages}


def normalize_url(href: str, base_url: str = f"https://{OFFICIAL_DOMAIN}/") -> str:
    if not isinstance(href, str) or not href.strip():
        raise ValueError("URL must be a non-empty string")
    return urljoin(base_url, href.strip())


def is_official_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == OFFICIAL_DOMAIN and not parsed.username and not parsed.password


def validate_official_url(url: str) -> str:
    normalized = normalize_url(url)
    if not is_official_url(normalized):
        raise ValueError(f"URL must use HTTPS and belong to {OFFICIAL_DOMAIN}: {url}")
    return normalized


def clean_title(title: str) -> str:
    """Convert a search-result title containing markup into plain text."""
    if not isinstance(title, str):
        raise ValueError("title must be a string")
    text = unescape(title)
    text = re.sub(r"<[^>]*>", "", text)
    return " ".join(text.split())


def make_candidate(source_url: str, title: str, keyword: str, page: int, discovered_at: str | None = None) -> dict[str, Any]:
    normalized = validate_official_url(source_url)
    title = clean_title(title)
    if not title:
        raise ValueError("title must be a non-empty string")
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("keyword must be a non-empty string")
    if not isinstance(page, int) or page < 1:
        raise ValueError("page must be a positive integer")
    return {
        "source_url": normalized,
        "title": title.strip(),
        "keyword": keyword.strip(),
        "page": page,
        "source_domain": OFFICIAL_DOMAIN,
        "discovered_at": discovered_at or datetime.now(timezone.utc).isoformat(),
        "status": "candidate",
    }


def deduplicate_candidates(candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for candidate in candidates:
        normalized = validate_official_url(candidate["source_url"])
        if normalized in seen:
            continue
        item = dict(candidate)
        item["source_url"] = normalized
        seen.add(normalized)
        unique.append(item)
    return unique


def validate_candidate(candidate: dict[str, Any]) -> None:
    required = {"source_url", "title", "keyword", "page", "source_domain", "discovered_at", "status"}
    if set(candidate) != required:
        raise ValueError(f"candidate fields must be exactly {sorted(required)}")
    validate_official_url(candidate["source_url"])
    if not isinstance(candidate["title"], str) or not candidate["title"].strip():
        raise ValueError("candidate.title must be non-empty")
    if not isinstance(candidate["keyword"], str) or not candidate["keyword"].strip():
        raise ValueError("candidate.keyword must be non-empty")
    if not isinstance(candidate["page"], int) or candidate["page"] < 1:
        raise ValueError("candidate.page must be positive")
    if candidate["source_domain"] != OFFICIAL_DOMAIN or candidate["status"] not in {"candidate", "discovered"}:
        raise ValueError("candidate has invalid source_domain or status")
    if not isinstance(candidate["discovered_at"], str) or not candidate["discovered_at"].strip():
        raise ValueError("candidate.discovered_at must be non-empty")


def write_candidates(path: Path, candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = deduplicate_candidates(candidates)
    for candidate in unique:
        validate_candidate(candidate)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(unique, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return unique


def save_timeout_debug(
    page: Any,
    debug_dir: Path = DEFAULT_DEBUG_DIR,
    stem: str = "discovery_timeout",
    text_limit: int = 500,
) -> None:
    """Persist visible page diagnostics after a result-list timeout."""
    debug_dir.mkdir(parents=True, exist_ok=True)
    html_path = debug_dir / f"{stem}.html"
    screenshot_path = debug_dir / f"{stem}.png"
    html_path.write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(screenshot_path), full_page=True)
    try:
        page_text = page.locator("body").inner_text(timeout=5000)
    except Exception:
        page_text = "<unable to read visible body text>"
    print(f"debug current URL: {page.url}", flush=True)
    print(f"debug page title: {page.title()}", flush=True)
    print(f"debug page text (first {text_limit} chars): {page_text[:text_limit]}", flush=True)


def search_state(page: Any, search_input: Any) -> dict[str, str]:
    """Return only visible search diagnostics; no browser storage is read."""
    try:
        value = search_input.input_value(timeout=5000)
    except Exception:
        value = "<unable to read input value>"
    return {"url": page.url, "title": page.title(), "input_value": value}


def print_search_state(label: str, state: dict[str, str]) -> None:
    print(f"search {label} URL: {state['url']}", flush=True)
    print(f"search {label} title: {state['title']}", flush=True)
    print(f"search {label} input value: {state['input_value']}", flush=True)


def save_search_after_click_debug(page: Any, debug_dir: Path = DEFAULT_DEBUG_DIR) -> None:
    """Save the page state after search-trigger attempts."""
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "search_after_click.html").write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(debug_dir / "search_after_click.png"), full_page=True)
    try:
        text = page.locator("body").inner_text(timeout=5000)
    except Exception:
        text = "<unable to read visible body text>"
    print(f"search after click page text (first 1000 chars): {text[:1000]}", flush=True)


def save_search_js_success_debug(page: Any, debug_dir: Path = DEFAULT_DEBUG_DIR) -> None:
    """Save the page after a JavaScript search trigger succeeds."""
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "search_js_success.html").write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(debug_dir / "search_js_success.png"), full_page=True)


def install_network_diagnostics(page: Any) -> list[dict[str, Any]]:
    """Capture request/response metadata without headers or browser storage."""
    records: list[dict[str, Any]] = []
    markers = ("api", "search", "query", "list", "case", "content", "ajax")

    def record(kind: str, url: str, method: str, resource_type: str, status: int | None = None) -> None:
        lowered = url.lower()
        item: dict[str, Any] = {
            "event": kind,
            "url": url,
            "method": method,
            "resource_type": resource_type,
            "relevant": any(marker in lowered for marker in markers),
        }
        if status is not None:
            item["status"] = status
        records.append(item)

    def on_request(request: Any) -> None:
        record("request", request.url, request.method, request.resource_type)

    def on_response(response: Any) -> None:
        request = response.request
        record("response", response.url, request.method, request.resource_type, response.status)

    page.on("request", on_request)
    page.on("response", on_response)
    return records


def write_network_diagnostics(records: list[dict[str, Any]], debug_path: Path = NETWORK_DEBUG_PATH) -> None:
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"network diagnostics saved: {debug_path}", flush=True)
    print(f"network records: {len(records)}", flush=True)
    print(f"relevant network records: {sum(1 for item in records if item['relevant'])}", flush=True)


def extract_search_candidates(payload: Any, keyword: str, page_url: str, page_number: int = 1) -> list[dict[str, Any]]:
    """Convert official search response rows into candidate records."""
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data.get("datas") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    candidates: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = row.get("cpws_al_title") or row.get("title") or row.get("case_title")
        case_id = row.get("id") or row.get("cpws_al_id") or row.get("case_id")
        if not title or not case_id:
            continue
        direct_url = row.get("url") or row.get("source_url")
        if direct_url:
            source_url = normalize_url(str(direct_url), page_url)
        else:
            case_type = row.get("cpws_al_type")
            lib = "zdx" if case_type == "01" else "ck" if case_type == "02" else "qb"
            encoded_id = quote(str(case_id), safe="")
            source_url = urljoin(page_url, f"/view/content.html?id={encoded_id}&lib={lib}")
        try:
            candidate = make_candidate(source_url, str(title), keyword, page_number)
        except ValueError:
            continue
        candidate["status"] = "discovered"
        candidates.append(candidate)
    return deduplicate_candidates(candidates)


def install_search_api_diagnostics(page: Any, keyword: str, candidates: list[dict[str, Any]], records: list[dict[str, Any]]) -> None:
    """Listen on a result tab for the official case search API."""
    endpoint_marker = "/cpws_al_api/api/cpwsAl/search"

    def on_request(request: Any) -> None:
        if endpoint_marker not in request.url:
            return
        records.append({
            "event": "request",
            "url": request.url,
            "method": request.method,
            "post_data": request.post_data,
        })

    def on_response(response: Any) -> None:
        if endpoint_marker not in response.url:
            return
        request = response.request
        payload: Any = None
        try:
            payload = response.json()
        except Exception as exc:
            records.append({
                "event": "response",
                "url": response.url,
                "method": request.method,
                "post_data": request.post_data,
                "status": response.status,
                "json_error": f"{type(exc).__name__}: {exc}",
            })
            return
        records.append({
            "event": "response",
            "url": response.url,
            "method": request.method,
            "post_data": request.post_data,
            "status": response.status,
            "json": payload,
        })
        candidates.extend(extract_search_candidates(payload, keyword, page.url))

    page.on("request", on_request)
    page.on("response", on_response)


def write_search_api_debug(records: list[dict[str, Any]], debug_dir: Path = DEFAULT_DEBUG_DIR) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "search_api.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"search API records: {len(records)}", flush=True)


def prepare_persistent_profile(profile: Path) -> None:
    """Remove only a stale Chromium SingletonLock before launch.

    The profile directory and all other profile data are preserved. If the
    lock is still held by a live browser, unlinking fails and no process is
    terminated by this module.
    """
    profile.mkdir(parents=True, exist_ok=True)
    lock_path = profile / "SingletonLock"
    if not lock_path.exists() and not lock_path.is_symlink():
        return
    print(f"WARNING: found persistent-profile lock: {lock_path}", flush=True)
    try:
        lock_path.unlink()
    except OSError as exc:
        raise RuntimeError(
            f"Unable to remove SingletonLock; the profile may still be in use: {lock_path}"
        ) from exc
    print(f"WARNING: removed stale lock only; profile data preserved: {lock_path}", flush=True)


def report_search_experiment(page: Any, label: str, before_url: str) -> bool:
    """Wait and report one search-trigger experiment."""
    page.wait_for_timeout(5000)
    state = search_state(page, page.locator(SEARCH_INPUT_SELECTOR))
    try:
        text = page.locator("body").inner_text(timeout=5000)
    except Exception:
        text = "<unable to read visible body text>"
    url_changed = state["url"] != before_url
    print(f"search experiment {label} URL: {state['url']}", flush=True)
    print(f"search experiment {label} title: {state['title']}", flush=True)
    print(f"search experiment {label} text (first 1000 chars): {text[:1000]}", flush=True)
    print(f"search experiment {label} URL changed: {url_changed}", flush=True)
    success = url_changed or "/view/list.html" in state["url"] or "命中案例" in text
    if success:
        save_search_js_success_debug(page)
        print(f"search experiment success: {label}", flush=True)
    return success


def save_search_result_debug(page: Any, debug_dir: Path = DEFAULT_DEBUG_DIR) -> None:
    """Save and print the complete post-search DOM state."""
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "search_result.html").write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(debug_dir / "search_result.png"), full_page=True)
    try:
        text = page.locator("body").inner_text(timeout=5000)
    except Exception:
        text = "<unable to read visible body text>"
    print(f"search result URL: {page.url}", flush=True)
    print(f"search result title: {page.title()}", flush=True)
    print(f"search result text (first 2000 chars): {text[:2000]}", flush=True)


def wait_for_search_state(page: Any, before_url: str, timeout_ms: int = 30000) -> str:
    """Wait for URL/list-page change or a DOM state stable for five seconds."""
    deadline = time.monotonic() + timeout_ms / 1000
    previous_dom = page.content()
    stable_since: float | None = None
    while time.monotonic() < deadline:
        current_url = page.url
        if current_url != before_url:
            return "url_changed"
        if "/view/list.html" in current_url:
            return "list_url_present"
        current_dom = page.content()
        if current_dom == previous_dom:
            stable_since = stable_since or time.monotonic()
            if time.monotonic() - stable_since >= 5:
                return "dom_stable_5s"
        else:
            stable_since = None
            previous_dom = current_dom
        page.wait_for_timeout(500)
    return "timeout"


def scan_case_link_candidates(page: Any) -> list[dict[str, str]]:
    """Print possible case links without creating candidate records."""
    matches: list[dict[str, str]] = []
    for link in page.locator("a[href]").all():
        href = link.get_attribute("href", timeout=5000) or ""
        text = link.inner_text(timeout=5000).strip()
        marker = f"{href} {text}".lower()
        if any(token in marker for token in ("/view/", "content", "case", "detail")):
            item = {"href": href, "text": text}
            matches.append(item)
            print(f"possible case link href={href} text={text}", flush=True)
    print(f"possible case links found: {len(matches)}", flush=True)
    return matches


def diagnose_search_dom(page: Any, search_input: Any, search_button: Any, debug_dir: Path = DEFAULT_DEBUG_DIR) -> None:
    """Print search-control DOM metadata and save the complete page HTML."""
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "search_dom.html").write_text(page.content(), encoding="utf-8")

    button_info = search_button.first.evaluate(
        """el => ({
            outerHTML: el.outerHTML,
            tagName: el.tagName,
            className: el.className,
            id: el.id,
            onclick: el.getAttribute('onclick'),
            parentHTML: el.parentElement ? el.parentElement.outerHTML : ''
        })"""
    ) if search_button.count() else {"error": "search button not found"}
    input_info = search_input.first.evaluate(
        """el => ({
            outerHTML: el.outerHTML,
            tagName: el.tagName,
            className: el.className,
            id: el.id,
            placeholder: el.getAttribute('placeholder'),
            value: el.value
        })"""
    ) if search_input.count() else {"error": "search input not found"}
    keyword_elements = page.locator("body *").evaluate_all(
        """elements => elements.filter(el => {
            const attrs = [el.tagName, el.className, el.id, el.getAttribute('aria-label'), el.getAttribute('placeholder'), el.textContent].join(' ');
            return /search|查询|检索|submit/i.test(attrs);
        }).map(el => ({
            tag: el.tagName,
            className: typeof el.className === 'string' ? el.className : '',
            id: el.id || '',
            text: (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 300)
        }))"""
    )

    print(f"search button DOM: {json.dumps(button_info, ensure_ascii=False)}", flush=True)
    print(f"search input DOM: {json.dumps(input_info, ensure_ascii=False)}", flush=True)
    print("search-related elements:", flush=True)
    for item in keyword_elements:
        print(
            f"element tag={item['tag']} class={item['className']} id={item['id']} text={item['text']}",
            flush=True,
        )


def diagnose_search_area_and_scripts(page: Any, search_input: Any, search_button: Any, debug_dir: Path = DEFAULT_DEBUG_DIR) -> None:
    """Inspect search DOM/event metadata and loaded JavaScript source files."""
    debug_dir.mkdir(parents=True, exist_ok=True)
    search_info = page.evaluate(
        """() => {
            const input = document.querySelector('input.keyword');
            const button = document.querySelector('.general-search-submit');
            const describe = element => element ? {
                outerHTML: element.outerHTML,
                tagName: element.tagName,
                className: typeof element.className === 'string' ? element.className : '',
                id: element.id || '',
                onclick: element.getAttribute('onclick'),
                parentHTML: element.parentElement ? element.parentElement.outerHTML : '',
                jqueryEvents: window.jQuery && jQuery._data ? Object.keys(jQuery._data(element, 'events') || {}) : []
            } : {missing: true};
            return {input: describe(input), button: describe(button)};
        }"""
    )
    print(f"phase 2-G input DOM: {json.dumps(search_info['input'], ensure_ascii=False)}", flush=True)
    print(f"phase 2-G button DOM: {json.dumps(search_info['button'], ensure_ascii=False)}", flush=True)

    script_urls = page.evaluate(
        """() => Array.from(document.querySelectorAll('script[src]')).map(script => new URL(script.src, document.baseURI).href)"""
    )
    script_urls = list(dict.fromkeys(script_urls))
    script_records = page.evaluate(
        """async urls => {
            const patterns = ['general-search-submit', 'keyword', 'search', 'query', 'list.html'];
            return Promise.all(urls.map(async url => {
                try {
                    const response = await fetch(url);
                    const text = await response.text();
                    return {
                        url,
                        matches: patterns.filter(pattern => text.toLowerCase().includes(pattern.toLowerCase())),
                        status: response.status
                    };
                } catch (error) {
                    return {url, matches: [], error: String(error)};
                }
            }));
        }""",
        script_urls,
    )
    (debug_dir / "scripts.json").write_text(json.dumps(script_records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"phase 2-G loaded scripts: {len(script_records)}", flush=True)
    for record in script_records:
        if record.get("matches"):
            print(f"phase 2-G script matches: {record['url']} -> {record['matches']}", flush=True)


def trigger_search(page: Any, search_input: Any, search_button: Any) -> tuple[str, bool]:
    """Try the supported visible search triggers and report URL change."""
    before = search_state(page, search_input)
    print_search_state("before click", before)
    print(f"search input selector exists: {search_input.count() > 0}", flush=True)
    print(f"search button selector exists: {search_button.count() > 0}", flush=True)

    methods = (
        ("locator.click", lambda: search_button.click(timeout=15000)),
        ("dom.evaluate.click", lambda: page.evaluate("document.querySelector('.general-search-submit').click()")),
        ("jquery.trigger.click", lambda: page.evaluate("$('.general-search-submit').trigger('click')")),
    )
    selected = "none"
    for name, action in methods:
        try:
            action()
            selected = name
        except Exception as exc:
            print(f"search trigger {name} failed: {type(exc).__name__}: {exc}", flush=True)
            continue
        if report_search_experiment(page, name, before["url"]):
            after = search_state(page, search_input)
            return selected, after["url"] != before["url"]
        save_search_after_click_debug(page)
    after = search_state(page, search_input)
    print_search_state("after all triggers", after)
    print(f"search URL changed after all triggers: {after['url'] != before['url']}", flush=True)
    save_search_after_click_debug(page)
    return selected, after["url"] != before["url"]


def run_browser_discovery(keyword: str, output: Path, profile: Path, headful: bool = False, max_pages: int = 1) -> list[dict[str, Any]]:
    """Discover one keyword from one visible result page using a persistent profile."""
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("--keyword must be a non-empty string")
    if max_pages != 1:
        raise ValueError("Phase 2-A supports exactly one page; use --max-pages 1")

    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    prepare_persistent_profile(profile)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile),
            headless=not headful,
            accept_downloads=False,
        )
        network_records = install_network_diagnostics(context.pages[0] if context.pages else context.new_page())
        search_api_records: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        context.on("page", lambda new_page: install_search_api_diagnostics(new_page, keyword.strip(), candidates, search_api_records))
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
            search_input = page.locator(SEARCH_INPUT_SELECTOR)
            search_input.wait_for(state="visible", timeout=30000)
            diagnose_search_area_and_scripts(page, search_input, page.locator(SEARCH_BUTTON_SELECTOR))
            search_input.fill(keyword.strip())
            search_button = page.locator(SEARCH_BUTTON_SELECTOR)
            diagnose_search_dom(page, search_input, search_button)
            with context.expect_page(timeout=30000) as new_page_info:
                search_button.click(timeout=15000)
            new_page = new_page_info.value
            try:
                new_page.wait_for_load_state("networkidle", timeout=60000)
            except PlaywrightTimeoutError:
                print("new result page networkidle timeout; continuing with current page state", flush=True)
            print(f"new page URL: {new_page.url}", flush=True)
            print(f"new page title: {new_page.title()}", flush=True)
            try:
                new_page_text = new_page.locator("body").inner_text(timeout=5000)
            except Exception:
                new_page_text = "<unable to read visible body text>"
            print(f"new page text (first 2000 chars): {new_page_text[:2000]}", flush=True)
            save_search_result_debug(new_page)
            return deduplicate_candidates(candidates)
        finally:
            write_search_api_debug(search_api_records)
            write_network_diagnostics(network_records)
            context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover official case URLs from one visible result page")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path, help="offline JSON list of candidate records")
    parser.add_argument("--keyword", help="one search keyword for Phase 2-A")
    parser.add_argument("--max-pages", type=int, default=1, help="Phase 2-A only permits 1")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--headful", action="store_true", help="show the persistent browser")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    load_config(args.config)
    if args.keyword and args.input:
        raise SystemExit("use either --keyword or --input, not both")
    if args.keyword:
        candidates = write_candidates(args.output, run_browser_discovery(args.keyword, args.output, args.profile, args.headful, args.max_pages))
    else:
        raw = json.loads(args.input.read_text(encoding="utf-8")) if args.input else []
        if not isinstance(raw, list):
            raise SystemExit("--input JSON must contain a list")
        candidates = write_candidates(args.output, raw)
    print(json.dumps({"candidates": len(candidates), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
