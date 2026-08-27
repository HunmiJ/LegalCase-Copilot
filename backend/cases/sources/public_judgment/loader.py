"""Loader for locally staged public judgment documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from .text_extractor import extract_text


SUPPORTED_SUFFIXES = {".pdf", ".txt", ".html", ".htm"}


def iter_input_files(input_dir: Path) -> Iterator[Path]:
    if not input_dir.exists():
        return
    for path in sorted(input_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


def load_one(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    extracted = extract_text(path)
    return {"path": path, **extracted}


def load_directory(input_dir: Path) -> Iterator[dict[str, Any]]:
    for path in iter_input_files(input_dir):
        yield load_one(path)
