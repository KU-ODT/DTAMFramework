"""Unified DTAM message catalog shared by the SDK, server, and modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class MessageSpec:
    mid: str
    alias: str
    name_en: str
    name_ko: str
    direction: str
    rate_hz: float
    phase: int
    icd_proto: str
    db_folder: str
    has_image_payload: bool = False

    @property
    def callback_name(self) -> str:
        return f"on_{self.alias}"

    @property
    def push_name(self) -> str:
        return f"push_{self.alias}"


CATALOG: Dict[str, MessageSpec] = {
    "0001": MessageSpec(
        mid="0001", alias="module_setting_info",
        name_en="Module Setting Info", name_ko="?? ?? ??",
        direction="module->server", rate_hz=0.0, phase=0,
        icd_proto="ws", db_folder="ModuleSettingInfo",
    ),
    "0002": MessageSpec(
        mid="0002", alias="module_status",
        name_en="Module Status", name_ko="?? ??",
        direction="module->server", rate_hz=1.0, phase=0,
        icd_proto="ws", db_folder="ModuleStatus",
    ),
    "0003": MessageSpec(
        mid="0003", alias="common_time_info",
        name_en="Common Time Info", name_ko="?? ?? ??",
        direction="sim_state->server", rate_hz=1.0, phase=5,
        icd_proto="ws", db_folder="CommonTimeInfo",
    ),
    "1001": MessageSpec(
        mid="1001", alias="sim_mode_setup",
        name_en="Sim Mode Setup", name_ko="????? ?? ??",
        direction="user->server", rate_hz=0.0, phase=1,
        icd_proto="ws", db_folder="SimModeSetup",
    ),
    "1002": MessageSpec(
        mid="1002", alias="simulation_setup",
        name_en="Simulation Setup", name_ko="????? ??",
        direction="user->server", rate_hz=0.0, phase=4,
        icd_proto="ws", db_folder="SimulationSetup",
    ),
    "1003": MessageSpec(
        mid="1003", alias="scenario_setup",
        name_en="Scenario Setup", name_ko="???? ??",
        direction="user->server", rate_hz=0.0, phase=1,
        icd_proto="ws", db_folder="ScenarioSetup",
    ),
    "2001": MessageSpec(
        mid="2001", alias="flight_plan_request",
        name_en="Flight Plan Request", name_ko="???? ??",
        direction="user|psu|uao->server", rate_hz=0.0, phase=2,
        icd_proto="ws", db_folder="FlightPlanRequest",
    ),
    "2002": MessageSpec(
        mid="2002", alias="dtam_execute",
        name_en="DTAM Execute", name_ko="DTAM ??",
        direction="user->server", rate_hz=0.0, phase=3,
        icd_proto="ws", db_folder="DtamExecute",
    ),
    "3001": MessageSpec(
        mid="3001", alias="scheduled_flight",
        name_en="Scheduled Flight", name_ko="?? ??",
        direction="mission->server", rate_hz=0.0, phase=2,
        icd_proto="ws", db_folder="ScheduledFlight",
    ),
    "3002": MessageSpec(
        mid="3002", alias="strategic_separation",
        name_en="Strategic Separation", name_ko="??? ??",
        direction="mission->server", rate_hz=0.0, phase=6,
        icd_proto="ws", db_folder="ScheduledFlightModification",
    ),
    "3003": MessageSpec(
        mid="3003", alias="tactical_separation",
        name_en="Tactical Separation", name_ko="??? ??",
        direction="mission->server", rate_hz=0.0, phase=6,
        icd_proto="ws", db_folder="TacticalActionCommand",
    ),
    "4001": MessageSpec(
        mid="4001", alias="vehicle_status",
        name_en="Vehicle Status", name_ko="??? ??",
        direction="vehicle->server", rate_hz=10.0, phase=5,
        icd_proto="ws", db_folder="VehicleStatus",
    ),
    "4002": MessageSpec(
        mid="4002", alias="vehicle_warning_event",
        name_en="Vehicle Warning Event", name_ko="비행체 경고 이벤트",
        direction="vehicle->server", rate_hz=0.0, phase=5,
        icd_proto="ws", db_folder="VehicleWarningEvent",
    ),
    "4101": MessageSpec(
        mid="4101", alias="camera_image",
        name_en="Camera Image Frame", name_ko="??? ??? ???",
        direction="visual->server", rate_hz=5.0, phase=5,
        icd_proto="ws", db_folder="CameraImage", has_image_payload=True,
    ),
    "4102": MessageSpec(
        mid="4102", alias="camera_stream_descriptor",
        name_en="Camera Stream Descriptor", name_ko="카메라 스트림 디스크립터",
        direction="visual->server", rate_hz=0.0, phase=5,
        icd_proto="ws", db_folder="CameraStreamDescriptor",
    ),
    "4103": MessageSpec(
        mid="4103", alias="vehicle_collision_event",
        name_en="Vehicle Collision Event", name_ko="비행체 충돌 이벤트",
        direction="visual->server", rate_hz=0.0, phase=5,
        icd_proto="ws", db_folder="VehicleCollisionEvent",
    ),
    "5001": MessageSpec(
        mid="5001", alias="operator_control_input",
        name_en="Operator Control Input", name_ko="??? ?? ??",
        direction="operator->server", rate_hz=20.0, phase=7,
        icd_proto="ws", db_folder="OperatorControlInput",
    ),
    "5002": MessageSpec(
        mid="5002", alias="camera_control_command",
        name_en="Camera Control Command", name_ko="??? ?? ??",
        direction="operator->server", rate_hz=0.0, phase=7,
        icd_proto="ws", db_folder="CameraControlCommand",
    ),
    "5003": MessageSpec(
        mid="5003", alias="abnormal_situation_command",
        name_en="Abnormal Situation Command", name_ko="비정상 상황/장애물 생성 명령",
        direction="operator->server", rate_hz=0.0, phase=7,
        icd_proto="ws", db_folder="AbnormalSituationCommand",
    ),
}


# Registration handling
PHASE_INFO: Dict[int, Dict[str, str]] = {
    0: {"name": "???", "name_en": "Initialization", "description": "Module setting/status messages"},
    1: {"name": "??", "name_en": "Configuration", "description": "Simulation mode and scenario setup"},
    2: {"name": "??", "name_en": "Planning", "description": "Flight plan request and scheduled flight output"},
    3: {"name": "??", "name_en": "Execution", "description": "Execute command delivery"},
    4: {"name": "????? ??", "name_en": "Simulation Control", "description": "Simulation setup to vehicle and visual modules"},
    5: {"name": "?? ??", "name_en": "Status Update", "description": "Common time, vehicle status, camera image/stream, and collision event updates"},
    6: {"name": "??", "name_en": "Separation", "description": "Strategic and tactical separation commands"},
    7: {"name": "??? ??", "name_en": "Operator Control", "description": "Operator, camera, and abnormal situation commands"},
}


# Registration handling
_ALIASES: Dict[str, str] = {}
for _mid, _spec in CATALOG.items():
    _ALIASES[_mid] = _mid
    _ALIASES[_spec.alias] = _mid
    _ALIASES[_spec.alias.replace("_", "")] = _mid
    _ALIASES[f"push_{_spec.alias}"] = _mid
    _ALIASES[f"on_{_spec.alias}"] = _mid


def resolve(key: Any) -> MessageSpec:
    """Internal helper."""
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
    name = info.get("name", "Other")
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
