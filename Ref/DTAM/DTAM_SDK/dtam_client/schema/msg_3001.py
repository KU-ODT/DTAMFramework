"""Scheduled Flight (MSG 3001) 스키마 — 정기편 정보.

aircraftId 는 4001 과 동일한 패턴을 공유 (common.AIRCRAFT_ID_PATTERN).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .common import (
    AIRCRAFT_ID_PATTERN,
    AIRCRAFT_ID_REGEX,
    Field,
    TIME_HMS_PATTERN,
    validate_field,
)


# ----- 상수 / 서브 스키마 -----

PLAN_STATUSES = ["active", "superseded", "discarded"]

PHASE_PATTERN = r"^[A-Z]$"
TURN_CHOICES = ["CW", "CCW"]

LLA_FIELDS: Dict[str, Field] = {
    "lat": Field("float", "deg", "위도", "Latitude",  range=(-90.0, 90.0)),
    "lon": Field("float", "deg", "경도", "Longitude", range=(-180.0, 180.0)),
    "alt": Field("float", "m",   "고도", "Altitude",  range=(-500.0, 20000.0)),
}

DEPARTURE_FIELDS: Dict[str, Field] = {
    "vertiport":     Field("str", "",         "출발 버티포트",            "Departure vertiport"),
    "std":           Field("str", "HH:MM:SS", "정기 출발 시각 (STD)",     "Scheduled Time of Departure", pattern=TIME_HMS_PATTERN),
    "depGateNumber": Field("str", "",         "출발 게이트 번호",         "Departure gate number"),
    "eobt":          Field("str", "HH:MM:SS", "예상 블록이탈 시각 (EOBT)","Estimated Off-Block Time",    pattern=TIME_HMS_PATTERN),
    "depFatoNumber": Field("str", "",         "출발 FATO 번호",           "Departure FATO number"),
    "etot":          Field("str", "HH:MM:SS", "예상 이륙 시각 (ETOT)",    "Estimated Take-Off Time",     pattern=TIME_HMS_PATTERN),
}

ARRIVAL_FIELDS: Dict[str, Field] = {
    "vertiport":     Field("str", "",         "도착 버티포트",            "Arrival vertiport"),
    "sta":           Field("str", "HH:MM:SS", "정기 도착 시각 (STA)",     "Scheduled Time of Arrival",   pattern=TIME_HMS_PATTERN),
    "arrGateNumber": Field("str", "",         "도착 게이트 번호",         "Arrival gate number"),
    "eibt":          Field("str", "HH:MM:SS", "예상 블록인 시각 (EIBT)",  "Estimated In-Block Time",     pattern=TIME_HMS_PATTERN),
    "arrFatoNumber": Field("str", "",         "도착 FATO 번호",           "Arrival FATO number"),
    "eldt":          Field("str", "HH:MM:SS", "예상 착륙 시각 (ELDT)",    "Estimated Landing Time",      pattern=TIME_HMS_PATTERN),
}

ENROUTE_REQUIRED: Dict[str, Field] = {
    "seq":         Field("int",   "",    "순서 번호",      "Sequence",       range=(1, 9999)),
    "phase":       Field("str",   "",    "단계 식별자",    "Phase letter",   pattern=PHASE_PATTERN),
    "targetSpeed": Field("float", "m/s", "목표 속도",      "Target speed",   range=(0.0, 200.0)),
}

ENROUTE_OPTIONAL: Dict[str, Field] = {
    "turnDirection": Field("str", "", "선회 방향", "Turn direction", choices=TURN_CHOICES),
    # startLLA / endLLA / centerLLA 는 dict — 별도 처리
}

TOP_FIELDS: Dict[str, Field] = {
    "flightPlanNumber": Field("int", "", "정기편 번호",        "Flight plan number",  range=(1, 9_999_999)),
    "planVersion":      Field("int", "", "계획 버전 번호",     "Plan version",        range=(1, 999_999)),
    "planStatus":       Field("str", "", "계획 상태",          "Plan status",         choices=PLAN_STATUSES),
    "aircraftId":       Field("str", "", "비행체 ID",          "Aircraft ID",         pattern=AIRCRAFT_ID_PATTERN),
}


# ----- 내부 검증 유틸 -----

def _validate_section(obj: Dict[str, Any], key: str, fields: Dict[str, Field], errors: List[str]) -> None:
    sec = obj.get(key)
    if sec is None:
        errors.append(f"{key}: 누락")
        return
    if not isinstance(sec, dict):
        errors.append(f"{key}: dict 필요")
        return
    for fname, fspec in fields.items():
        if fname not in sec:
            errors.append(f"{key}.{fname}: 누락")
            continue
        validate_field(sec[fname], fspec, f"{key}.{fname}", errors)


def _validate_lla(lla: Any, path: str, errors: List[str]) -> None:
    if not isinstance(lla, dict):
        errors.append(f"{path}: dict 필요")
        return
    for name, fspec in LLA_FIELDS.items():
        if name not in lla:
            errors.append(f"{path}.{name}: 누락")
            continue
        validate_field(lla[name], fspec, f"{path}.{name}", errors)


def _validate_waypoint(wp: Any, path: str, errors: List[str]) -> None:
    if not isinstance(wp, dict):
        errors.append(f"{path}: dict 필요")
        return
    # required
    for fname, fspec in ENROUTE_REQUIRED.items():
        if fname not in wp:
            errors.append(f"{path}.{fname}: 누락")
            continue
        validate_field(wp[fname], fspec, f"{path}.{fname}", errors)
    # LLA (required)
    if "startLLA" not in wp:
        errors.append(f"{path}.startLLA: 누락")
    else:
        _validate_lla(wp["startLLA"], f"{path}.startLLA", errors)
    if "endLLA" not in wp:
        errors.append(f"{path}.endLLA: 누락")
    else:
        _validate_lla(wp["endLLA"], f"{path}.endLLA", errors)
    # 선회 (optional, 있으면 centerLLA 필수)
    if "turnDirection" in wp:
        validate_field(wp["turnDirection"], ENROUTE_OPTIONAL["turnDirection"],
                       f"{path}.turnDirection", errors)
        if "centerLLA" not in wp:
            errors.append(f"{path}.centerLLA: turnDirection 존재 시 필수")
        else:
            _validate_lla(wp["centerLLA"], f"{path}.centerLLA", errors)


def _validate_enroute(lst: Any, errors: List[str]) -> None:
    if lst is None:
        errors.append("enRoute: 누락")
        return
    if not isinstance(lst, list):
        errors.append("enRoute: list 필요")
        return
    if len(lst) < 1:
        errors.append("enRoute: 최소 1 segment 필요")
        return
    for i, wp in enumerate(lst):
        _validate_waypoint(wp, f"enRoute[{i}]", errors)
    # seq 단조 증가 확인
    seqs = [wp.get("seq") for wp in lst if isinstance(wp, dict)]
    if seqs and any(isinstance(s, int) for s in seqs):
        for a, b in zip(seqs, seqs[1:]):
            if isinstance(a, int) and isinstance(b, int) and b <= a:
                errors.append(f"enRoute.seq 단조 증가 위반 ({a} → {b})")
                break


# ----- 퍼블릭 API -----

def validate_message(obj: Any) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["root: dict 필요"], {}

    # top-level
    for fname, fspec in TOP_FIELDS.items():
        if fname not in obj:
            errors.append(f"{fname}: 누락")
            continue
        validate_field(obj[fname], fspec, fname, errors)
    # aircraftId 추가 패턴 확인 (정규식은 이미 Field.pattern 으로 적용됨)

    _validate_section(obj, "departure", DEPARTURE_FIELDS, errors)
    _validate_section(obj, "arrival", ARRIVAL_FIELDS, errors)
    _validate_enroute(obj.get("enRoute"), errors)

    return (len(errors) == 0), errors, obj
