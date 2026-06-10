"""Phase 2/3 메시지 — 2001, 2002, 3001."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field, fields as _dc_fields
from typing import Any, Dict, List, Optional

from .icd_common import LLA


# ── MSG 2001 ─────────────────────────────────────────────

@dataclass
class Msg2001_FlightPlanRequest:
    """MSG 2001: 비행계획 요청 (초기 + 재계획 트리거).

    초기 계획 요청 (S1 정상): OperationModule 이 ``scenarioFileName`` 으로
    Mission 에 plan 생성 요청.

    재계획 트리거 (S2 PSU 회랑 충돌 회피 / S3 UAO 배터리 대체 vertiport):
    PSU/UAO 가 4개 optional 필드로 어느 plan 을 왜 (어떤 4002 eventId)
    어디로 (대체 vertiport hint) 재계획해야 하는지 Mission 에 전달.

    Mission 은 이 트리거를 받아 본래 의도대로 3001 v2 (revised plan) +
    3002 (modification header) + 필요 시 3003 (즉시 land action) 를 발행.

    Wire format::

        {
          "timestamp": "<ISO-8601 UTC>",
          "scenarioFileName": "<filename>",
          // optional — 재계획 트리거인 경우
          "flightPlanNumber": 1234,
          "reasonCode": "LOW_BATTERY",
          "triggeringEventId": "WARN-UAM0001-20260610-0001",
          "arrivalVertiportHint": "VP_KU"
        }
    """
    timestamp: str = ""
    scenarioFileName: str = ""
    # ─ Re-plan 트리거용 (모두 optional) ─────────────────────
    flightPlanNumber: Optional[int] = None             # 개정 대상 3001 번호 (없으면 신규 plan)
    reasonCode: Optional[str] = None                   # LOW_BATTERY | BATTERY_OVERHEAT | BATTERY_VOLTAGE_LOW |
                                                       # TRAFFIC_CONFLICT | LOSS_OF_SEPARATION_RISK |
                                                       # CORRIDOR_BLOCKED | WEATHER |
                                                       # VERTIPORT_CAPACITY | VERTIPORT_UNAVAILABLE |
                                                       # OPERATOR_REQUEST
    triggeringEventId: Optional[str] = None            # 4002.eventId / 4103.eventId 등 인과 chain
    arrivalVertiportHint: Optional[str] = None         # PSU/UAO 가 제안하는 대체 도착 vertiport ID

    def to_wire(self) -> Dict[str, Any]:
        """dataclass → ICD wire dict — optional 필드 중 None 인 것은 제외."""
        payload: Dict[str, Any] = {
            "timestamp": self.timestamp,
            "scenarioFileName": self.scenarioFileName,
        }
        if self.flightPlanNumber is not None:
            payload["flightPlanNumber"] = self.flightPlanNumber
        if self.reasonCode is not None:
            payload["reasonCode"] = self.reasonCode
        if self.triggeringEventId is not None:
            payload["triggeringEventId"] = self.triggeringEventId
        if self.arrivalVertiportHint is not None:
            payload["arrivalVertiportHint"] = self.arrivalVertiportHint
        return payload

    @classmethod
    def from_wire(cls, data: Dict[str, Any]) -> "Msg2001_FlightPlanRequest":
        """ICD wire dict → dataclass — 알 수 없는 key 는 무시 (forward-compat).

        ``to_wire()`` 와 대칭. Mission 측 consumer 가 미래에 추가될 필드를
        만나도 깨지지 않도록 known field 만 골라서 인스턴스화.
        """
        if not isinstance(data, dict):
            return cls()
        known = {f.name for f in _dc_fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(**kwargs)


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

    def to_wire(self) -> dict:
        payload = asdict(self)
        for segment in payload.get("enRoute", []) or []:
            if not isinstance(segment, dict):
                continue
            if segment.get("turnDirection") is None:
                segment.pop("turnDirection", None)
            if segment.get("centerLLA") is None:
                segment.pop("centerLLA", None)
        return payload
