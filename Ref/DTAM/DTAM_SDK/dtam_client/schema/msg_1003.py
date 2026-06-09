"""Scenario Setup (MSG 1003) 스키마."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from .common import (
    Field,
    ISO_DATETIME_PATTERN,
    TIME_HMS_PATTERN,
    validate_field,
)


VERTIPORT_CLASSES = ["port", "hub"]
VEHICLE_TYPES = ["KP2A", "JobyS4"]
WAYPOINT_ID_PATTERN = r"^[A-Za-z0-9_-]{1,32}$"
WAYPOINT_ID_REGEX = re.compile(WAYPOINT_ID_PATTERN)

TOP_FIELDS: Dict[str, Field] = {
    "timestamp":          Field("iso_datetime", "UTC", "송신 시각",       "Send time",          pattern=ISO_DATETIME_PATTERN),
    "scenarioFileName":   Field("str", "",             "시나리오 저장 파일명", "Scenario file name"),
    "totalAircraftCount": Field("int", "",             "총 투입 비행기 수", "Total aircraft count", range=(1, 100000)),
    "mainVehicleType":    Field("str", "",             "대표 비행체 종류",  "Main vehicle type",  choices=VEHICLE_TYPES),
}

OPERATION_TIME_FIELDS: Dict[str, Field] = {
    "startTime": Field("str", "HH:MM:SS", "운용 시작 시각", "Operation start", pattern=TIME_HMS_PATTERN),
    "endTime":   Field("str", "HH:MM:SS", "운용 종료 시각", "Operation end",   pattern=TIME_HMS_PATTERN),
}

VERTIPORT_FIELDS: Dict[str, Field] = {
    "name":         Field("str", "",    "버티포트 이름", "Vertiport name"),
    "class":        Field("str", "",    "버티포트 분류", "Vertiport class", choices=VERTIPORT_CLASSES),
    "lat":          Field("float", "deg", "위도",       "Latitude",        range=(-90.0, 90.0)),
    "lon":          Field("float", "deg", "경도",       "Longitude",       range=(-180.0, 180.0)),
    "angleDegrees": Field("float", "deg", "기준 각도",   "Angle",          range=(0.0, 360.0)),
}

WAYPOINT_FIELDS: Dict[str, Field] = {
    "waypointId":   Field("str", "",    "웨이포인트 ID",   "Waypoint ID",   pattern=WAYPOINT_ID_PATTERN),
    "waypointName": Field("str", "",    "웨이포인트 이름", "Waypoint name"),
    "lat":          Field("float", "deg", "위도",         "Latitude",      range=(-90.0, 90.0)),
    "lon":          Field("float", "deg", "경도",         "Longitude",     range=(-180.0, 180.0)),
    "altFt":        Field("float", "ft",  "고도",         "Altitude",      range=(0.0, 60000.0)),
}


def _validate_dict_fields(obj: Dict[str, Any], fields: Dict[str, Field],
                          path: str, errors: List[str]) -> None:
    for fname, fspec in fields.items():
        if fname not in obj:
            errors.append(f"{path}.{fname}: 누락")
            continue
        validate_field(obj[fname], fspec, f"{path}.{fname}", errors)


def _validate_operation_time(obj: Dict[str, Any], errors: List[str]) -> None:
    ot = obj.get("operationTime")
    if ot is None:
        errors.append("operationTime: 누락")
        return
    if not isinstance(ot, dict):
        errors.append("operationTime: dict 필요")
        return
    _validate_dict_fields(ot, OPERATION_TIME_FIELDS, "operationTime", errors)
    s, e = ot.get("startTime"), ot.get("endTime")
    if isinstance(s, str) and isinstance(e, str) and len(s) == 8 and len(e) == 8:
        if s >= e:
            errors.append(f"operationTime: startTime({s}) < endTime({e}) 이어야 함")


def _validate_vertiports(obj: Dict[str, Any], errors: List[str]) -> None:
    vps = obj.get("vertiports")
    if vps is None:
        errors.append("vertiports: 누락")
        return
    if not isinstance(vps, list):
        errors.append("vertiports: list 필요")
        return
    if len(vps) < 1:
        errors.append("vertiports: 최소 1개 필요")
        return
    names = set()
    for i, vp in enumerate(vps):
        path = f"vertiports[{i}]"
        if not isinstance(vp, dict):
            errors.append(f"{path}: dict 필요")
            continue
        _validate_dict_fields(vp, VERTIPORT_FIELDS, path, errors)
        name = vp.get("name")
        if isinstance(name, str):
            if not name:
                errors.append(f"{path}.name: 빈 문자열 불가")
            elif name in names:
                errors.append(f"{path}.name: 중복 ({name})")
            names.add(name)


def _validate_route_network(obj: Dict[str, Any], errors: List[str]) -> None:
    rn = obj.get("routeNetwork")
    if rn is None:
        errors.append("routeNetwork: 누락")
        return
    if not isinstance(rn, dict):
        errors.append("routeNetwork: dict 필요")
        return
    wps = rn.get("waypoints")
    if wps is None:
        errors.append("routeNetwork.waypoints: 누락")
        return
    if not isinstance(wps, list):
        errors.append("routeNetwork.waypoints: list 필요")
        return
    if len(wps) < 1:
        errors.append("routeNetwork.waypoints: 최소 1개 필요")
        return

    all_ids: set = set()
    for i, wp in enumerate(wps):
        path = f"routeNetwork.waypoints[{i}]"
        if not isinstance(wp, dict):
            errors.append(f"{path}: dict 필요")
            continue
        _validate_dict_fields(wp, WAYPOINT_FIELDS, path, errors)
        wid = wp.get("waypointId")
        if isinstance(wid, str):
            if wid in all_ids:
                errors.append(f"{path}.waypointId: 중복 ({wid})")
            all_ids.add(wid)
        # links
        links = wp.get("links")
        if links is None:
            errors.append(f"{path}.links: 누락")
        elif not isinstance(links, list):
            errors.append(f"{path}.links: list 필요")
        elif len(links) < 1:
            errors.append(f"{path}.links: 최소 1개 필요")

    # links 참조 검증 (2nd pass)
    for i, wp in enumerate(wps):
        if not isinstance(wp, dict):
            continue
        wid = wp.get("waypointId", "")
        links = wp.get("links", [])
        if not isinstance(links, list):
            continue
        seen = set()
        for j, lid in enumerate(links):
            path = f"routeNetwork.waypoints[{i}].links[{j}]"
            if not isinstance(lid, str):
                errors.append(f"{path}: str 필요")
                continue
            if lid == wid:
                errors.append(f"{path}: 자기 자신 참조 불가")
            if lid not in all_ids:
                errors.append(f"{path}: 존재하지 않는 waypointId ({lid})")
            if lid in seen:
                errors.append(f"{path}: 중복 링크 ({lid})")
            seen.add(lid)


def validate_message(obj: Any) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["root: dict 필요"], {}

    for name, fspec in TOP_FIELDS.items():
        if name not in obj:
            errors.append(f"{name}: 누락")
            continue
        validate_field(obj[name], fspec, name, errors)

    _validate_operation_time(obj, errors)
    _validate_vertiports(obj, errors)
    _validate_route_network(obj, errors)

    return (len(errors) == 0), errors, obj
