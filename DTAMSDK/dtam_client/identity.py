"""DTAM module role and source identity definitions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class Role(str, Enum):
    """Roles used by DTAM modules."""

    SERVER = "server"
    SIM_STATE = "sim_state"
    MISSION = "mission"
    MONITORING = "monitoring"
    VEHICLE = "vehicle"
    VISUAL = "visual"
    SITUATION_AWARENESS = "situation_awareness"
    PSU = "psu"                              # Provider of Services for UAM (ExtenstionModule/PSUModule)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ModuleIdentity:
    role: Role
    source: str
    display_name: str


KNOWN_MODULES: Dict[Role, ModuleIdentity] = {
    Role.MISSION: ModuleIdentity(Role.MISSION, "MissionModule", "Mission Planner"),
    Role.MONITORING: ModuleIdentity(Role.MONITORING, "OperationModule", "Operations Console"),
    Role.VEHICLE: ModuleIdentity(Role.VEHICLE, "VehicleModule", "Air Mobility"),
    Role.VISUAL: ModuleIdentity(Role.VISUAL, "VisualizationModule", "Visualization"),
    Role.SITUATION_AWARENESS: ModuleIdentity(Role.SITUATION_AWARENESS, "SituationAwareness", "Situation Awareness"),
    Role.SIM_STATE: ModuleIdentity(Role.SIM_STATE, "SimulationState", "Simulation State"),
    Role.SERVER: ModuleIdentity(Role.SERVER, "IntegrationHub", "IntegrationHub"),
    Role.PSU: ModuleIdentity(Role.PSU, "PSUModule", "Provider of Services for UAM"),
}


_SOURCE_TO_ROLE: Dict[str, Role] = {
    identity.source: identity.role for identity in KNOWN_MODULES.values()
}
for _role in Role:
    _SOURCE_TO_ROLE.setdefault(_role.value, _role)
    _SOURCE_TO_ROLE.setdefault(_role.value.upper(), _role)
    _SOURCE_TO_ROLE.setdefault(f"DTAM_{_role.value.upper()}", _role)


def role_from_source(source: str) -> Optional[Role]:
    """Resolve a 0002.source string to a Role, or None on failure."""
    if not source:
        return None
    return _SOURCE_TO_ROLE.get(str(source).strip())


def role_of(source: str) -> Optional[Role]:
    """Backward-compatible alias for role_from_source()."""
    return role_from_source(source)


def identity_of(role) -> ModuleIdentity:
    """Return ModuleIdentity for a Role or role string."""
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
    "role_from_source",
    "role_of",
    "identity_of",
]
