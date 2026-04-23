"""Flight Plan Request (MSG 2001) 스키마."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .common import (
    Field,
    ISO_DATETIME_PATTERN,
    validate_field,
)


TOP_FIELDS: Dict[str, Field] = {
    "timestamp":        Field("iso_datetime", "UTC", "송신 시각",          "Send time",          pattern=ISO_DATETIME_PATTERN),
    "scenarioFileName": Field("str", "",             "시나리오 파일명",     "Scenario file name"),
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

    if isinstance(obj.get("scenarioFileName"), str) and not obj["scenarioFileName"]:
        errors.append("scenarioFileName: 빈 문자열 불가")

    return (len(errors) == 0), errors, obj
