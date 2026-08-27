"""Text extraction for text-layered PDF, TXT, and HTML judgment files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from pypdf import PdfReader


def _clean_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for raw_line in lines:
        line = re.sub(r"[ \t\u00a0]+", " ", raw_line).strip()
        if not line:
            continue
        if line in {"中国裁判文书网", "裁判文书网", "人民法院案例库"}:
            continue
        if re.fullmatch(r"第\s*\d+\s*页(?:/共\s*\d+\s*页)?(?:人民法院案例库|中国裁判文书网)?", line):
            continue
        cleaned.append(line)
    return cleaned


def _result(raw_text: str, page_count: int, extractor: str, status: str = "ok") -> dict[str, Any]:
    return {
        "raw_text": raw_text,
        "page_count": page_count,
        "extractor": extractor,
        "status": status,
    }


def extract_pdf(path: Path) -> dict[str, Any]:
    reader = PdfReader(str(path))
    lines: list[str] = []
    for page in reader.pages:
        lines.extend((page.extract_text() or "").splitlines())
    cleaned = _clean_lines(lines)
    if not cleaned:
        return _result("", len(reader.pages), "pypdf", "need_ocr")
    return _result("\n".join(cleaned), len(reader.pages), "pypdf", "ok")


def _decode_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_txt(path: Path) -> dict[str, Any]:
    text = "\n".join(_clean_lines(_decode_text(path).splitlines()))
    return _result(text, 1, "text", "ok")


def extract_html(path: Path) -> dict[str, Any]:
    soup = BeautifulSoup(_decode_text(path), "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    text = "\n".join(_clean_lines(soup.get_text("\n").splitlines()))
    return _result(text, 1, "beautifulsoup", "ok")


def extract_text(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix == ".txt":
        return extract_txt(path)
    if suffix in {".html", ".htm"}:
        return extract_html(path)
    raise ValueError(f"unsupported public judgment file type: {path.suffix}")
