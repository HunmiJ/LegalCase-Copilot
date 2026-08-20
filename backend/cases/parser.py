"""Parser for the text-layered official People's Court Case Database PDFs."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pypdf import PdfReader

from .schemas import CaseRecord


SECTION_NAMES = ("基本案情", "裁判结果", "裁判理由", "裁判要旨", "裁判要点", "相关法条", "关联索引")
DATABASE_ID_RE = re.compile(r"^\d{4}-\d+-\d+-\d+-\d+$")
DATE_RE = re.compile(r"\d{4}年\d{1,2}月\d{1,2}日")
CASE_NUMBER_RE = re.compile(r"[（(]\d{4}[）)]\s*[^，。；：:（）()]{2,30}?号")


def _clean_lines(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line or line == "人民法院案例库":
                continue
            if re.fullmatch(r"第\s*\d+\s*页人民法院案例库", line):
                continue
            lines.append(line)
    return lines


def extract_pdf_text(pdf_path: Path) -> tuple[str, int]:
    """Return cleaned, complete text and page count; no OCR is attempted."""
    reader = PdfReader(str(pdf_path))
    lines = _clean_lines(pdf_path)
    return "\n".join(lines), len(reader.pages)


def _section_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    positions = {line: index for index, line in enumerate(lines) if line in SECTION_NAMES}
    result: dict[str, tuple[int, int]] = {}
    ordered = [(name, positions[name]) for name in SECTION_NAMES if name in positions]
    for index, (name, start) in enumerate(ordered):
        end = ordered[index + 1][1] if index + 1 < len(ordered) else len(lines)
        result[name] = (start + 1, end)
    return result


def _join(lines: list[str]) -> str | None:
    value = "".join(lines).strip()
    return value or None


def _first_line_containing(lines: list[str], marker: str) -> int | None:
    for index, line in enumerate(lines):
        if marker in line:
            return index
    return None


def _first_heading(lines: list[str], heading: str, start: int = 0) -> int | None:
    for index in range(start, len(lines)):
        if lines[index] == heading or lines[index].startswith(heading + " "):
            return index
    return None


def _extract_legal_basis(lines: list[str]) -> list[str]:
    value = "".join(lines).strip()
    return [value] if value else []


def _extract_keywords(lines: list[str]) -> list[str]:
    value = "".join(line.removeprefix("关键词").strip() for line in lines).strip()
    return [item for item in re.split(r"[、,，;；\s]+", value) if item]


def _extract_related_index(lines: list[str]) -> tuple[list[str], list[str]]:
    joined = "".join(lines).strip()
    joined = joined.split("本案例文本已于", 1)[0].strip()
    if not joined:
        return [], []
    references = re.findall(r"《.*?》[^《]*?(?=《|一审：|二审：|$)", joined)
    trials = re.findall(r"(?:一审|二审)：.*?(?=一审：|二审：|$)", joined)
    return [item.strip() for item in references + trials if item.strip()], [item.strip() for item in references if item.strip()]


def _stable_fallback_id(title: str, case_number: str | None, source_file: str) -> str:
    content = "\x1f".join((title, case_number or "", source_file))
    return "case-" + hashlib.sha256(content.encode("utf-8")).hexdigest()[:20]


def parse_case_pdf(pdf_path: Path, source_url: str | None = None) -> tuple[CaseRecord, int]:
    lines = _clean_lines(pdf_path)
    if not lines:
        raise ValueError(f"PDF has no extractable text: {pdf_path.name}")
    page_count = len(PdfReader(str(pdf_path)).pages)
    database_case_number = next((line for line in lines if DATABASE_ID_RE.fullmatch(line)), None)
    id_index = lines.index(database_case_number) if database_case_number else 0
    title_parts: list[str] = []
    subtitle_parts: list[str] = []
    in_subtitle = False
    cursor = id_index + 1
    while cursor < len(lines):
        line = lines[cursor]
        if line == "关键词" or line.startswith("关键词 "):
            break
        if line.startswith("——"):
            in_subtitle = True
            subtitle_parts.append(line.removeprefix("——"))
        elif in_subtitle:
            subtitle_parts.append(line)
        else:
            title_parts.append(line)
        cursor += 1
    title = "".join(title_parts).strip() or None
    subtitle = "".join(subtitle_parts).strip() or None
    keyword_index = _first_heading(lines, "关键词", id_index + 1)
    heading_positions = [
        _first_heading(lines, heading, keyword_index + 1 if keyword_index is not None else id_index + 1)
        for heading in SECTION_NAMES
    ]
    heading_positions = [index for index in heading_positions if index is not None]
    keyword_end = min(heading_positions) if heading_positions else (keyword_index + 1 if keyword_index is not None else 0)
    keywords = _extract_keywords(lines[keyword_index:keyword_end]) if keyword_index is not None else []
    sections = _section_ranges(lines)
    facts_start, facts_end = sections.get("基本案情", (0, len(lines)))
    facts_lines = lines[facts_start:facts_end]
    facts = _join(facts_lines)
    reasoning_start, reasoning_end = sections.get("裁判理由", (0, 0))
    reasoning = _join(lines[reasoning_start:reasoning_end]) if reasoning_end else None
    gist_start, gist_end = sections.get("裁判要旨", (0, 0))
    if not gist_end:
        gist_start, gist_end = sections.get("裁判要点", (0, 0))
    case_gist = _join(lines[gist_start:gist_end]) if gist_end else None
    index_start, index_end = sections.get("关联索引", (0, 0))
    related_index, legal_basis = _extract_related_index(lines[index_start:index_end]) if index_end else ([], [])
    law_start, law_end = sections.get("相关法条", (0, 0))
    if law_end:
        legal_basis = _extract_legal_basis(lines[law_start:law_end])
    facts_block = "".join(facts_lines)
    result_start, result_end = sections.get("裁判结果", (0, 0))
    judgment_result = _join(lines[result_start:result_end]) if result_end else None
    if not judgment_result:
        result_match = re.search(r"[^。；]*人民法院于\d{4}年", facts_block)
        judgment_result = facts_block[result_match.start():].strip() if result_match else None
    all_case_numbers = list(dict.fromkeys(re.sub(r"\s+", "", item) for item in CASE_NUMBER_RE.findall(judgment_result or "")))
    case_number = "；".join(all_case_numbers) or None
    courts = list(dict.fromkeys(re.findall(r"([一-龥]{2,30}人民法院)于\d{4}年", judgment_result or "")))
    court = "；".join(courts) or None
    dates = list(dict.fromkeys(re.findall(r"人民法院于(\d{4}年\d{1,2}月\d{1,2}日)", judgment_result or "")))
    judgment_date = "；".join(dates) or None
    source_file = f"data/raw/cases/{pdf_path.name}"
    case_id = database_case_number or _stable_fallback_id(title or "", case_number, source_file)
    record = CaseRecord(
        case_id=case_id, title=title or pdf_path.stem, case_number=case_number,
        case_type=keywords[0] if keywords else "劳动争议", court=court,
        judgment_date=judgment_date, keywords=keywords, basic_facts=facts,
        dispute_focus=subtitle, court_reasoning=reasoning, judgment_result=judgment_result,
        case_gist=case_gist, legal_basis=legal_basis, related_index=related_index,
        database_case_number=database_case_number,
        case_level=("再审" if "再审" in "".join(lines) else "二审" if "二审" in "".join(lines) else "一审"),
        source_name="人民法院案例库", source_url=source_url, source_file=source_file,
        raw_text="\n".join(lines),
    )
    return record, page_count
