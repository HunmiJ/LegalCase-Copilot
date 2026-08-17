"""Parse official law DOCX files into article-level JSONL records."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ARTICLE_RE = re.compile(r"^(第[一二三四五六七八九十百千万零〇两0-9]+条)(?:[\s　]*(.*))?$")
CHAPTER_RE = re.compile(r"^(第[一二三四五六七八九十百千万零〇两0-9]+章)(?:[\s　]*(.*))?$")
SECTION_RE = re.compile(r"^(第[一二三四五六七八九十百千万零〇两0-9]+节)(?:[\s　]*(.*))?$")


def read_docx_paragraphs(path: Path) -> list[str]:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.iter(W_NS + "p"):
        chunks = []
        for node in paragraph.iter():
            if node.tag == W_NS + "t" and node.text:
                chunks.append(node.text)
            elif node.tag == W_NS + "tab":
                chunks.append(" ")
            elif node.tag == W_NS + "br":
                chunks.append(" ")
        text = re.sub(r"\s+", " ", "".join(chunks)).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def inspect_file(path: Path) -> dict:
    try:
        paragraphs = read_docx_paragraphs(path)
        articles = sum(bool(ARTICLE_RE.match(p)) for p in paragraphs)
        chapters = sum(bool(CHAPTER_RE.match(p)) for p in paragraphs)
        return {"file": path.name, "readable": True, "paragraphs": len(paragraphs),
                "chapters": chapters, "articles": articles, "error": None}
    except (BadZipFile, KeyError, ET.ParseError, OSError, ValueError) as exc:
        return {"file": path.name, "readable": False, "paragraphs": 0,
                "chapters": 0, "articles": 0, "error": str(exc)}


def parse_articles(path: Path, metadata: dict) -> list[dict]:
    paragraphs = read_docx_paragraphs(path)
    records = []
    current = None
    chapter = None
    for paragraph in paragraphs:
        chapter_match = CHAPTER_RE.match(paragraph)
        if chapter_match:
            chapter = chapter_match.group(1) + (chapter_match.group(2) or "")
            continue
        if SECTION_RE.match(paragraph):
            continue
        article_match = ARTICLE_RE.match(paragraph)
        if article_match:
            if current:
                current["article_content"] = "\n".join(current.pop("_parts")).strip()
                records.append(current)
            current = {"id": None, "law_name": metadata["law_name"],
                       "article_number": article_match.group(1),
                       "article_content": "", "chapter": chapter,
                       "document_type": metadata.get("document_type"),
                       "issuing_authority": metadata.get("issuing_authority"),
                       "publish_date": metadata.get("publish_date"),
                       "effective_date": metadata.get("effective_date"),
                       "status": metadata.get("status"),
                       "source_name": metadata.get("source_name"),
                       "source_url": metadata.get("source_url"),
                       "source_file": metadata["source_file"],
                       "_parts": []}
            if article_match.group(2):
                current["_parts"].append(article_match.group(2).strip())
        elif current:
            current["_parts"].append(paragraph)
    if current:
        current["article_content"] = "\n".join(current.pop("_parts")).strip()
        records.append(current)
    for record in records:
        digest = hashlib.sha256(f"{record['source_file']}:{record['article_number']}".encode()).hexdigest()
        record["id"] = digest[:20]
        if not record["article_content"]:
            raise ValueError(f"empty article content: {record['source_file']} {record['article_number']}")
    return records


def load_metadata(path: Path) -> dict[str, dict]:
    items = json.loads(path.read_text(encoding="utf-8"))
    return {item["source_file"]: item for item in items}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", default=str(ROOT / "data/law_metadata.json"))
    parser.add_argument("--output", default=str(ROOT / "data/processed/laws.jsonl"))
    parser.add_argument("--scan-only", action="store_true")
    args = parser.parse_args()
    laws_dir = ROOT / "data/raw/laws"
    files = sorted(laws_dir.glob("*.docx"))
    if not files:
        print("未发现 DOCX 文件", file=sys.stderr)
        return 1
    print("原始文件检查：")
    inspections = [inspect_file(path) for path in files]
    for item in inspections:
        state = "可读取" if item["readable"] else f"异常：{item['error']}"
        print(f"- {item['file']} | {state} | 段落 {item['paragraphs']} | "
              f"章节 {item['chapters']} | 条文 {item['articles']}")
    if any(not item["readable"] for item in inspections):
        return 2
    if args.scan_only:
        return 0
    metadata = load_metadata(Path(args.metadata))
    records = []
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if relative not in metadata:
            raise ValueError(f"metadata missing for {relative}")
        records.extend(parse_articles(path, metadata[relative]))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"已输出 {len(records)} 条法律条文：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
