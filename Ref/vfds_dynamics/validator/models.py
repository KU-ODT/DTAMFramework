"""
Mission ICD v1 — Pydantic v2 데이터 모델

ICD v1 §3~§5에 정의된 Canonical JSON 구조를 1:1 매핑한다.
모든 필드 제약 조건과 조건부 필수 로직(Phase D/H 회전 필드)을 포함한다.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ──────────────────────────── Enums ────────────────────────────

class PhaseCode(str, Enum):
    """ICD v1 §5 — 미션 프로파일 Phase 코드"""
    A = "A"   # gate out taxi
    B = "B"   # vertical takeoff
    C = "C"   # departure transition
    D = "D"   # departure turn (회전)
    E = "E"   # climb out
    F = "F"   # cruise
    G = "G"   # arrival transition
    H = "H"   # arrival turn (회전)
    I = "I"   # final approach
    J = "J"   # landing
    K = "K"   # gate in taxi


# 회전 세그먼트 Phase 집합
TURN_PHASES: frozenset[PhaseCode] = frozenset({PhaseCode.D, PhaseCode.H})

# HH:MM:SS 시간 형식 정규식
_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


# ──────────────────────────── LLA ────────────────────────────

class LLA(BaseModel):
    """
    ICD v1 §4.4 — 위경도·고도 좌표 객체

    - lat: 위도 (degree), -90 ~ 90
    - lon: 경도 (degree), -180 ~ 180
    - alt: 고도 (m), >= 0
    """
    lat: float = Field(..., ge=-90.0, le=90.0, description="위도 (degree)")
    lon: float = Field(..., ge=-180.0, le=180.0, description="경도 (degree)")
    alt: float = Field(..., ge=0.0, description="고도 (m)")


# ──────────────────────────── Departure ────────────────────────

class Departure(BaseModel):
    """
    ICD v1 §4.2 — 출발 정보

    시간 필드는 모두 HH:MM:SS 문자열이다.
    """
    vertiport: str = Field(..., min_length=1, description="출발 버티포트 이름")
    std: str = Field(..., description="Scheduled Time of Departure (HH:MM:SS)")
    depGateNumber: str = Field(..., min_length=1, description="출발 게이트 번호")
    eobt: str = Field(..., description="Estimated Off-Block Time (HH:MM:SS)")
    depFatoNumber: str = Field(..., min_length=1, description="출발 FATO 번호")
    etot: str = Field(..., description="Estimated Takeoff Time (HH:MM:SS)")

    @model_validator(mode="after")
    def _validate_time_format(self) -> "Departure":
        for field_name in ("std", "eobt", "etot"):
            value = getattr(self, field_name)
            if not _TIME_RE.match(value):
                raise ValueError(
                    f"departure.{field_name} must be HH:MM:SS format, got '{value}'"
                )
        return self


# ──────────────────────────── Arrival ─────────────────────────

class Arrival(BaseModel):
    """
    ICD v1 §4.6 — 도착 정보

    시간 필드는 모두 HH:MM:SS 문자열이다.
    """
    vertiport: str = Field(..., min_length=1, description="도착 버티포트 이름")
    sta: str = Field(..., description="Scheduled Time of Arrival (HH:MM:SS)")
    arrGateNumber: str = Field(..., min_length=1, description="도착 게이트 번호")
    eibt: str = Field(..., description="Estimated In-Block Time (HH:MM:SS)")
    arrFatoNumber: str = Field(..., min_length=1, description="도착 FATO 번호")
    eldt: str = Field(..., description="Estimated Landing Time (HH:MM:SS)")

    @model_validator(mode="after")
    def _validate_time_format(self) -> "Arrival":
        for field_name in ("sta", "eibt", "eldt"):
            value = getattr(self, field_name)
            if not _TIME_RE.match(value):
                raise ValueError(
                    f"arrival.{field_name} must be HH:MM:SS format, got '{value}'"
                )
        return self


# ──────────────────────────── EnRouteSegment ──────────────────

class EnRouteSegment(BaseModel):
    """
    ICD v1 §4.3 + §4.5 — 경로 세그먼트

    - 공통 필드: seq, phase, startLLA, endLLA, targetSpeed
    - 회전 전용 (phase D, H): turnDirection, centerLLA
    """
    seq: int = Field(..., ge=1, description="세그먼트 순번 (1부터 시작)")
    phase: PhaseCode = Field(..., description="미션 프로파일 Phase 코드")
    startLLA: LLA = Field(..., description="시작 좌표")
    endLLA: LLA = Field(..., description="종료 좌표")
    targetSpeed: float = Field(..., gt=0.0, description="목표 속도 (m/s)")

    # 회전 세그먼트 전용 필드 (Phase D, H)
    turnDirection: Optional[Literal["CW", "CCW"]] = Field(
        default=None, description="회전 방향 (CW: 시계, CCW: 반시계)"
    )
    centerLLA: Optional[LLA] = Field(
        default=None, description="회전 중심 좌표"
    )

    @model_validator(mode="after")
    def _validate_turn_fields(self) -> "EnRouteSegment":
        """
        ICD v1 §6 규칙 4-5:
        - Phase D/H → turnDirection, centerLLA 필수
        - 그 외 Phase → turnDirection, centerLLA 금지
        """
        is_turn = self.phase in TURN_PHASES

        if is_turn:
            missing = []
            if self.turnDirection is None:
                missing.append("turnDirection")
            if self.centerLLA is None:
                missing.append("centerLLA")
            if missing:
                raise ValueError(
                    f"Phase '{self.phase.value}' (seq={self.seq}) is a turn segment; "
                    f"missing required fields: {', '.join(missing)}"
                )
        else:
            extra = []
            if self.turnDirection is not None:
                extra.append("turnDirection")
            if self.centerLLA is not None:
                extra.append("centerLLA")
            if extra:
                raise ValueError(
                    f"Phase '{self.phase.value}' (seq={self.seq}) is NOT a turn segment; "
                    f"unexpected fields: {', '.join(extra)}"
                )

        return self


# ──────────────────────────── MissionPlan ─────────────────────

class MissionPlan(BaseModel):
    """
    ICD v1 §4.1 — 최상위 비행계획 레코드

    단건 Mission JSON의 루트 객체이다.
    """
    flightPlanNumber: int = Field(..., description="비행계획 식별 번호")
    aircraftId: str = Field(..., min_length=1, description="기체 식별자")
    departure: Departure = Field(..., description="출발 정보")
    enRoute: list[EnRouteSegment] = Field(
        ..., min_length=1, description="경로 세그먼트 배열 (1개 이상)"
    )
    arrival: Arrival = Field(..., description="도착 정보")
