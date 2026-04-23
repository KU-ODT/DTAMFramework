"""Schema 공통 — 모든 메시지 스키마에서 재사용.

- 공통 정규식 (aircraftId / 시간 형식 등)
- Field dataclass
- 기본 타입 검증기 (validate_field)

새 메시지는 이 모듈을 import 하여 동일 규칙을 공유한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple


# ===== 공통 정규식 =====
AIRCRAFT_ID_PATTERN = r"^[A-Z]{2,8}\d{4}$"     # 예: UAM0001
AIRCRAFT_ID_REGEX = re.compile(AIRCRAFT_ID_PATTERN)
TIME_HMS_PATTERN = r"^\d{2}:\d{2}:\d{2}$"       # 예: 09:02:00
TIME_HM_PATTERN = r"^\d{2}:\d{2}$"               # 예: 09:02
ISO_DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"

# 0401 과의 하위호환 별칭 (VEHICLE_ID = AIRCRAFT_ID)
VEHICLE_ID_PATTERN = AIRCRAFT_ID_PATTERN
VEHICLE_ID_REGEX = AIRCRAFT_ID_REGEX


# ===== Field 스펙 =====

@dataclass
class Field:
    ftype: str                         # "float"|"int"|"str"|"iso_datetime"|"list[float]"|"list[int]"
    unit: str = ""
    desc_kr: str = ""
    desc_en: str = ""
    range: Optional[Tuple[float, float]] = None
    length: Optional[int] = None
    item_range: Optional[Tuple[float, float]] = None
    pattern: Optional[str] = None
    choices: Optional[List[Any]] = None

    def describe(self) -> str:
        bits = [self.ftype]
        if self.unit: bits.append(f"[{self.unit}]")
        if self.range: bits.append(f"range {self.range[0]}~{self.range[1]}")
        if self.length is not None: bits.append(f"len={self.length}")
        if self.item_range: bits.append(f"item {self.item_range[0]}~{self.item_range[1]}")
        if self.choices: bits.append(f"choices={self.choices}")
        if self.pattern: bits.append(f"pattern={self.pattern}")
        return " ".join(bits)


# ===== 검증기 =====

def _check_number(val: Any, f: Field, path: str, errors: List[str]) -> None:
    if f.ftype == "int":
        if not isinstance(val, int) or isinstance(val, bool):
            errors.append(f"{path}: int 필요, got {type(val).__name__}")
            return
    else:
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            errors.append(f"{path}: float 필요, got {type(val).__name__}")
            return
    if f.range is not None:
        lo, hi = f.range
        if not (lo <= val <= hi):
            errors.append(f"{path}: 범위 벗어남 ({val} not in [{lo},{hi}])")


def _check_list(val: Any, f: Field, path: str, errors: List[str]) -> None:
    if not isinstance(val, list):
        errors.append(f"{path}: list 필요, got {type(val).__name__}")
        return
    if f.length is not None and len(val) != f.length:
        errors.append(f"{path}: 길이 {f.length} 필요, got {len(val)}")
    inner = "float" if f.ftype == "list[float]" else "int"
    for i, v in enumerate(val):
        _check_number(v, Field(inner, range=f.item_range), f"{path}[{i}]", errors)


def _check_str(val: Any, f: Field, path: str, errors: List[str]) -> None:
    if not isinstance(val, str):
        errors.append(f"{path}: str 필요, got {type(val).__name__}")
        return
    if f.pattern and not re.match(f.pattern, val):
        errors.append(f"{path}: 패턴 불일치 ({f.pattern})")
    if f.choices and val not in f.choices:
        errors.append(f"{path}: choices 불일치 {f.choices}")


def validate_field(val: Any, f: Field, path: str, errors: List[str]) -> None:
    if f.ftype in ("float", "int"):
        _check_number(val, f, path, errors)
    elif f.ftype in ("list[float]", "list[int]"):
        _check_list(val, f, path, errors)
    elif f.ftype in ("str", "iso_datetime"):
        _check_str(val, f, path, errors)
    elif f.ftype == "bool":
        if not isinstance(val, bool):
            errors.append(f"{path}: bool 필요, got {type(val).__name__}")
    elif f.ftype == "dict":
        if not isinstance(val, dict):
            errors.append(f"{path}: dict 필요, got {type(val).__name__}")
    else:
        errors.append(f"{path}: 알 수 없는 타입 '{f.ftype}'")
