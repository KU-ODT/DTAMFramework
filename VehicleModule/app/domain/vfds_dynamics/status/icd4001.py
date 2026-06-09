from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Iterable

from .models import AircraftStatus


def utc_now_ms() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _as_pct(value: Any, default: float = 100.0) -> float:
    number = _as_float(value, default)
    return max(0.0, min(100.0, number))


def _as_rpm4(values: Iterable[Any]) -> list[float]:
    rpms = [_as_float(value) for value in list(values)[:4]]
    while len(rpms) < 4:
        rpms.append(0.0)
    return rpms


def _current_waypoint_id(status: AircraftStatus) -> str:
    return f"{int(status.flightPlanNumber or 0)}-{int(status.seq or 0)}"


def _wrap_deg_180(deg: float) -> float:
    return ((deg + 180.0) % 360.0) - 180.0


def _quat_from_euler_rad(roll: float, pitch: float, yaw: float) -> dict[str, float]:
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    return {
        "w": cr * cp * cy + sr * sp * sy,
        "x": sr * cp * cy - cr * sp * sy,
        "y": cr * sp * cy + sr * cp * sy,
        "z": cr * cp * sy - sr * sp * cy,
    }


def _pressure_pa_from_altitude_m(altitude_m: float) -> float:
    base = 1.0 - (2.25577e-5 * altitude_m)
    if base <= 0.0:
        return 10000.0
    return max(10000.0, min(120000.0, 101325.0 * (base ** 5.25588)))


def _energy_from_status(status: AircraftStatus) -> dict[str, Any]:
    """Return 4001 energy block without changing legacy telemetry output.

    The current VFDS mission-script path does not publish a real battery field,
    so this remains 100% exactly like the reference implementation.  If a newer
    VFDS/KP2A runtime sends one of the known optional battery/SOC fields, use it
    for the auxiliary /ws/dtam 4001 feed.
    """

    energy = getattr(status, "energy", {}) or {}
    payload = dict(energy) if isinstance(energy, dict) else {}

    candidates = [
        getattr(status, "batteryPct", None),
        getattr(status, "battery_pct", None),
        getattr(status, "stateOfChargePct", None),
        getattr(status, "state_of_charge_pct", None),
        payload.get("battery_pct"),
        payload.get("state_of_charge_pct"),
        payload.get("batteryPct"),
        payload.get("stateOfChargePct"),
    ]
    battery_pct = 100.0
    for candidate in candidates:
        if candidate is None:
            continue
        battery_pct = _as_pct(candidate, 100.0)
        break

    payload["battery_pct"] = battery_pct
    payload["state_of_charge_pct"] = battery_pct
    return payload


def aircraft_status_to_4001_vehicle(status: AircraftStatus) -> dict[str, Any]:
    position = status.position
    attitude = status.attitude
    velocity = status.velocityNed
    actuator = status.actuator

    # The VFDS dashboard model stores MAVSDK/MAVLink Euler angles in degrees.
    roll_rad = math.radians(_wrap_deg_180(_as_float(attitude.roll)))
    pitch_rad = math.radians(_as_float(attitude.pitch))
    yaw_rad = math.radians(_wrap_deg_180(_as_float(attitude.yaw)))

    lat = _as_float(position.lat)
    lon = _as_float(position.lon)
    alt = _as_float(position.alt)
    gps_valid = not (abs(lat) < 1e-9 and abs(lon) < 1e-9)
    current_waypoint_id = _current_waypoint_id(status)

    return {
        "currentWaypointId": current_waypoint_id,
        "position": {
            "north": _as_float(position.north),
            "east": _as_float(position.east),
            "down": _as_float(position.down),
        },
        "attitude": {
            "roll": roll_rad,
            "pitch": pitch_rad,
            "yaw": yaw_rad,
        },
        "actuator": {
            "tilt_left": _as_float(actuator.tilt_left),
            "tilt_right": _as_float(actuator.tilt_right),
            "aileron": _as_float(actuator.aileron),
            "rudder_left": _as_float(actuator.rudder_left),
            "rudder_right": _as_float(actuator.rudder_right),
        },
        "propulsion": {
            "motor_rpm": _as_rpm4(status.motorRpm),
        },
        "gps": {
            "is_valid": gps_valid,
            "fix_type": 3 if gps_valid else 0,
            "latitude": lat,
            "longitude": lon,
            "altitude": alt,
            "velocity_north": _as_float(velocity.north),
            "velocity_east": _as_float(velocity.east),
            "velocity_down": _as_float(velocity.down),
            "eph": 0.0,
            "epv": 0.0,
        },
        "imu": {
            "orientation": _quat_from_euler_rad(roll_rad, pitch_rad, yaw_rad),
            "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
            "linear_acceleration": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
        "barometer": {
            "altitude": alt,
            "pressure": _pressure_pa_from_altitude_m(alt),
            "qnh": 1013.25,
        },
        "energy": _energy_from_status(status),
        "navigation": {
            "flightPlanNumber": int(status.flightPlanNumber or 0),
            "currentWaypointId": current_waypoint_id,
            "nextWaypointId": current_waypoint_id,
            "targetLLA": {"lat": lat, "lon": lon, "alt": alt},
            "bearingToTargetDeg": 0.0,
            "distanceToTargetM": 0.0,
            "verticalDeltaM": 0.0,
            "source": "VFDS",
        },
    }


def build_vehicle_status_4001(
    statuses: Iterable[AircraftStatus],
    *,
    timestamp: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"timestamp": timestamp or utc_now_ms()}
    for status in statuses:
        payload[status.aircraftId] = aircraft_status_to_4001_vehicle(status)
    return payload


def dumps_vehicle_status_4001(statuses: Iterable[AircraftStatus]) -> str:
    return json.dumps(
        build_vehicle_status_4001(statuses),
        ensure_ascii=False,
        separators=(",", ":"),
    )
