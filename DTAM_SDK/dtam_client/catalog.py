"""DTAM 메시지 단일 카탈로그.

이 카탈로그가 SDK·서버·클라이언트 모듈 모두의 권위 있는 메시지 메타입니다.
이전 sdk 코드의 ``MESSAGE_SPECS``, ``_CALLBACK_MAP`` (listener/channel),
``_ROUTES`` (router) 그리고 ``DTAM_CoreServer/app/model/message.py:MESSAGE_TABLE``
다섯 사본을 한 곳으로 통합합니다.

Public API:
    CATALOG     — dict[mid, MessageSpec]
    resolve(key)→ MessageSpec   # mid / alias / "vehicle_status" 등 모두 인식
    callback_name(mid) → "on_vehicle_status"
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class MessageSpec:
    mid: str                       # "4001"
    alias: str                     # "vehicle_status"
    name_en: str                   # "Vehicle Status"
    name_ko: str                   # "비행체 상태 정보"
    direction: str                 # "vehicle->server" — server forwarding 추출용
    rate_hz: float                 # 0.0 = 비주기
    phase: int                     # 시퀀스 다이어그램 phase 0..6
    icd_proto: str                 # "udp" | "tcp" — ICD 명세 표기 (정보용)
    db_folder: str                 # 파일 DB 폴더명
    has_image_payload: bool = False  # 4101 처럼 binary tail 포함 여부

    @property
    def callback_name(self) -> str:
        return f"on_{self.alias}"

    @property
    def push_name(self) -> str:
        return f"push_{self.alias}"


CATALOG: Dict[str, MessageSpec] = {
    "0001": MessageSpec(
        mid="0001", alias="module_setting_info",
        name_en="Module Setting Info", name_ko="모듈 세팅 정보",
        direction="module->server", rate_hz=0.0, phase=0,
        icd_proto="udp", db_folder="ModuleSettingInfo",
    ),
    "0002": MessageSpec(
        mid="0002", alias="module_status",
        name_en="Module Status", name_ko="모듈 상태",
        direction="module->server", rate_hz=1.0, phase=0,
        icd_proto="udp", db_folder="ModuleStatus",
    ),
    "0003": MessageSpec(
        mid="0003", alias="common_time_info",
        name_en="Common Time Info", name_ko="공통 시간 정보",
        direction="sim_state->server", rate_hz=1.0, phase=5,
        icd_proto="udp", db_folder="CommonTimeInfo",
    ),
    "1001": MessageSpec(
        mid="1001", alias="sim_mode_setup",
        name_en="Sim Mode Setup", name_ko="시뮬레이션 모드 설정",
        direction="user->server", rate_hz=0.0, phase=1,
        icd_proto="udp", db_folder="SimModeSetup",
    ),
    "1002": MessageSpec(
        mid="1002", alias="simulation_setup",
        name_en="Simulation Setup", name_ko="시뮬레이션 통제",
        direction="user->server", rate_hz=0.0, phase=4,
        icd_proto="udp", db_folder="SimulationSetup",
    ),
    "1003": MessageSpec(
        mid="1003", alias="scenario_setup",
        name_en="Scenario Setup", name_ko="시나리오 설정",
        direction="user->server", rate_hz=0.0, phase=1,
        icd_proto="udp", db_folder="ScenarioSetup",
    ),
    "2001": MessageSpec(
        mid="2001", alias="flight_plan_request",
        name_en="Flight Plan Request", name_ko="비행계획 요청",
        direction="user->server", rate_hz=0.0, phase=2,
        icd_proto="tcp", db_folder="FlightPlanRequest",
    ),
    "2002": MessageSpec(
        mid="2002", alias="dtam_execute",
        name_en="DTAM Execute", name_ko="DTAM 실행",
        direction="user->server", rate_hz=0.0, phase=3,
        icd_proto="tcp", db_folder="DtamExecute",
    ),
    "3001": MessageSpec(
        mid="3001", alias="scheduled_flight",
        name_en="Scheduled Flight", name_ko="계획 비행",
        direction="mission->server", rate_hz=0.0, phase=2,
        icd_proto="tcp", db_folder="ScheduledFlight",
    ),
    "3002": MessageSpec(
        mid="3002", alias="strategic_separation",
        name_en="Strategic Separation", name_ko="전략적 분리",
        direction="mission->server", rate_hz=0.0, phase=6,
        icd_proto="tcp", db_folder="ScheduledFlightModification",
    ),
    "3003": MessageSpec(
        mid="3003", alias="tactical_separation",
        name_en="Tactical Separation", name_ko="전술적 분리",
        direction="mission->server", rate_hz=0.0, phase=6,
        icd_proto="tcp", db_folder="TacticalActionCommand",
    ),
    "4001": MessageSpec(
        mid="4001", alias="vehicle_status",
        name_en="Vehicle Status", name_ko="비행체 상태 정보",
        direction="vehicle->server", rate_hz=10.0, phase=5,
        icd_proto="udp", db_folder="VehicleStatus",
    ),
    "4101": MessageSpec(
        mid="4101", alias="camera_image",
        name_en="Camera Image Frame", name_ko="카메라 이미지 프레임",
        direction="visual->server", rate_hz=5.0, phase=5,
        icd_proto="tcp", db_folder="CameraImage", has_image_payload=True,
    ),
}


# Phase 정의 (시퀀스 다이어그램 기준)
PHASE_INFO: Dict[int, Dict[str, str]] = {
    0: {"name": "DTAM 초기화",          "name_en": "Initialization",     "description": "모듈 세팅 정보(0001), 모듈 상태 보고(0002)"},
    1: {"name": "설정 단계",            "name_en": "Configuration",      "description": "시뮬레이션 모드 설정(1001), 시나리오 설정(1003)"},
    2: {"name": "계획 단계",            "name_en": "Planning",           "description": "비행계획 요청(2001), 계획 비행 제출(3001)"},
    3: {"name": "실행 단계",            "name_en": "Execution",          "description": "DTAM 실행 명령(2002) → 각 모듈 전달"},
    4: {"name": "시뮬레이션 통제 단계",  "name_en": "Simulation Control", "description": "시뮬레이션 통제(1002) → vehicle, visual 전달"},
    5: {"name": "상태정보 업데이트",     "name_en": "Status Update",      "description": "공통 시간(0003) 1Hz, 기체 상태(4001), 카메라(4101)"},
    6: {"name": "분리 명령",            "name_en": "Separation",         "description": "전략적 분리(3002), 전술적 분리(3003) → vehicle"},
}


# alias / sender / callback / 압축형 모두 mid로 환원하기 위한 lookup
_ALIASES: Dict[str, str] = {}
for _mid, _spec in CATALOG.items():
    _ALIASES[_mid] = _mid
    _ALIASES[_spec.alias] = _mid
    _ALIASES[_spec.alias.replace("_", "")] = _mid
    _ALIASES[f"push_{_spec.alias}"] = _mid
    _ALIASES[f"on_{_spec.alias}"] = _mid


def resolve(key: Any) -> MessageSpec:
    """mid / alias / sender 함수명 / 콜백명 모두 받아 MessageSpec 으로 환원."""
    if isinstance(key, MessageSpec):
        return key
    raw = str(key).strip().lower().replace("-", "_").replace(" ", "_")
    mid = _ALIASES.get(raw) or _ALIASES.get(raw.replace("_", ""))
    if mid is None:
        known = ", ".join(sorted(CATALOG))
        raise ValueError(f"Unknown DTAM message {key!r}. Known IDs: {known}")
    return CATALOG[mid]


def try_resolve(key: Any) -> Optional[MessageSpec]:
    try:
        return resolve(key)
    except ValueError:
        return None


def callback_name(key: Any) -> str:
    return resolve(key).callback_name


def push_name(key: Any) -> str:
    return resolve(key).push_name


def all_callback_names() -> set[str]:
    return {spec.callback_name for spec in CATALOG.values()}


def phase_tag(phase: int) -> str:
    info = PHASE_INFO.get(phase, {})
    name = info.get("name", "기타")
    return f"Phase {phase} - {name}"


__all__ = [
    "MessageSpec",
    "CATALOG",
    "PHASE_INFO",
    "resolve",
    "try_resolve",
    "callback_name",
    "push_name",
    "all_callback_names",
    "phase_tag",
]
