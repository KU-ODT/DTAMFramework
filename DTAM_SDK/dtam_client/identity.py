"""DTAM 모듈 정체성.

각 모듈의 ``role`` 과 ``source`` 문자열(0002 Module Status 의 ``source`` 필드값)
은 SDK가 들고 있는 단일 표 ``KNOWN_MODULES`` 가 권위입니다.

이전에는 4곳에 흩어져 있었습니다:
  - DTAM_CoreServer/app/model/config.py:default_modules() 의 expected_source
  - DTAMAirMobility 의 source="DTAMAirMobility" 하드코딩
  - DTAM_MissionPlanner 의 MODULE_SOURCE_NAME
  - DTAMOperationsConsole 의 MODULE_SOURCE_NAME
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class Role(str, Enum):
    """DTAM 시스템에서 식별 가능한 역할.

    StrEnum 같은 동작 — JSON 직렬화/HTTP 라우팅에서 그대로 문자열로 쓰임.
    """
    SERVER       = "server"        # SimulationState 자신을 가리킴
    SIM_STATE    = "sim_state"     # forwarding 규칙의 DB sink alias
    MISSION      = "mission"
    MONITORING   = "monitoring"
    VEHICLE      = "vehicle"
    VISUAL       = "visual"

    def __str__(self) -> str:  # str(role) → "vehicle"
        return self.value


@dataclass(frozen=True)
class ModuleIdentity:
    role: Role
    source: str             # "DTAMAirMobility" — 0002.source 와 동일
    display_name: str


KNOWN_MODULES: Dict[Role, ModuleIdentity] = {
    Role.MISSION:    ModuleIdentity(Role.MISSION,    "DTAM_MissionPlanner",   "Mission Planner"),
    Role.MONITORING: ModuleIdentity(Role.MONITORING, "DTAMOperationsConsole", "Operations Console"),
    Role.VEHICLE:    ModuleIdentity(Role.VEHICLE,    "DTAMAirMobility",       "Air Mobility"),
    Role.VISUAL:     ModuleIdentity(Role.VISUAL,     "DTAMVisualization",     "Visualization"),
    Role.SIM_STATE:  ModuleIdentity(Role.SIM_STATE,  "DTAM_SimulationState",  "Simulation State"),
    Role.SERVER:     ModuleIdentity(Role.SERVER,     "DTAM_Server",           "DTAM Server"),
}


# source string → Role 역방향 lookup
_SOURCE_TO_ROLE: Dict[str, Role] = {
    identity.source: identity.role for identity in KNOWN_MODULES.values()
}
# 역할 자체를 source 로 보낸 경우(예: source="vehicle")도 허용
for _role in Role:
    _SOURCE_TO_ROLE.setdefault(_role.value, _role)
    _SOURCE_TO_ROLE.setdefault(_role.value.upper(), _role)
    _SOURCE_TO_ROLE.setdefault(f"DTAM_{_role.value.upper()}", _role)


def role_of(source: str) -> Optional[Role]:
    """0002.source 문자열을 Role 로 환원. 매칭 실패 시 None."""
    if not source:
        return None
    return _SOURCE_TO_ROLE.get(str(source).strip())


def identity_of(role) -> ModuleIdentity:
    """Role 또는 문자열로 ModuleIdentity 조회."""
    if isinstance(role, str):
        try:
            role = Role(role.strip().lower())
        except ValueError:
            raise KeyError(f"Unknown role: {role}")
    return KNOWN_MODULES[role]


__all__ = [
    "Role",
    "ModuleIdentity",
    "KNOWN_MODULES",
    "role_of",
    "identity_of",
]
