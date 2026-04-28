"""DTAM MSG 4001 (Vehicle Status) payload builder.

Trajectory 포인트 + 좌표 변환 프레임 → 4001 dict.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from ..domain.transform.coord_transform import LocalNEDFrame, heading_to_ned_velocity


@dataclass
class VehiclePublishContext:
    """한 비행체의 4001 메시지 생성을 위한 컨텍스트.

    origin_frame 은 position(NED) 계산용 기준점.
    current_waypoint_id 는 매 tick 호출측에서 갱신한다.
    """
    vehicle_id: str                      # ``^[A-Z]{2,8}\\d{4}$``
    flight_plan_number: int
    origin_frame: LocalNEDFrame
    departure_vertiport: str = ""
    departure_gate: str = ""
    arrival_vertiport: str = ""
    arrival_gate: str = ""
    current_waypoint_id: str = ""
    battery_pct: float = 100.0


def iso_timestamp(dt: Optional[datetime] = None) -> str:
    """``YYYY-MM-DDTHH:MM:SS.sssZ`` (UTC)."""
    now = dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _yaw_to_quaternion(yaw_rad: float) -> Dict[str, float]:
    half = 0.5 * float(yaw_rad)
    return {
        "w": float(math.cos(half)),
        "x": 0.0,
        "y": 0.0,
        "z": float(math.sin(half)),
    }


def _clamp(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _wrap_pi(angle_rad: float) -> float:
    """[-π, π] 범위로 래핑."""
    a = float(angle_rad)
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


def _estimate_motor_rpm(speed_mps: float, climb_mps: float) -> Tuple[float, float, float, float]:
    """단순 휴리스틱 — 실제 다이나믹스 엔진이 아닌 시각화용.

    4001 스키마가 motor_rpm (0..6000) 4-채널을 요구하므로 값만 그럴듯하게 채운다.
    """
    base = 2000.0
    base += min(max(abs(speed_mps), 0.0), 60.0) * 30.0
    base += max(climb_mps, 0.0) * 150.0
    base = _clamp(base, 0.0, 6000.0)
    # 미세한 채널별 차이
    return (base, base * 1.01, base * 0.99, base * 1.005)


def build_vehicle_payload(
    *,
    context: VehiclePublishContext,
    lat: float,
    lon: float,
    alt_m: float,
    speed_mps: float,
    heading_deg: float,
    track_heading_deg: Optional[float] = None,
    pitch_rad: float = 0.0,
    roll_rad: float = 0.0,
    climb_rate_mps: float = 0.0,
    phase: str = "",
    seq: Optional[int] = None,
    battery_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """Trajectory 한 포인트 → 4001 의 한 비행체 서브-dict."""
    north_m, east_m, down_m = context.origin_frame.to_ned(lat, lon, alt_m)
    # 스키마 범위 방어 — 스키마는 -10000..10000 m 제한
    north_m = _clamp(north_m, -9999.9, 9999.9)
    east_m = _clamp(east_m, -9999.9, 9999.9)
    down_m = _clamp(down_m, -4999.9, 499.9)

    yaw_rad = _wrap_pi(math.radians(float(heading_deg)))
    pitch_clamped = _clamp(float(pitch_rad), -math.pi / 2, math.pi / 2)
    roll_clamped = _clamp(_wrap_pi(float(roll_rad)), -math.pi, math.pi)

    track_deg = float(track_heading_deg) if track_heading_deg is not None else float(heading_deg)
    vn, ve, _ = heading_to_ned_velocity(float(speed_mps), track_deg)
    vd = -float(climb_rate_mps)

    motor_rpm = list(_estimate_motor_rpm(float(speed_mps), float(climb_rate_mps)))
    batt = float(battery_pct) if battery_pct is not None else float(context.battery_pct)

    waypoint_id = context.current_waypoint_id
    if not waypoint_id:
        if seq is not None:
            waypoint_id = f"{context.flight_plan_number}-{int(seq)}"
        elif context.departure_vertiport and context.departure_gate:
            waypoint_id = (
                f"{context.flight_plan_number}-"
                f"{context.departure_vertiport}-{context.departure_gate}"
            )
        else:
            waypoint_id = f"{context.flight_plan_number}-1"

    return {
        "currentWaypointId": str(waypoint_id),
        "position": {
            "north": float(north_m),
            "east": float(east_m),
            "down": float(down_m),
        },
        "attitude": {
            "roll": float(roll_clamped),
            "pitch": float(pitch_clamped),
            "yaw": float(yaw_rad),
        },
        "actuator": {
            "tilt_left": 0.5,
            "tilt_right": 0.5,
            "aileron": 0.0,
            "rudder_left": 0.0,
            "rudder_right": 0.0,
        },
        "propulsion": {
            "motor_rpm": [float(r) for r in motor_rpm],
        },
        "gps": {
            "is_valid": True,
            "fix_type": 3,
            "latitude": _clamp(float(lat), -90.0, 90.0),
            "longitude": _clamp(float(lon), -180.0, 180.0),
            "altitude": _clamp(float(alt_m), -1000.0, 20000.0),
            "velocity_north": _clamp(float(vn), -1000.0, 1000.0),
            "velocity_east": _clamp(float(ve), -1000.0, 1000.0),
            "velocity_down": _clamp(float(vd), -1000.0, 1000.0),
            "eph": 0.8,
            "epv": 1.2,
        },
        "imu": {
            "orientation": _yaw_to_quaternion(yaw_rad),
            "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
            "linear_acceleration": {"x": 0.0, "y": 0.0, "z": -9.8},
        },
        "barometer": {
            "altitude": _clamp(float(alt_m), -1000.0, 20000.0),
            "pressure": 101325.0,
            "qnh": 1013.25,
        },
        "_battery_pct": float(batt),  # 내부 추적용(4001 스키마 외)
    }


def build_4001_message(
    vehicle_payloads: Dict[str, Dict[str, Any]],
    *,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """여러 비행체 서브-payload 를 하나의 4001 메시지로 묶는다."""
    ts = timestamp or iso_timestamp()
    message: Dict[str, Any] = {"timestamp": ts}
    for vid, payload in vehicle_payloads.items():
        scrubbed = {k: v for k, v in payload.items() if not k.startswith("_")}
        message[str(vid)] = scrubbed
    return message
