"""MSG 4001 — Vehicle Status (UDP, 주기적)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..schema.msg_4001 import validate_message
from .._config import get_config
from .._result import PushResult
from .._transport import send_udp


def push_vehicle_status(
    data: Dict[str, Any],
    *,
    target_ip: Optional[str] = None,
    target_port: Optional[int] = None,
) -> PushResult:
    """비행체 상태 정보를 서버로 전송한다 (UDP).

    data 는 timestamp + 1대 이상의 비행체 키(aircraftId)로 구성된다.

    Example::

        push_vehicle_status({
            "timestamp": "2026-04-16T10:00:00.000Z",
            "UAM0001": {
                "currentWaypointId": "1201-3",
                "position":  {"north": 120.0, "east": 340.0, "down": -150.0},
                "attitude":  {"roll": 0.01, "pitch": -0.02, "yaw": 1.57},
                "actuator":  {
                    "tilt_left": 0.5, "tilt_right": 0.5,
                    "aileron": 0.0, "rudder_left": 0.0, "rudder_right": 0.0,
                },
                "propulsion": {"motor_rpm": [3200.0, 3200.0, 3200.0, 3200.0]},
                "gps": {
                    "is_valid": True, "fix_type": 3,
                    "latitude": 37.525, "longitude": 126.921, "altitude": 150.0,
                    "velocity_north": 10.0, "velocity_east": 5.0, "velocity_down": 0.0,
                    "eph": 1.2, "epv": 1.5,
                },
                "imu": {
                    "orientation":         {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0},
                    "angular_velocity":    {"x": 0.0, "y": 0.0, "z": 0.0},
                    "linear_acceleration": {"x": 0.0, "y": 0.0, "z": -9.8},
                },
                "barometer": {"altitude": 150.0, "pressure": 100000.0, "qnh": 1013.25},
            },
        })
    """
    cfg = get_config()
    ip   = target_ip   or cfg.server_ip
    port = target_port or cfg.udp_port
    result = PushResult(target=f"{ip}:{port}", payload=data)

    ok, errors, _ = validate_message(data)
    if not ok:
        result.errors.extend(errors)
        return result

    return send_udp(ip, port, data)
