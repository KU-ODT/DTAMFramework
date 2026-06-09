from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Iterable


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not reader.fieldnames:
        raise ValueError(f"CSV headers are missing: {path}")
    return rows, list(reader.fieldnames)


def read_csv_matrix(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def normalize_key(text: str) -> str:
    return "".join(ch.lower() for ch in str(text) if ch.isalnum())


def find_column(fieldnames: Iterable[str], matcher: Callable[[str], bool]) -> str | None:
    for name in fieldnames:
        if matcher(normalize_key(name)):
            return name
    return None


def read_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
