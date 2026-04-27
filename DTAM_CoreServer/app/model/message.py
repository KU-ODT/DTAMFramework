"""DTAM 메시지 정의 — ICD 기반.

MESSAGE_TABLE:  메시지 ID별 이름, 프로토콜, 방향, 주기, phase 매핑
FORWARD_RULES:  메시지별 포워딩 대상 역할
PHASE_INFO:     시퀀스 다이어그램 기준 6단계 phase 정의
"""
from __future__ import annotations

from typing import Any, Dict, List


# ── Phase 정의 (시퀀스 다이어그램 기준) ────────────────────────
PHASE_INFO: Dict[int, Dict[str, str]] = {
    0: {"name": "DTAM 초기화",          "name_en": "Initialization",     "description": "모듈 세팅 정보(0001), 모듈 상태 보고(0002)"},
    1: {"name": "설정 단계",            "name_en": "Configuration",      "description": "시뮬레이션 모드 설정(1001), 시나리오 설정(1003)"},
    2: {"name": "계획 단계",            "name_en": "Planning",           "description": "비행계획 요청(2001), 계획 비행 제출(3001)"},
    3: {"name": "실행 단계",            "name_en": "Execution",          "description": "DTAM 실행 명령(2002) → 각 모듈 전달"},
    4: {"name": "시뮬레이션 통제 단계",  "name_en": "Simulation Control", "description": "시뮬레이션 통제(1002) → vehicle, visual 전달"},
    5: {"name": "상태정보 업데이트",     "name_en": "Status Update",      "description": "공통 시간(0003) 1Hz, 기체 상태(4001) 주기, 카메라(4101) 주기"},
    6: {"name": "분리 명령",            "name_en": "Separation",         "description": "전략적 분리(3002), 전술적 분리(3003) → vehicle 전달"},
}

# ── 메시지 ID → 상세 정보 ──────────────────────────────────────
MESSAGE_TABLE: Dict[str, Dict[str, Any]] = {
    "0001": {
        "name": "Module Setting Info",
        "name_ko": "모듈 세팅 정보",
        "proto": "udp",
        "direction": "module->server",
        "rate_hz": 0.0,
        "phase": 0,
    },
    "0002": {
        "name": "Module Status",
        "name_ko": "모듈 상태",
        "proto": "udp",
        "direction": "module->server",
        "rate_hz": 1.0,
        "phase": 0,
    },
    "0003": {
        "name": "Common Time Info",
        "name_ko": "공통 시간 정보",
        "proto": "udp",
        "direction": "sim_state->server",
        "rate_hz": 1.0,
        "phase": 5,
    },
    "1001": {
        "name": "Sim Mode Setup",
        "name_ko": "시뮬레이션 모드 설정",
        "proto": "udp",
        "direction": "user->server",
        "rate_hz": 0.0,
        "phase": 1,
    },
    "1002": {
        "name": "Simulation Setup",
        "name_ko": "시뮬레이션 통제",
        "proto": "udp",
        "direction": "user->server",
        "rate_hz": 0.0,
        "phase": 4,
    },
    "1003": {
        "name": "Scenario Setup",
        "name_ko": "시나리오 설정",
        "proto": "udp",
        "direction": "user->server",
        "rate_hz": 0.0,
        "phase": 1,
    },
    "2001": {
        "name": "Flight Plan Request",
        "name_ko": "비행계획 요청",
        "proto": "tcp",
        "direction": "user->server",
        "rate_hz": 0.0,
        "phase": 2,
    },
    "2002": {
        "name": "DTAM Execute",
        "name_ko": "DTAM 실행",
        "proto": "tcp",
        "direction": "user->server",
        "rate_hz": 0.0,
        "phase": 3,
    },
    "3001": {
        "name": "Scheduled Flight",
        "name_ko": "계획 비행",
        "proto": "tcp",
        "direction": "mission->server",
        "rate_hz": 0.0,
        "phase": 2,
    },
    "3002": {
        "name": "Strategic Separation",
        "name_ko": "전략적 분리",
        "proto": "tcp",
        "direction": "mission->server",
        "rate_hz": 0.0,
        "phase": 6,
    },
    "3003": {
        "name": "Tactical Separation",
        "name_ko": "전술적 분리",
        "proto": "tcp",
        "direction": "mission->server",
        "rate_hz": 0.0,
        "phase": 6,
    },
    "4001": {
        "name": "Vehicle Status",
        "name_ko": "비행체 상태 정보",
        "proto": "udp",
        "direction": "vehicle->server",
        "rate_hz": 10.0,
        "phase": 5,
    },
    "4101": {
        "name": "Camera Image Frame",
        "name_ko": "카메라 이미지 프레임",
        "proto": "tcp",
        "direction": "visual->server",
        "rate_hz": 5.0,
        "phase": 5,
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
}

# 시퀀스 다이어그램 기준 포워딩 규칙: mid → list of roles
FORWARD_RULES: Dict[str, List[str]] = {
    "0001": ["monitoring"],                          # Phase 0: 모듈 세팅 종합 → 운용콘솔
    "0002": ["monitoring"],                          # Phase 0: 모듈 상태 → 운용콘솔
    "0003": ["vehicle", "visual"],                   # Phase 5: 공통 시간 정보 → 비행체, 시각화
    "1001": ["sim_state"],                           # Phase 1: 시뮬레이션 모드 → 시뮬레이션 엔진
    "1002": ["vehicle", "visual", "sim_state"],      # Phase 4: 시뮬레이션 통제 → 비행체, 시각화, 엔진
    "1003": ["sim_state"],                           # Phase 1: 시나리오 설정 → 시뮬레이션 엔진
    "2001": ["mission"],                             # Phase 2: 비행계획 요청 → 임무계획
    "2002": ["mission", "monitoring", "vehicle", "visual"],  # Phase 3: 실행 → 전체
    "3001": ["vehicle"],                             # Phase 2: 계획 비행 → 비행체
    "3002": ["vehicle"],                             # Phase 6: 전략적 분리 → 비행체
    "3003": ["vehicle"],                             # Phase 6: 전술적 분리 → 비행체
    "4001": ["monitoring", "visual"],                # Phase 5: 기체 상태 → 운용콘솔, 시각화
    "4101": ["monitoring"],                          # Phase 5: 카메라 → 운용콘솔
}

# 역할 목록
MODULE_ROLES: List[str] = ["mission", "monitoring", "vehicle", "visual", "sim_state"]


def phase_tag(phase: int) -> str:
    """Phase 번호로 Swagger 태그 문자열 생성."""
    info = PHASE_INFO.get(phase, {})
    name = info.get("name", "기타")
    return f"Phase {phase} - {name}"


def get_message_phase_tag(mid: str) -> str:
    """메시지 ID로 Swagger 태그 문자열 가져오기."""
    info = MESSAGE_TABLE.get(mid, {})
    return phase_tag(info.get("phase", -1))
