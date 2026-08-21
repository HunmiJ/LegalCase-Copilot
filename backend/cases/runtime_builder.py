"""Resumable, isolated builder for the official runtime case corpus.

This module deliberately never writes under ``data/raw/cases`` or
``data/processed/cases``.  Browser discovery/download orchestration can call
these small, deterministic operations after a human-visible official UI step.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .parser import parse_case_pdf
from .schemas import CaseRecord

OFFICIAL_HOST = "rmfyalk.court.gov.cn"
TOPICS: dict[str, list[str]] = {
    "劳动关系认定": ["确认劳动关系", "合作协议 劳动关系", "平台用工 劳动关系", "主播 劳动关系", "骑手 劳动关系"],
    "新就业形态": ["新就业形态 劳动关系", "网约车 劳动关系", "外卖骑手 劳动争议"],
    "违法解除": ["违法解除 劳动合同", "严重违纪 解除", "不能胜任 解除", "绩效 解除", "旷工 解除"],
    "经济补偿与赔偿金": ["经济补偿 劳动争议", "违法解除 赔偿金", "被迫解除 经济补偿"],
    "工资与加班": ["欠薪 劳动争议", "加班费 劳动争议", "工资结构 奖金 提成", "高温津贴"],
    "书面合同与试用期": ["未签书面劳动合同 二倍工资", "试用期 劳动争议", "劳动合同变更"],
    "竞业与培训": ["竞业限制 劳动争议", "服务期 专项培训 劳动争议"],
    "调岗与绩效": ["调岗调薪 劳动争议", "绩效考核 劳动争议", "不能胜任工作"],
    "休假与女职工": ["年休假 劳动争议", "女职工 特殊保护", "生育待遇 劳动争议"],
    "社会保险与工伤": ["社会保险 劳动争议", "工伤保险待遇", "工伤待遇 劳动争议"],
    "派遣与非全日制": ["劳务派遣 劳动争议", "非全日制用工"],
    "规章与终止": ["规章制度 严重违纪", "劳动合同终止", "仲裁时效 劳动争议"],
}

_ILLEGAL_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_LABOR_TERMS = ("劳动", "工资", "加班", "竞业", "工伤", "社保", "解除", "劳动关系", "劳务派遣")
_AUXILIARY_TERMS = ("拒不支付劳动报酬罪", "刑事", "刑法")


@dataclass(frozen=True)
class RuntimePaths:
    root: Path

    @property
    def raw(self) -> Path: return self.root / "raw"
    @property
    def processed(self) -> Path: return self.root / "processed"
    @property
    def manifest(self) -> Path: return self.root / "manifest.jsonl"
    @property
    def plan(self) -> Path: return self.root / "collection_plan.json"
    @property
    def stats(self) -> Path: return self.root / "collection_stats.json"
    @property
    def corpus(self) -> Path: return self.processed / "runtime_cases.jsonl"
    @property
    def embeddings(self) -> Path: return self.processed / "runtime_case_embeddings.npy"
    @property
    def embedding_index(self) -> Path: return self.processed / "runtime_case_embedding_index.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_filename(case_id: str, title: str, suffix: str = ".pdf") -> str:
    normalized = _ILLEGAL_FILENAME.sub("_", title).strip(" .") or "untitled"
    return f"{case_id}__{normalized}{suffix}"


def is_official_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == OFFICIAL_HOST


def content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(paths: RuntimePaths) -> list[dict[str, Any]]:
    if not paths.manifest.exists():
        return []
    return [json.loads(line) for line in paths.manifest.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_manifest(paths: RuntimePaths, rows: Iterable[dict[str, Any]]) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda row: (row.get("case_id") or row.get("database_case_number") or "", row.get("source_url") or ""))
    paths.manifest.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ordered), encoding="utf-8")


def discover(paths: RuntimePaths, *, case_id: str, title: str, database_case_number: str | None,
             source_url: str, topic: str, discovery_query: str) -> dict[str, Any]:
    if not is_official_url(source_url):
        raise ValueError("source_url must be an HTTPS URL on rmfyalk.court.gov.cn")
    rows = load_manifest(paths)
    for row in rows:
        if row.get("case_id") == case_id or (database_case_number and row.get("database_case_number") == database_case_number):
            return row
    row = {"case_id": case_id, "database_case_number": database_case_number, "title": title,
           "source_url": source_url, "topic": topic, "discovery_query": discovery_query,
           "status": "download_pending", "pdf_path": None, "downloaded_at": None,
           "parsed": False, "eligibility": None, "parse_error": None, "duplicate_of": None,
           "content_hash": None}
    save_manifest(paths, [*rows, row])
    return row


def classify_eligibility(record: CaseRecord) -> str:
    text = " ".join((record.title, record.case_type, record.raw_text[:5000])).lower()
    if any(term in text for term in _AUXILIARY_TERMS):
        return "AUXILIARY_ONLY"
    return "ELIGIBLE_MAIN_RUNTIME" if any(term in text for term in _LABOR_TERMS) else "REJECT"


def ingest_pdf(paths: RuntimePaths, row: dict[str, Any], pdf_path: Path) -> dict[str, Any]:
    if not is_official_url(row.get("source_url")):
        raise ValueError("official provenance is required before ingestion")
    digest = content_hash(pdf_path)
    rows = load_manifest(paths)
    duplicate = next((item for item in rows if item.get("content_hash") == digest and item.get("case_id") != row.get("case_id")), None)
    updated = dict(row)
    updated.update({"pdf_path": str(pdf_path), "downloaded_at": row.get("downloaded_at") or utc_now(), "content_hash": digest})
    if duplicate:
        updated.update(status="duplicate", duplicate_of=duplicate.get("case_id"), parsed=False, eligibility="DUPLICATE")
    else:
        try:
            record, _ = parse_case_pdf(pdf_path, source_url=row["source_url"])
            data = record.to_dict()
            data["case_id"] = row["case_id"]
            data["database_case_number"] = row.get("database_case_number") or data.get("database_case_number")
            project_root = paths.root.parents[2]
            data["source_file"] = str(pdf_path.relative_to(project_root)).replace("\\", "/")
            record = CaseRecord.from_dict(data)
            eligibility = classify_eligibility(record)
            updated.update(status="main" if eligibility == "ELIGIBLE_MAIN_RUNTIME" else "auxiliary" if eligibility == "AUXILIARY_ONLY" else "failed",
                           parsed=True, eligibility=eligibility, parse_error=None)
            _write_main_record(paths, record, eligibility)
        except Exception as exc:  # keep the queue resumable and auditable
            updated.update(status="failed", parsed=False, eligibility="REJECT", parse_error=f"{type(exc).__name__}: {exc}")
    save_manifest(paths, [updated if item.get("case_id") == row.get("case_id") else item for item in rows])
    write_stats(paths)
    return updated


def _write_main_record(paths: RuntimePaths, record: CaseRecord, eligibility: str) -> None:
    if eligibility != "ELIGIBLE_MAIN_RUNTIME":
        return
    existing = [json.loads(line) for line in paths.corpus.read_text(encoding="utf-8").splitlines() if line.strip()] if paths.corpus.exists() else []
    by_id = {item["case_id"]: item for item in existing}
    by_id[record.case_id] = record.to_dict()
    paths.processed.mkdir(parents=True, exist_ok=True)
    paths.corpus.write_text("".join(json.dumps(by_id[key], ensure_ascii=False) + "\n" for key in sorted(by_id)), encoding="utf-8")


def write_stats(paths: RuntimePaths) -> dict[str, Any]:
    rows = load_manifest(paths)
    stats = {"target_main_cases": 500, "current": {key: sum(1 for row in rows if row.get("status") == value) for key, value in {
        "discovered": "download_pending", "downloaded": "downloaded", "main": "main", "auxiliary": "auxiliary",
        "duplicates": "duplicate", "failed": "failed", "pending_retry": "pending_retry"}.items()},
        "topic_distribution": {}, "last_checkpoint": None, "last_successful_case_id": None}
    for row in rows:
        if row.get("status") == "main": stats["topic_distribution"][row.get("topic") or "unknown"] = stats["topic_distribution"].get(row.get("topic") or "unknown", 0) + 1
    main = stats["current"]["main"]
    stats["last_checkpoint"] = max((n for n in (25, 50, 100, 250, 500) if main >= n), default=None)
    successful = [row for row in rows if row.get("status") == "main"]
    stats["last_successful_case_id"] = successful[-1].get("case_id") if successful else None
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.stats.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def write_collection_plan(paths: RuntimePaths) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.plan.write_text(json.dumps({"target_main_cases": 500, "topics": TOPICS, "created_at": utc_now()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
