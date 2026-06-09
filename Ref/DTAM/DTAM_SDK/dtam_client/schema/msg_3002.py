"""Scheduled Flight Modification Command (MSG 3002) 스키마."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .common import (
    AIRCRAFT_ID_PATTERN,
    Field,
    ISO_DATETIME_PATTERN,
    validate_field,
)


MODIFICATION_TYPES = [
    "scheduleResourceUpdate",
    "routeUpdate",
    "aircraftSwap",
    "delayOnly",
    "cancelPlan",
]

REASON_CODES = [
    "VERTIPORT_CAPACITY",
    "CORRIDOR_CLOSED",
    "WEATHER",
    "VEHICLE_UNAVAILABLE",
    "OPERATOR_REQUEST",
]

MODIFY_SCOPES = [
    "departureOnly",
    "arrivalOnly",
    "departureAndArrival",
    "enRouteOnly",
    "aircraftOnly",
    "fullPlan",
]


TOP_FIELDS: Dict[str, Field] = {
    "timestamp":        Field("iso_datetime", "UTC", "명령 생성 시각",       "Command creation time",      pattern=ISO_DATETIME_PATTERN),
    "commandId":        Field("str", "",             "수정 명령 고유 ID",    "Modification command ID"),
    "flightPlanNumber": Field("int", "",             "수정 대상 정기편 번호", "Target flight plan number",  range=(1, 9_999_999)),
    "planVersion":      Field("int", "",             "수정 후 버전 번호",    "Plan version after modify",  range=(1, 999_999)),
    "aircraftId":       Field("str", "",             "비행체 ID",            "Aircraft ID",                pattern=AIRCRAFT_ID_PATTERN),
    "modificationType": Field("str", "",             "수정 유형",            "Modification type",          choices=MODIFICATION_TYPES),
    "reasonCode":       Field("str", "",             "수정 사유 코드",       "Reason code",                choices=REASON_CODES),
    "modifyScope":      Field("str", "",             "수정 범위",            "Modification scope",         choices=MODIFY_SCOPES),
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

    # commandId 빈 문자열 불가
    if isinstance(obj.get("commandId"), str) and not obj["commandId"]:
        errors.append("commandId: 빈 문자열 불가")

    return (len(errors) == 0), errors, obj
