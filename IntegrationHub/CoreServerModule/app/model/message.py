"""DTAM 메시지 정의 — ICD 기반.

MESSAGE_TABLE:  메시지 ID별 이름, 전송 채널, 방향, 주기, phase 매핑
FORWARD_RULES:  메시지별 포워딩 대상 역할
PHASE_INFO:     시퀀스 다이어그램 기준 6단계 phase 정의
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

_FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
_DTAMSDK_ROOT = _FRAMEWORK_ROOT / "DTAMSDK"
if _DTAMSDK_ROOT.is_dir() and str(_DTAMSDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_DTAMSDK_ROOT))

from dtam_client.policy import FORWARD_RULES as SDK_FORWARD_RULES  # type: ignore


# ── Phase 정의 (시퀀스 다이어그램 기준) ────────────────────────
PHASE_INFO: Dict[int, Dict[str, str]] = {
    0: {"name": "DTAM 초기화",          "name_en": "Initialization",     "description": "모듈 세팅 정보(0001), 모듈 상태 보고(0002)"},
    1: {"name": "설정 단계",            "name_en": "Configuration",      "description": "시뮬레이션 모드 설정(1001), 시나리오 설정(1003)"},
    2: {"name": "계획 단계",            "name_en": "Planning",           "description": "비행계획 요청(2001), 계획 비행 제출(3001)"},
    3: {"name": "실행 단계",            "name_en": "Execution",          "description": "DTAM 실행 명령(2002) → 각 모듈 전달"},
    4: {"name": "시뮬레이션 통제 단계",  "name_en": "Simulation Control", "description": "시뮬레이션 통제(1002) → vehicle, visual 전달"},
    5: {"name": "상태정보 업데이트",     "name_en": "Status Update",      "description": "공통 시간(0003) 1Hz, 기체 상태(4001), 저주기 이미지(4101), 스트림 디스크립터(4102), 충돌 이벤트(4103)"},
    6: {"name": "분리 명령",            "name_en": "Separation",         "description": "전략적 분리(3002), 전술적 분리(3003) → vehicle 전달"},
    7: {"name": "운용자 제어",           "name_en": "Operator Control",    "description": "수동 조종 입력(5001), 카메라 제어 명령(5002), 비정상 상황 명령(5003) → 해당 모듈 전달"},
}

# ── 메시지 ID → 상세 정보 ──────────────────────────────────────
MESSAGE_TABLE: Dict[str, Dict[str, Any]] = {
    "0001": {
        "name": "Module Setting Info",
        "name_ko": "모듈 세팅 정보",
        "proto": "ws",
        "direction": "module->server",
        "rate_hz": 0.0,
        "phase": 0,
    },
    "0002": {
        "name": "Module Status",
        "name_ko": "모듈 상태",
        "proto": "ws",
        "direction": "module->server",
        "rate_hz": 1.0,
        "phase": 0,
    },
    "0003": {
        "name": "Common Time Info",
        "name_ko": "공통 시간 정보",
        "proto": "ws",
        "direction": "sim_state->server",
        "rate_hz": 1.0,
        "phase": 5,
    },
    "1001": {
        "name": "Sim Mode Setup",
        "name_ko": "시뮬레이션 모드 설정",
        "proto": "ws",
        "direction": "user->server",
        "rate_hz": 0.0,
        "phase": 1,
    },
    "1002": {
        "name": "Simulation Setup",
        "name_ko": "시뮬레이션 통제",
        "proto": "ws",
        "direction": "user->server",
        "rate_hz": 0.0,
        "phase": 4,
    },
    "1003": {
        "name": "Scenario Setup",
        "name_ko": "시나리오 설정",
        "proto": "ws",
        "direction": "user->server",
        "rate_hz": 0.0,
        "phase": 1,
    },
    "2001": {
        "name": "Flight Plan Request",
        "name_ko": "비행계획 요청",
        "proto": "ws",
        "direction": "user->server",
        "rate_hz": 0.0,
        "phase": 2,
    },
    "2002": {
        "name": "DTAM Execute",
        "name_ko": "DTAM 실행",
        "proto": "ws",
        "direction": "user->server",
        "rate_hz": 0.0,
        "phase": 3,
    },
    "3001": {
        "name": "Scheduled Flight",
        "name_ko": "계획 비행",
        "proto": "ws",
        "direction": "mission->server",
        "rate_hz": 0.0,
        "phase": 2,
    },
    "3002": {
        "name": "Strategic Separation",
        "name_ko": "전략적 분리",
        "proto": "ws",
        "direction": "mission->server",
        "rate_hz": 0.0,
        "phase": 6,
    },
    "3003": {
        "name": "Tactical Separation",
        "name_ko": "전술적 분리",
        "proto": "ws",
        "direction": "mission->server",
        "rate_hz": 0.0,
        "phase": 6,
    },
    "4001": {
        "name": "Vehicle Status",
        "name_ko": "비행체 상태 정보",
        "proto": "ws",
        "direction": "vehicle->server",
        "rate_hz": 10.0,
        "phase": 5,
    },
    "4101": {
        "name": "Camera Image Frame",
        "name_ko": "카메라 이미지 프레임",
        "proto": "ws",
        "direction": "visual->server",
        "rate_hz": 5.0,
        "phase": 5,
    },
    "4102": {
        "name": "Camera Stream Descriptor",
        "name_ko": "카메라 스트림 디스크립터",
        "proto": "ws",
        "direction": "visual->server",
        "rate_hz": 0.0,
        "phase": 5,
    },
    "4103": {
        "name": "Vehicle Collision Event",
        "name_ko": "비행체 충돌 이벤트",
        "proto": "ws",
        "direction": "visual->server",
        "rate_hz": 0.0,
        "phase": 5,
    },
    "5001": {
        "name": "Operator Control Input",
        "name_ko": "수동 조종 입력",
        "proto": "ws",
        "direction": "operator->server",
        "rate_hz": 20.0,
        "phase": 7,
    },
    "5002": {
        "name": "Camera Control Command",
        "name_ko": "카메라 제어 명령",
        "proto": "ws",
        "direction": "operator->server",
        "rate_hz": 0.0,
        "phase": 7,
    },
    "5003": {
        "name": "Abnormal Situation Command",
        "name_ko": "비정상 상황/장애물 생성 명령",
        "proto": "ws",
        "direction": "operator->server",
        "rate_hz": 0.0,
        "phase": 7,
    },
}

# 메시지 ID → DB 저장 폴더명
DB_FOLDER_FOR_MID: Dict[str, str] = {
    "0002": "ModuleStatus",
    "0003": "CommonTimeInfo",
    "1001": "SimModeSetup",
    "1002": "SimulationSetup",
    "1003": "ScenarioSetup",
    "2001": "FlightPlanRequest",
    "2002": "DtamExecute",
    "3001": "ScheduledFlight",
    "3002": "ScheduledFlightModification",
    "3003": "TacticalActionCommand",
    "4001": "VehicleStatus",
    "4101": "CameraImage",
    "4102": "CameraStreamDescriptor",
    "4103": "VehicleCollisionEvent",
    "5001": "OperatorControlInput",
    "5002": "CameraControlCommand",
    "5003": "AbnormalSituationCommand",
}

# SDK policy is the single forwarding authority. CoreServer keeps MESSAGE_TABLE
# metadata for docs, but its forwarding view is derived from dtam_client.policy.
FORWARD_RULES: Dict[str, List[str]] = {
    mid: [str(role.value if hasattr(role, "value") else role) for role in roles]
    for mid, roles in SDK_FORWARD_RULES.items()
}

# 역할 목록
MODULE_ROLES: List[str] = [
    "mission",
    "monitoring",
    "vehicle",
    "visual",
    "situation_awareness",
    "sim_state",
]


def phase_tag(phase: int) -> str:
    """Phase 번호로 Swagger 태그 문자열 생성."""
    info = PHASE_INFO.get(phase, {})
    name = info.get("name", "기타")
    return f"Phase {phase} - {name}"


def get_message_phase_tag(mid: str) -> str:
    """메시지 ID로 Swagger 태그 문자열 가져오기."""
    info = MESSAGE_TABLE.get(mid, {})
    return phase_tag(info.get("phase", -1))

