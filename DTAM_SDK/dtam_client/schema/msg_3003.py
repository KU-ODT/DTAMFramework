"""Tactical Action Command (MSG 3003) 스키마."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .common import (
    AIRCRAFT_ID_PATTERN,
    Field,
    ISO_DATETIME_PATTERN,
    validate_field,
)


REASON_CODES = [
    "LOSS_OF_SEPARATION_RISK",
    "LOCAL_CORRIDOR_BLOCKED",
    "LOW_BATTERY",
    "WEATHER_AVOIDANCE",
    "OPERATOR_OVERRIDE",
    "EMERGENCY_LANDING",
]

ACTION_TYPES = ["setSpeed", "directTo", "hold", "rejoinPlan", "land"]
TURN_CHOICES = ["CW", "CCW"]

TOP_FIELDS: Dict[str, Field] = {
    "timestamp":  Field("iso_datetime", "UTC", "명령 생성 시각",    "Command creation time",  pattern=ISO_DATETIME_PATTERN),
    "commandId":  Field("str", "",             "전술 명령 고유 ID", "Tactical command ID"),
    "aircraftId": Field("str", "",             "대상 비행체 ID",    "Target aircraft ID",     pattern=AIRCRAFT_ID_PATTERN),
    "reasonCode": Field("str", "",             "명령 사유 코드",    "Reason code",            choices=REASON_CODES),
}

LLA_FIELDS: Dict[str, Field] = {
    "lat": Field("float", "deg", "위도", "Latitude",  range=(-90.0, 90.0)),
    "lon": Field("float", "deg", "경도", "Longitude", range=(-180.0, 180.0)),
    "alt": Field("float", "m",   "고도", "Altitude",  range=(-500.0, 20000.0)),
}


def _validate_lla(obj: Any, path: str, errors: List[str]) -> None:
    if not isinstance(obj, dict):
        errors.append(f"{path}: dict 필요")
        return
    for fname, fspec in LLA_FIELDS.items():
        if fname not in obj:
            errors.append(f"{path}.{fname}: 누락")
            continue
        validate_field(obj[fname], fspec, f"{path}.{fname}", errors)


def _validate_set_speed(action: Dict[str, Any], path: str, errors: List[str]) -> None:
    f = Field("float", "m/s", "목표 속도", "Target speed", range=(0.0, 200.0))
    if "targetSpeed" not in action:
        errors.append(f"{path}.targetSpeed: 누락")
    else:
        validate_field(action["targetSpeed"], f, f"{path}.targetSpeed", errors)


def _validate_direct_to(action: Dict[str, Any], path: str, errors: List[str]) -> None:
    llas = action.get("targetLLAs")
    if llas is None:
        errors.append(f"{path}.targetLLAs: 누락")
        return
    if not isinstance(llas, list):
        errors.append(f"{path}.targetLLAs: list 필요")
        return
    if len(llas) < 1:
        errors.append(f"{path}.targetLLAs: 최소 1개 필요")
        return
    speed_field = Field("float", "m/s", "목표 속도", "Target speed", range=(0.0, 200.0))
    for i, pt in enumerate(llas):
        p = f"{path}.targetLLAs[{i}]"
        if not isinstance(pt, dict):
            errors.append(f"{p}: dict 필요")
            continue
        _validate_lla(pt, p, errors)
        if "targetSpeed" not in pt:
            errors.append(f"{p}.targetSpeed: 누락")
        else:
            validate_field(pt["targetSpeed"], speed_field, f"{p}.targetSpeed", errors)


def _validate_hold(action: Dict[str, Any], path: str, errors: List[str]) -> None:
    if "holdLLA" not in action:
        errors.append(f"{path}.holdLLA: 누락")
    else:
        _validate_lla(action["holdLLA"], f"{path}.holdLLA", errors)

    td_field = Field("str", "", "선회 방향", "Turn direction", choices=TURN_CHOICES)
    if "turnDirection" not in action:
        errors.append(f"{path}.turnDirection: 누락")
    else:
        validate_field(action["turnDirection"], td_field, f"{path}.turnDirection", errors)

    radius_field = Field("float", "m", "홀드 반경", "Holding radius", range=(1.0, 5000.0))
    if "holdingRadiusM" not in action:
        errors.append(f"{path}.holdingRadiusM: 누락")
    else:
        validate_field(action["holdingRadiusM"], radius_field, f"{path}.holdingRadiusM", errors)

    count_field = Field("int", "", "홀드 횟수", "Holding count", range=(0, 9999))
    if "maxHoldingCount" not in action:
        errors.append(f"{path}.maxHoldingCount: 누락")
    else:
        validate_field(action["maxHoldingCount"], count_field, f"{path}.maxHoldingCount", errors)


def _validate_rejoin_plan(action: Dict[str, Any], path: str, errors: List[str]) -> None:
    seq_field = Field("int", "", "재합류 seq", "Rejoin seq", range=(1, 9999))
    if "atSeq" not in action:
        errors.append(f"{path}.atSeq: 누락")
    else:
        validate_field(action["atSeq"], seq_field, f"{path}.atSeq", errors)


def _validate_land(action: Dict[str, Any], path: str, errors: List[str]) -> None:
    has_target = "targetLLA" in action
    has_vertiport = "vertiport" in action

    if not has_target and not has_vertiport:
        errors.append(f"{path}: targetLLA 또는 vertiport 중 최소 하나 필요")

    if has_target:
        _validate_lla(action["targetLLA"], f"{path}.targetLLA", errors)
    if has_vertiport:
        if not isinstance(action["vertiport"], str):
            errors.append(f"{path}.vertiport: str 필요")
        elif not action["vertiport"]:
            errors.append(f"{path}.vertiport: 빈 문자열 불가")
    if "fatoNumber" in action:
        if not isinstance(action["fatoNumber"], str):
            errors.append(f"{path}.fatoNumber: str 필요")


_ACTION_VALIDATORS = {
    "setSpeed":    _validate_set_speed,
    "directTo":    _validate_direct_to,
    "hold":        _validate_hold,
    "rejoinPlan":  _validate_rejoin_plan,
    "land":        _validate_land,
}


def _validate_actions(obj: Dict[str, Any], errors: List[str]) -> None:
    actions = obj.get("actions")
    if actions is None:
        errors.append("actions: 누락")
        return
    if not isinstance(actions, list):
        errors.append("actions: list 필요")
        return
    if len(actions) < 1:
        errors.append("actions: 최소 1개 필요")
        return

    for i, action in enumerate(actions):
        path = f"actions[{i}]"
        if not isinstance(action, dict):
            errors.append(f"{path}: dict 필요")
            continue
        atype = action.get("type")
        if atype is None:
            errors.append(f"{path}.type: 누락")
            continue
        if atype not in ACTION_TYPES:
            errors.append(f"{path}.type: 허용 값 외 ({atype})")
            continue
        _ACTION_VALIDATORS[atype](action, path, errors)


def validate_message(obj: Any) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["root: dict 필요"], {}

    for name, fspec in TOP_FIELDS.items():
        if name not in obj:
            errors.append(f"{name}: 누락")
            continue
        validate_field(obj[name], fspec, name, errors)

    if isinstance(obj.get("commandId"), str) and not obj["commandId"]:
        errors.append("commandId: 빈 문자열 불가")

    _validate_actions(obj, errors)

    return (len(errors) == 0), errors, obj
