"""
VFDS Dynamics Dispatch System — Receiver 수신 모델

HTTP API 응답 및 내부 처리 결과를 표현하는 모델.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MissionAcceptedResponse:
    """미션 접수 성공 응답"""
    mission_id: str
    flight_plan_number: int
    aircraft_id: str
    status: str = "QUEUED"
    message: str = "Mission accepted and queued for processing."

    def to_dict(self) -> dict:
        return {
            "missionId": self.mission_id,
            "flightPlanNumber": self.flight_plan_number,
            "aircraftId": self.aircraft_id,
            "status": self.status,
            "message": self.message,
        }


@dataclass
class BatchResponse:
    """배치 처리 결과 응답"""
    total: int = 0
    accepted: int = 0
    rejected: int = 0
    results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "results": self.results,
        }
