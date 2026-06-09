"""Registry for pluggable operator dynamics implementations."""

from __future__ import annotations

from typing import Dict, Type

from .base import ManualVehicleConfig, OperatorDynamicsModel
from .manual_kinematic import ManualKinematicDynamics


_OPERATOR_DYNAMICS: Dict[str, Type[OperatorDynamicsModel]] = {
    "manual_kinematic": ManualKinematicDynamics,
}


def available_operator_dynamics() -> list[str]:
    return sorted(_OPERATOR_DYNAMICS.keys())


def create_operator_dynamics(
    name: str,
    config: ManualVehicleConfig | None = None,
) -> OperatorDynamicsModel:
    key = str(name or "").strip().lower()
    try:
        cls = _OPERATOR_DYNAMICS[key]
    except KeyError as exc:
        raise ValueError(f"unknown operator dynamics model: {name}") from exc
    return cls(config or ManualVehicleConfig())

