"""Conservative rule-based extraction; no model inference is used."""

from __future__ import annotations

import re


CASE_NUMBER_RE = re.compile(r"[（(]\d{4}[）)][^\s，。；：:]{2,60}?号")
DATE_RE = re.compile(r"(\d{4})[年./-](\d{1,2})[月./-](\d{1,2})日?")
COURT_RE = re.compile(r"[\u4e00-\u9fff]{2,40}人民法院")
LEGAL_BASIS_RE = re.compile(r"《[^》]{2,80}法》?第[一二三四五六七八九十百千万零〇0-9]+条")


def _heading_start(text: str, headings: tuple[str, ...], start: int = 0) -> tuple[int, int] | None:
    """Find a section heading at a line boundary, including ``标题：内容``."""
    matches: list[tuple[int, int]] = []
    for heading in headings:
        pattern = re.compile(rf"(?m)^[ \t\u3000]*{re.escape(heading)}(?:[：:、.]?[ \t\u3000]*)")
        match = pattern.search(text, start)
        if match:
            matches.append((match.start(), match.end()))
    return min(matches, default=None)


def _section(
    text: str,
    headings: tuple[str, ...],
    next_headings: tuple[str, ...],
    *,
    allow_end_of_document: bool = False,
) -> str:
    start_match = _heading_start(text, headings)
    if not start_match:
        return ""
    _, content_start = start_match
    end_match = _heading_start(text, next_headings, content_start)
    if end_match:
        end = end_match[0]
    elif allow_end_of_document:
        end = len(text)
    else:
        return ""
    value = text[content_start:end].strip()
    return value if value else ""


def extract_fields(text: str, filename_stem: str = "") -> dict[str, object]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else filename_stem
    case_number_match = CASE_NUMBER_RE.search(text)
    date_match = DATE_RE.search(text)
    date = ""
    if date_match:
        date = f"{int(date_match.group(1)):04d}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
    courts = list(dict.fromkeys(COURT_RE.findall(text)))
    facts = _section(
        text,
        ("本院查明", "经审理查明", "事实与理由", "案件事实", "基本案情"),
        ("本院认为", "经审查认为", "法院认为", "裁判理由", "本院意见", "判决如下", "裁定如下", "判决结果", "裁判结果", "综上"),
    )
    if not facts:
        facts = _section(
            text,
            ("案件事实", "基本案情"),
            ("本院认为", "经审查认为", "法院认为", "裁判理由", "本院意见", "判决如下", "裁定如下", "判决结果", "裁判结果", "综上"),
        )
    reasoning = _section(
        text,
        ("本院认为", "经审查认为", "法院认为", "裁判理由", "本院意见"),
        ("判决如下", "裁定如下", "判决结果", "裁判结果", "综上", "裁判要旨", "裁判要点", "相关法条", "关联索引"),
    )
    result = _section(
        text,
        ("判决如下", "裁定如下", "判决结果", "裁判结果", "综上"),
        ("如不服本判决", "如不服本裁定", "审判长", "书记员", "本判决为终审判决"),
        allow_end_of_document=True,
    )
    if not result:
        result = _section(
            text,
            ("判决结果", "裁判结果"),
            ("如不服本判决", "如不服本裁定", "审判长", "书记员", "本判决为终审判决"),
            allow_end_of_document=True,
        )
    if not result:
        reasoning_start = _heading_start(
            text,
            ("本院认为", "经审查认为", "法院认为", "裁判理由", "本院意见"),
        )
        boundary = reasoning_start[0] if reasoning_start else len(text)
        inline_results = list(re.finditer(r"(?:民事|刑事|行政)?(?:判决|裁定)[：:]", text[:boundary]))
        if inline_results:
            result = text[inline_results[-1].end():boundary].strip()
    legal_basis = list(dict.fromkeys(LEGAL_BASIS_RE.findall(text)))
    case_type = ""
    for label in ("案由", "案件类型"):
        match = re.search(rf"{label}\s*[:：]?\s*([^\n；;]+)", text)
        if match:
            case_type = match.group(1).strip()
            break
    return {
        "title": title.strip(),
        "case_number": case_number_match.group(0) if case_number_match else "",
        "court": courts[0] if courts else "",
        "judgment_date": date,
        "case_type": case_type,
        "basic_facts": facts,
        "court_reasoning": reasoning,
        "judgment_result": result,
        "legal_basis": legal_basis,
    }
