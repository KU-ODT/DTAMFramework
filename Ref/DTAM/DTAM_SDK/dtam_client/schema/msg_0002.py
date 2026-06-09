"""Module Status (MSG 0002) 스키마."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .common import (
    Field,
    ISO_DATETIME_PATTERN,
    validate_field,
)


TOP_FIELDS: Dict[str, Field] = {
    "timestamp": Field("iso_datetime", "UTC", "송신 시각", "Send time", pattern=ISO_DATETIME_PATTERN),
    "source":    Field("str", "", "모듈 영문 이름", "Module name (English)"),
    "status":    Field("int", "", "상태 코드 (1=정상)", "Status code (1=Normal)", range=(1, 1)),
}


def validate_message(obj: Any) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["root: dict 필요"], {}

    for name, fspec in TOP_FIELDS.items():
        if name not in obj:
            errors.append(f"{name}: 누락")
            continue
        validate_field(obj[name], fspec, name, errors)

    # source 빈 문자열 불가
    if isinstance(obj.get("source"), str) and not obj["source"]:
        errors.append("source: 빈 문자열 불가")

    return (len(errors) == 0), errors, obj
