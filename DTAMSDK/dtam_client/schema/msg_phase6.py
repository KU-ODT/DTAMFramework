"""Phase 6 메시지 — 3002 Strategic Separation, 3003 Tactical Separation."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from .icd_common import LLA


# ── MSG 3002 ─────────────────────────────────────────────

@dataclass
class Msg3002_StrategicSeparation:
    """MSG 3002: 전략적 분리 — 비행계획 수정 명령."""
    timestamp: str = ""
    commandId: str = ""
    flightPlanNumber: int = 0
    planVersion: int = 1
    aircraftId: str = ""
    modificationType: str = ""         # scheduleResourceUpdate|routeUpdate|aircraftSwap|delayOnly|cancelPlan
    reasonCode: str = ""               # VERTIPORT_CAPACITY|CORRIDOR_CLOSED|WEATHER|VEHICLE_UNAVAILABLE|OPERATOR_REQUEST
    modifyScope: str = ""              # departureOnly|arrivalOnly|departureAndArrival|enRouteOnly|aircraftOnly|fullPlan


# ── MSG 3003 ─────────────────────────────────────────────

@dataclass
class DirectToTarget:
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    targetSpeed: float = 0.0


@dataclass
class HoldAction:
    holdLLA: LLA = field(default_factory=LLA)
    turnDirection: str = "CW"          # CW | CCW
    holdingRadiusM: float = 100.0
    maxHoldingCount: int = 1


@dataclass
class LandAction:
    targetLLA: Optional[LLA] = None
    vertiport: Optional[str] = None
    fatoNumber: Optional[str] = None


@dataclass
class TacticalAction:
    """전술 명령 단위. type에 따라 해당 필드만 사용."""
    type: str = ""                     # setSpeed|directTo|hold|rejoinPlan|land
    targetSpeed: Optional[float] = None
    targetLLAs: Optional[List[DirectToTarget]] = None
    holdLLA: Optional[LLA] = None
    turnDirection: Optional[str] = None
    holdingRadiusM: Optional[float] = None
    maxHoldingCount: Optional[int] = None
    atSeq: Optional[int] = None
    targetLLA: Optional[LLA] = None
    vertiport: Optional[str] = None
    fatoNumber: Optional[str] = None


@dataclass
class Msg3003_TacticalSeparation:
    """MSG 3003: 전술적 분리 — 실시간 분리 명령."""
    timestamp: str = ""
    commandId: str = ""
    aircraftId: str = ""
    reasonCode: str = ""               # LOSS_OF_SEPARATION_RISK|LOCAL_CORRIDOR_BLOCKED|LOW_BATTERY|WEATHER_AVOIDANCE|OPERATOR_OVERRIDE|EMERGENCY_LANDING
    actions: List[TacticalAction] = field(default_factory=list)
