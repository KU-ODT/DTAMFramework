"""Vehicle Status (MSG 4001) 스키마 — generator/pusher/receiver 공유."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from .common import (
    Field,
    ISO_DATETIME_PATTERN,
    VEHICLE_ID_PATTERN,
    VEHICLE_ID_REGEX,
    validate_field,
)


VEHICLE_SCHEMA: Dict[str, Dict[str, Field]] = {
    "position": {
        "north": Field("float", "m", "NED 북쪽", "NED north", range=(-10000.0, 10000.0)),
        "east":  Field("float", "m", "NED 동쪽", "NED east",  range=(-10000.0, 10000.0)),
        "down":  Field("float", "m", "NED 아래(음수=고도)", "NED down", range=(-5000.0, 500.0)),
    },
    "attitude": {
        "roll":  Field("float", "rad", "롤",   "Roll",  range=(-math.pi, math.pi)),
        "pitch": Field("float", "rad", "피치", "Pitch", range=(-math.pi/2, math.pi/2)),
        "yaw":   Field("float", "rad", "요",   "Yaw",   range=(-math.pi, math.pi)),
    },
    "actuator": {
        "tilt_left":    Field("float", "0..1", "좌측 틸트", "Left tilt",   range=(0.0, 1.0)),
        "tilt_right":   Field("float", "0..1", "우측 틸트", "Right tilt",  range=(0.0, 1.0)),
        "aileron":      Field("float", "deg",  "에일러론",   "Aileron",     range=(-30.0, 30.0)),
        "rudder_left":  Field("float", "deg",  "좌측 러더", "Left rudder", range=(-30.0, 30.0)),
        "rudder_right": Field("float", "deg",  "우측 러더", "Right rudder",range=(-30.0, 30.0)),
    },
    "propulsion": {
        "motor_rpm": Field("list[float]", "rpm", "모터 RPM 4채널", "Motor RPM 4-ch",
                           length=4, item_range=(0.0, 6000.0)),
    },
    "gps": {
        "is_valid":       Field("bool", "",    "GPS 유효 플래그",      "GPS validity flag"),
        "fix_type":       Field("int",  "",    "GNSS 수신 유형",       "GNSS fix type",        range=(0, 3)),
        "latitude":       Field("float", "deg", "WGS84 위도",          "WGS84 latitude",       range=(-90.0, 90.0)),
        "longitude":      Field("float", "deg", "WGS84 경도",          "WGS84 longitude",      range=(-180.0, 180.0)),
        "altitude":       Field("float", "m",   "WGS84 고도",          "WGS84 altitude",       range=(-1000.0, 20000.0)),
        "velocity_north": Field("float", "m/s", "NED 북쪽 속도",       "NED north velocity",   range=(-1000.0, 1000.0)),
        "velocity_east":  Field("float", "m/s", "NED 동쪽 속도",       "NED east velocity",    range=(-1000.0, 1000.0)),
        "velocity_down":  Field("float", "m/s", "NED 아래 속도",       "NED down velocity",    range=(-1000.0, 1000.0)),
        "eph":            Field("float", "",    "수평 위치 오차",       "Horizontal position error", range=(0.0, 100.0)),
        "epv":            Field("float", "",    "수직 위치 오차",       "Vertical position error",   range=(0.0, 100.0)),
    },
    "imu": {
        "orientation":          Field("dict", "",      "자세 쿼터니언",          "Orientation quaternion"),
        "angular_velocity":     Field("dict", "rad/s", "각속도 벡터",            "Angular velocity vector"),
        "linear_acceleration":  Field("dict", "m/s²",  "선형 가속도 벡터",       "Linear acceleration vector"),
    },
    "barometer": {
        "altitude": Field("float", "m",   "기압 고도",     "Barometric altitude",  range=(-1000.0, 20000.0)),
        "pressure": Field("float", "Pa",  "대기압",        "Air pressure",         range=(10000.0, 120000.0)),
        "qnh":      Field("float", "hPa", "해면 기압 설정", "Sea-level pressure",  range=(800.0, 1200.0)),
    },
}

TOP_SCHEMA: Dict[str, Field] = {
    "timestamp": Field("iso_datetime", "UTC", "송신 시각 ISO-8601", "Send time ISO-8601",
                       pattern=ISO_DATETIME_PATTERN),
}

# 비행체 최상위 필드 (그룹이 아닌 단독 필드)
WAYPOINT_ID_PATTERN = r"^\d+-(\d+|[A-Za-z0-9]+-[A-Za-z0-9]+)$"
VEHICLE_TOP_FIELDS: Dict[str, Field] = {
    "currentWaypointId": Field("str", "", "현재 목표 웨이포인트 ID", "Current target waypoint ID",
                               pattern=WAYPOINT_ID_PATTERN),
}


IMU_ORIENTATION_FIELDS: Dict[str, Field] = {
    "w": Field("float", "", "쿼터니언 W", "Quaternion W", range=(-1.0, 1.0)),
    "x": Field("float", "", "쿼터니언 X", "Quaternion X", range=(-1.0, 1.0)),
    "y": Field("float", "", "쿼터니언 Y", "Quaternion Y", range=(-1.0, 1.0)),
    "z": Field("float", "", "쿼터니언 Z", "Quaternion Z", range=(-1.0, 1.0)),
}

IMU_VEC3_ANGULAR: Dict[str, Field] = {
    "x": Field("float", "rad/s", "각속도 X", "Angular velocity X", range=(-100.0, 100.0)),
    "y": Field("float", "rad/s", "각속도 Y", "Angular velocity Y", range=(-100.0, 100.0)),
    "z": Field("float", "rad/s", "각속도 Z", "Angular velocity Z", range=(-100.0, 100.0)),
}

IMU_VEC3_LINEAR: Dict[str, Field] = {
    "x": Field("float", "m/s²", "선형가속도 X", "Linear accel X", range=(-200.0, 200.0)),
    "y": Field("float", "m/s²", "선형가속도 Y", "Linear accel Y", range=(-200.0, 200.0)),
    "z": Field("float", "m/s²", "선형가속도 Z", "Linear accel Z", range=(-200.0, 200.0)),
}


def _validate_sub_dict(obj: Dict[str, Any], path: str, fields: Dict[str, Field], errors: List[str]) -> None:
    if not isinstance(obj, dict):
        errors.append(f"{path}: dict 필요")
        return
    for fname, fspec in fields.items():
        if fname not in obj:
            errors.append(f"{path}.{fname}: 누락")
            continue
        validate_field(obj[fname], fspec, f"{path}.{fname}", errors)


def _validate_imu(imu: Dict[str, Any], path: str, errors: List[str]) -> None:
    """imu 하위 구조 커스텀 검증 (orientation/angular_velocity/linear_acceleration)."""
    for key, sub_fields in (
        ("orientation", IMU_ORIENTATION_FIELDS),
        ("angular_velocity", IMU_VEC3_ANGULAR),
        ("linear_acceleration", IMU_VEC3_LINEAR),
    ):
        sub = imu.get(key)
        if sub is None:
            errors.append(f"{path}.{key}: 누락")
            continue
        _validate_sub_dict(sub, f"{path}.{key}", sub_fields, errors)


def validate_vehicle(v: Any, path: str, errors: List[str]) -> None:
    if not isinstance(v, dict):
        errors.append(f"{path}: dict 필요")
        return
    # 비행체 최상위 필드
    for fname, fspec in VEHICLE_TOP_FIELDS.items():
        if fname not in v:
            errors.append(f"{path}.{fname}: 누락")
            continue
        validate_field(v[fname], fspec, f"{path}.{fname}", errors)
    # 그룹별 검증
    for group, fields in VEHICLE_SCHEMA.items():
        sub = v.get(group)
        if sub is None:
            errors.append(f"{path}.{group}: 누락")
            continue
        if not isinstance(sub, dict):
            errors.append(f"{path}.{group}: dict 필요")
            continue
        # imu 는 하위 dict 구조를 커스텀 검증
        if group == "imu":
            _validate_imu(sub, f"{path}.{group}", errors)
            continue
        for fname, fspec in fields.items():
            if fname not in sub:
                errors.append(f"{path}.{group}.{fname}: 누락")
                continue
            validate_field(sub[fname], fspec, f"{path}.{group}.{fname}", errors)


def validate_message(obj: Any) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["root: dict 필요"], {}

    normalized: Dict[str, Any] = {}
    if "timestamp" not in obj:
        errors.append("timestamp: 누락")
    else:
        validate_field(obj["timestamp"], TOP_SCHEMA["timestamp"], "timestamp", errors)
        normalized["timestamp"] = obj["timestamp"]

    vehicle_keys = [k for k in obj.keys() if k != "timestamp"]
    if not vehicle_keys:
        errors.append("vehicles: 최소 1대 필요")
    for vid in vehicle_keys:
        if not VEHICLE_ID_REGEX.match(vid):
            errors.append(f"{vid}: 비행체 ID 패턴 불일치 ({VEHICLE_ID_PATTERN})")
        validate_vehicle(obj[vid], vid, errors)
        normalized[vid] = obj[vid]

    return (len(errors) == 0), errors, normalized
