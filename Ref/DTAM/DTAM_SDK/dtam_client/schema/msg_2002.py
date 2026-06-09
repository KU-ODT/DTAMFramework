"""DTAM Execute (MSG 2002) 스키마."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .common import (
    Field,
    ISO_DATETIME_PATTERN,
    validate_field,
)


TOP_FIELDS: Dict[str, Field] = {
    "timestamp":              Field("iso_datetime", "UTC", "송신 시각",             "Send time",               pattern=ISO_DATETIME_PATTERN),
    "simModeFileName":        Field("str", "",             "시뮬레이션 모드 파일명",  "Sim mode file name"),
    "simulationSetupFileName":Field("str", "",             "시뮬레이션 설정 파일명",  "Simulation setup file name"),
    "scenarioFileName":       Field("str", "",             "시나리오 설정 파일명",    "Scenario file name"),
    "flightPlanFolderName":   Field("str", "",             "비행계획 폴더명",        "Flight plan folder name"),
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

    # 빈 문자열 검사
    for key in ("simModeFileName", "simulationSetupFileName", "scenarioFileName", "flightPlanFolderName"):
        if isinstance(obj.get(key), str) and not obj[key]:
            errors.append(f"{key}: 빈 문자열 불가")

    return (len(errors) == 0), errors, obj
