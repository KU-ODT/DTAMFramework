"""
VFDS Dynamics Dispatch System — Mission Plan to Leg-Based IR

상위 Mission JSON을 leg semantics 기반 중간표현(IR)으로 변환한다.

각 세그먼트는 waypoint 배열이 아니라 **leg 파라미터**(시작점, 종료점,
센터, 반경, sweep, 종료조건)로 표현되어, 오토파일럿의 orbit/goto 명령으로
직접 실행된다.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..validator.models import EnRouteSegment, LLA, MissionPlan, PhaseCode, TURN_PHASES

from .arc_interpolator import compute_arc_params
from ..dispatcher.sim_time import format_hhmmss, parse_hhmmss

logger = logging.getLogger(__name__)


# ──────────────────────── Leg Type ────────────────────────────

class LegType(str, Enum):
    """비행 구간(leg) 유형 — ARINC 424 path terminator 개념에 기반."""
    TAXI = "TAXI"                       # 지상 이동 (A, K)
    VTOL_CLIMB = "VTOL_CLIMB"           # 수직 이륙/상승 (B)
    TF_LINE = "TF_LINE"                 # Track-to-Fix 직선 (E, F, I)
    RF_ARC = "RF_ARC"                   # Radius-to-Fix 원호 (D, H)
    VTOL_DESCENT = "VTOL_DESCENT"       # 수직 하강/착륙 (J)
    TRANSITION_FW = "TRANSITION_FW"     # MC→FW 전환 (C)
    TRANSITION_MC = "TRANSITION_MC"     # FW→MC 전환 (G)


# ──────────────────────── Leg Block ────────────────────────────

@dataclass
class LegBlock:
    """
    하나의 비행 구간(leg)을 표현하는 IR 단위.

    waypoint 나열이 아니라 leg의 의미론적 파라미터를 직접 보유한다.
    오토파일럿 실행 시 leg_type에 따라 다른 명령을 사용한다.
    """
    seq: int
    phase: str
    leg_type: LegType
    description: str

    # ── 공통 파라미터 ──
    start_lat: float = 0.0
    start_lon: float = 0.0
    start_alt: float = 0.0
    end_lat: float = 0.0
    end_lon: float = 0.0
    end_alt: float = 0.0
    target_speed: float = 0.0
    heading_deg: float = 0.0           # 진행 방위각 (North=0, CW 증가)

    # ── RF_ARC 전용 ──
    center_lat: float = 0.0
    center_lon: float = 0.0
    center_alt: float = 0.0
    radius_m: float = 0.0
    turn_direction: str = ""            # "CW" or "CCW"
    sweep_rad: float = 0.0             # 호 각도 (라디안, 양수)
    arc_valid: bool = True
    arc_warning: str = ""

    # ── 종료 조건 ──
    termination: str = "FIX"            # FIX, ALTITUDE, SWEPT_ANGLE


# ──────────────────────── Mission IR ────────────────────────────

@dataclass
class MissionIR:
    """Mission 전체의 중간표현."""
    flight_plan_number: int
    aircraft_id: str
    departure_vertiport: str
    arrival_vertiport: str
    std: str
    sta: str
    mission_start_time: str
    mission_arm_time: str
    mission_start_field: str
    arming_lead_sec: float
    connection_string: str
    vfds_host: str = "127.0.0.1"
    home_lat: float = 0.0
    home_lon: float = 0.0
    home_alt: float = 0.0
    legs: list[LegBlock] = field(default_factory=list)

    # 레거시 호환: 기존 테스트에서 ir.maneuvers를 참조하는 경우 대비
    @property
    def maneuvers(self) -> list[LegBlock]:
        return self.legs


# ──────────────────────── Phase → LegType 매핑 ────────────────

_PHASE_MAP: dict[PhaseCode, tuple[LegType, str]] = {
    PhaseCode.A: (LegType.TAXI, "Gate-out taxi"),
    PhaseCode.B: (LegType.VTOL_CLIMB, "Vertical takeoff"),
    PhaseCode.C: (LegType.TRANSITION_FW, "Departure transition (MC→FW)"),
    PhaseCode.D: (LegType.RF_ARC, "Departure turn"),
    PhaseCode.E: (LegType.TF_LINE, "Climb out"),
    PhaseCode.F: (LegType.TF_LINE, "Cruise"),
    PhaseCode.G: (LegType.TRANSITION_MC, "Arrival transition (FW→MC)"),
    PhaseCode.H: (LegType.RF_ARC, "Arrival turn"),
    PhaseCode.I: (LegType.TF_LINE, "Final approach"),
    PhaseCode.J: (LegType.VTOL_DESCENT, "Landing"),
    PhaseCode.K: (LegType.TAXI, "Gate-in taxi"),
}


# ──────────────────────── 방위각 계산 ────────────────────────────

def _bearing_deg(start: LLA, end: LLA) -> float:
    """start→end 방위각 (degree, North=0, CW 증가)."""
    lat1 = math.radians(start.lat)
    lat2 = math.radians(end.lat)
    d_lon = math.radians(end.lon - start.lon)

    y = math.sin(d_lon) * math.cos(lat2)
    x = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1) * math.cos(lat2) * math.cos(d_lon)
    )
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360.0) % 360.0


def _get_nested_attr(obj: object, path: str) -> str:
    current = obj
    for part in path.split("."):
        current = getattr(current, part)
    if not isinstance(current, str):
        raise TypeError(f"Mission start field '{path}' must be a HH:MM:SS string")
    return current


# ──────────────────────── 변환 메인 ────────────────────────────

def mission_to_ir(
    mission: MissionPlan,
    connection_string: str = "",
    arc_points: int = 6,  # 레거시 호환 (arc 보간 점수, 현재는 미사용)
    vfds_host: str = "127.0.0.1",
    mission_start_field: str = "departure.std",
    arming_lead_sec: float = 300.0,
) -> MissionIR:
    """
    MissionPlan을 leg-based MissionIR로 변환한다.

    Turn 세그먼트(Phase D, H)는 arc validation을 거쳐
    RF_ARC LegBlock으로 직접 변환된다. (더 이상 waypoint로 쪼개지 않음)
    """
    # Taxi (Phase A, K)를 제외한 첫 번째 비행 구간의 시작점을 Home(SITL 스폰 위치)으로 설정하여,
    # 지상 활주를 생략하더라도 기체가 정확히 비행 경로(FATO)에서 출발하도록 한다.
    flight_legs = [seg for seg in mission.enRoute if seg.phase.value not in ("A", "K")]
    home = flight_legs[0].startLLA if flight_legs else mission.enRoute[0].startLLA
    mission_start_time = _get_nested_attr(mission, mission_start_field)
    mission_start_seconds = parse_hhmmss(mission_start_time)
    mission_arm_seconds = max(0, mission_start_seconds - int(max(0.0, arming_lead_sec)))

    ir = MissionIR(
        flight_plan_number=mission.flightPlanNumber,
        aircraft_id=mission.aircraftId,
        departure_vertiport=mission.departure.vertiport,
        arrival_vertiport=mission.arrival.vertiport,
        std=mission.departure.std,
        sta=mission.arrival.sta,
        mission_start_time=mission_start_time,
        mission_arm_time=format_hhmmss(mission_arm_seconds),
        mission_start_field=mission_start_field,
        arming_lead_sec=max(0.0, arming_lead_sec),
        connection_string=connection_string,
        vfds_host=vfds_host,
        home_lat=home.lat,
        home_lon=home.lon,
        home_alt=home.alt,
    )

    for seg in mission.enRoute:
        leg_type, description = _PHASE_MAP.get(
            seg.phase, (LegType.TF_LINE, f"Phase {seg.phase.value}")
        )

        # 공통 파라미터
        heading = _bearing_deg(seg.startLLA, seg.endLLA)

        block = LegBlock(
            seq=seg.seq,
            phase=seg.phase.value,
            leg_type=leg_type,
            description=description,
            start_lat=seg.startLLA.lat,
            start_lon=seg.startLLA.lon,
            start_alt=seg.startLLA.alt,
            end_lat=seg.endLLA.lat,
            end_lon=seg.endLLA.lon,
            end_alt=seg.endLLA.alt,
            target_speed=seg.targetSpeed,
            heading_deg=heading,
        )

        # ── RF_ARC: arc validation + 파라미터 계산 ──
        if seg.phase in TURN_PHASES and seg.centerLLA is not None:
            arc = compute_arc_params(
                center=seg.centerLLA,
                start=seg.startLLA,
                end=seg.endLLA,
                direction=seg.turnDirection,
            )

            corrected_center = arc["center"]
            block.center_lat = corrected_center.lat
            block.center_lon = corrected_center.lon
            block.center_alt = corrected_center.alt
            block.radius_m = arc["radius_m"]
            block.turn_direction = seg.turnDirection
            block.sweep_rad = arc["sweep_rad"]
            block.arc_valid = arc["valid"]
            block.arc_warning = arc.get("warning", "") or ""
            block.termination = "SWEPT_ANGLE"

            if block.arc_warning:
                logger.warning(
                    "Seq %d (Phase %s): %s",
                    seg.seq, seg.phase.value, block.arc_warning,
                )

        # ── VTOL_CLIMB/VTOL_DESCENT: 고도 기반 종료 ──
        elif leg_type in (LegType.VTOL_CLIMB, LegType.VTOL_DESCENT):
            block.termination = "ALTITUDE"

        # ── TF_LINE, TRANSITION: fix 기반 종료 ──
        else:
            block.termination = "FIX"

        ir.legs.append(block)

    return ir
