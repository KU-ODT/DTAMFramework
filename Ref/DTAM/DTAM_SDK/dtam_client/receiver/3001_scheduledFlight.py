"""Scheduled Flight (MSG 3001) 수신/파싱기."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from dtam_client.schema.msg_3001 import validate_message


@dataclass
class WaypointSample:
    seq: int
    phase: str
    start_lla: Dict[str, float] = field(default_factory=dict)
    end_lla: Dict[str, float] = field(default_factory=dict)
    target_speed: float = 0.0
    turn_direction: Optional[str] = None
    center_lla: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "seq": self.seq,
            "phase": self.phase,
            "startLLA": self.start_lla,
            "endLLA": self.end_lla,
            "targetSpeed": self.target_speed,
        }
        if self.turn_direction is not None:
            d["turnDirection"] = self.turn_direction
        if self.center_lla is not None:
            d["centerLLA"] = self.center_lla
        return d


@dataclass
class ReceiveResult:
    ok: bool = False
    flight_plan_number: Optional[int] = None
    plan_version: Optional[int] = None
    plan_status: Optional[str] = None
    aircraft_id: Optional[str] = None
    departure: Dict[str, Any] = field(default_factory=dict)
    arrival: Dict[str, Any] = field(default_factory=dict)
    waypoints: List[WaypointSample] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "flightPlanNumber": self.flight_plan_number,
            "planVersion": self.plan_version,
            "planStatus": self.plan_status,
            "aircraftId": self.aircraft_id,
            "departure": self.departure,
            "arrival": self.arrival,
            "waypoints": [w.to_dict() for w in self.waypoints],
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

        result.flight_plan_number = obj.get("flightPlanNumber")
        result.plan_version = obj.get("planVersion")
        result.plan_status = obj.get("planStatus")
        result.aircraft_id = obj.get("aircraftId")
        result.departure = dict(obj.get("departure", {}))
        result.arrival = dict(obj.get("arrival", {}))
        for wp in obj.get("enRoute", []) or []:
            if not isinstance(wp, dict):
                continue
            result.waypoints.append(WaypointSample(
                seq=int(wp.get("seq", 0)),
                phase=str(wp.get("phase", "")),
                start_lla=dict(wp.get("startLLA", {})),
                end_lla=dict(wp.get("endLLA", {})),
                target_speed=float(wp.get("targetSpeed", 0.0)),
                turn_direction=wp.get("turnDirection"),
                center_lla=dict(wp["centerLLA"]) if isinstance(wp.get("centerLLA"), dict) else None,
            ))
        return result
    except Exception as e:
        result.ok = False
        result.errors.append(f"내부 예외: {type(e).__name__}: {e}")
        return result


def extract(data: Union[bytes, str, Dict[str, Any]]) -> Dict[str, Any]:
    return parse(data).to_dict()
