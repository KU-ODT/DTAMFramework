"""AirMobility 도메인 타입 정의.

- ``ClockMode`` / ``VehicleState`` — enum
- ``VehicleStatus`` / ``FleetStatus`` — status 보고 dataclass
- ``_parse_hhmmss_to_s`` / ``_s_to_hhmmss`` — 시간 변환 유틸
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ClockMode(str, Enum):
    EXTERNAL = "external"   # 외부에서 feed_time_* 호출
    WALL = "wall"           # 내부 실시간 시계
    MANUAL = "manual"       # step_once(t) 를 직접 호출


class VehicleState(str, Enum):
    WAITING = "waiting"     # etot 이전 (또는 plan 방금 등록)
    ACTIVE = "active"       # engine 실행 중, 4001 송출 중
    COMPLETED = "completed" # 궤적 끝
    ERROR = "error"


@dataclass
class VehicleStatus:
    vehicle_id: str
    flight_plan_number: int
    state: VehicleState
    etot_s: float
    elapsed_s: float
    total_duration_s: float
    last_point: Optional[Dict[str, Any]] = None
    last_error: str = ""


@dataclass
class FleetStatus:
    clock_mode: str
    running: bool
    publisher_connected: bool
    publisher_error: str
    sim_time_s: float
    sim_time_hms: str
    vehicles: List[VehicleStatus] = field(default_factory=list)
    rx_3001_count: int = 0
    rx_0003_count: int = 0
    last_rx_3001: str = ""
    last_rx_0003: str = ""
    rx_2002_count: int = 0
    rx_3002_count: int = 0
    rx_3003_count: int = 0
    last_rx_2002: str = ""
    last_rx_3002: str = ""
    last_rx_3003: str = ""
    last_heartbeat_error: str = ""


def parse_hhmmss_to_s(text: str) -> float:
    parts = str(text).split(":")
    if len(parts) != 3:
        raise ValueError(f"expected HH:MM:SS, got {text!r}")
    h, m, s = parts
    return float(int(h) * 3600 + int(m) * 60 + float(s))


def s_to_hhmmss(total_s: float) -> str:
    total = max(0.0, float(total_s))
    h = int(total // 3600) % 24
    m = int((total % 3600) // 60)
    s = int(total) % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


__all__ = [
    "ClockMode",
    "VehicleState",
    "VehicleStatus",
    "FleetStatus",
    "parse_hhmmss_to_s",
    "s_to_hhmmss",
]
