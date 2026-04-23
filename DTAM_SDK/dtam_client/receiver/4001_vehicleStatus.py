"""Vehicle Status (MSG 4001) 수신/파싱기.

bytes / str / dict 수용. parse() 는 절대 raise 하지 않음.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from dtam_client.schema.msg_4001 import validate_message


@dataclass
class VehicleSample:
    vehicle_id: str
    current_waypoint_id: str = ""
    position: Dict[str, float] = field(default_factory=dict)
    attitude: Dict[str, float] = field(default_factory=dict)
    actuator: Dict[str, float] = field(default_factory=dict)
    motor_rpm: List[float] = field(default_factory=list)
    gps: Dict[str, Any] = field(default_factory=dict)
    imu: Dict[str, Any] = field(default_factory=dict)
    barometer: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "currentWaypointId": self.current_waypoint_id,
            "position": self.position,
            "attitude": self.attitude,
            "actuator": self.actuator,
            "motor_rpm": self.motor_rpm,
            "gps": self.gps,
            "imu": self.imu,
            "barometer": self.barometer,
        }


@dataclass
class ReceiveResult:
    ok: bool = False
    timestamp: Optional[str] = None
    vehicles: List[VehicleSample] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "timestamp": self.timestamp,
            "vehicles": [v.to_dict() for v in self.vehicles],
            "errors": self.errors,
        }


def _coerce_dict(data: Union[bytes, str, Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if isinstance(data, dict):
        return data, None
    try:
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        if isinstance(data, str):
            return json.loads(data), None
        return None, f"지원하지 않는 입력 타입: {type(data).__name__}"
    except UnicodeDecodeError as e:
        return None, f"UTF-8 디코드 실패: {e}"
    except json.JSONDecodeError as e:
        return None, f"JSON 파싱 실패: {e}"


def parse(data: Union[bytes, str, Dict[str, Any]]) -> ReceiveResult:
    result = ReceiveResult()
    try:
        obj, err = _coerce_dict(data)
        if err:
            result.errors.append(err)
            return result
        result.raw = obj

        ok, errors, _ = validate_message(obj)
        result.ok = ok
        result.errors.extend(errors)
        if not ok:
            return result

        result.timestamp = obj.get("timestamp")
        for key, val in obj.items():
            if key == "timestamp":
                continue
            if not isinstance(val, dict):
                continue
            sample = VehicleSample(
                vehicle_id=key,
                current_waypoint_id=str(val.get("currentWaypointId", "")),
                position=dict(val.get("position", {})),
                attitude=dict(val.get("attitude", {})),
                actuator=dict(val.get("actuator", {})),
                motor_rpm=list(val.get("propulsion", {}).get("motor_rpm", [])),
                gps=dict(val.get("gps", {})),
                imu=dict(val.get("imu", {})),
                barometer=dict(val.get("barometer", {})),
            )
            result.vehicles.append(sample)
        return result
    except Exception as e:
        result.ok = False
        result.errors.append(f"내부 예외: {type(e).__name__}: {e}")
        return result


def extract(data: Union[bytes, str, Dict[str, Any]]) -> Dict[str, Any]:
    return parse(data).to_dict()
