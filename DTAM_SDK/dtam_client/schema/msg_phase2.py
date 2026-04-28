"""Phase 2/3 메시지 — 2001, 2002, 3001."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from .icd_common import LLA


# ── MSG 2001 ─────────────────────────────────────────────

@dataclass
class Msg2001_FlightPlanRequest:
    """MSG 2001: 비행계획 요청."""
    timestamp: str = ""
    scenarioFileName: str = ""


# ── MSG 2002 ─────────────────────────────────────────────

@dataclass
class Msg2002_DtamExecute:
    """MSG 2002: DTAM 실행 — 각 모듈에 실행 명령 전달."""
    timestamp: str = ""
    simModeFileName: str = ""
    simulationSetupFileName: str = ""
    scenarioFileName: str = ""
    flightPlanFolderName: str = ""


# ── MSG 3001 ─────────────────────────────────────────────

@dataclass
class DepartureInfo:
    vertiport: str = ""
    std: str = ""                      # HH:MM:SS
    depGateNumber: str = ""
    eobt: str = ""
    depFatoNumber: str = ""
    etot: str = ""


@dataclass
class ArrivalInfo:
    vertiport: str = ""
    sta: str = ""
    arrGateNumber: str = ""
    eibt: str = ""
    arrFatoNumber: str = ""
    eldt: str = ""


@dataclass
class EnRouteSegment:
    seq: int = 0
    phase: str = ""                    # A, B, C, ...
    targetSpeed: float = 0.0           # m/s
    startLLA: LLA = field(default_factory=LLA)
    endLLA: LLA = field(default_factory=LLA)
    turnDirection: Optional[str] = None  # CW | CCW
    centerLLA: Optional[LLA] = None


@dataclass
class Msg3001_ScheduledFlight:
    """MSG 3001: 계획 비행 — 정기편 전체 경로."""
    flightPlanNumber: int = 0
    planVersion: int = 1
    planStatus: str = "active"         # active | superseded | discarded
    aircraftId: str = ""               # UAM0001 등
    departure: DepartureInfo = field(default_factory=DepartureInfo)
    arrival: ArrivalInfo = field(default_factory=ArrivalInfo)
    enRoute: List[EnRouteSegment] = field(default_factory=list)
