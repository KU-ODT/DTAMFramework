"""Common Time Info (MSG 0003) 스키마."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .common import (
    Field,
    ISO_DATETIME_PATTERN,
    validate_field,
)


TOP_FIELDS: Dict[str, Field] = {
    "timestamp": Field("iso_datetime", "UTC", "송신 시각",          "Send time",       pattern=ISO_DATETIME_PATTERN),
    "simTime":   Field("str", "UTC", "시뮬레이션 내부 시간", "Simulation time",
                       pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"),
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

    return (len(errors) == 0), errors, obj
