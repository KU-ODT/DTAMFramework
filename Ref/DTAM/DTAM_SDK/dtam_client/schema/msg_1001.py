"""Sim Mode Setup (MSG 1001) schema.

Modes:
  - "single"  : requires the singleFlight block.
  - "traffic" : traffic simulation mode, no extra setup payload.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .common import (
    Field,
    ISO_DATETIME_PATTERN,
    validate_field,
)


# ===== 열거형 =====
OPERATION_MODES = ["single", "traffic"]
DYNAMICS_CHOICES = ["simple", "multirotor", "highFidelity"]
CONTROLLER_TYPES = ["Joystick", "Keyboard", "Autopilot"]


# ===== 필드 정의 =====

TOP_FIELDS: Dict[str, Field] = {
    "timestamp":     Field("iso_datetime", "UTC", "송신 시각", "Send time",      pattern=ISO_DATETIME_PATTERN),
    "operationMode": Field("str", "",             "운용 모드", "Operation mode", choices=OPERATION_MODES),
}

VEHICLE_SIM_TYPE_FIELDS: Dict[str, Field] = {
    "dynamics": Field("str", "", "동역학 모델", "Dynamics model", choices=DYNAMICS_CHOICES),
    "mainVehicleController": Field("str", "", "비행체 제어방식", "Aircraft controller", choices=CONTROLLER_TYPES),
}

# ===== 내부 검증 =====

def _validate_single_flight(obj: Dict[str, Any], errors: List[str]) -> None:
    sf = obj.get("singleFlight")
    if sf is None:
        errors.append("singleFlight: 누락")
        return
    if not isinstance(sf, dict):
        errors.append("singleFlight: dict 필요")
        return
    vst = sf.get("vehicleSimType")
    if vst is None:
        errors.append("singleFlight.vehicleSimType: 누락")
        return
    if not isinstance(vst, dict):
        errors.append("singleFlight.vehicleSimType: dict 필요")
        return
    for fname, fspec in VEHICLE_SIM_TYPE_FIELDS.items():
        if fname not in vst:
            errors.append(f"singleFlight.vehicleSimType.{fname}: 누락")
            continue
        validate_field(vst[fname], fspec, f"singleFlight.vehicleSimType.{fname}", errors)


def validate_message(obj: Any) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["root: dict 필요"], {}

    for name, fspec in TOP_FIELDS.items():
        if name not in obj:
            errors.append(f"{name}: 누락")
            continue
        validate_field(obj[name], fspec, name, errors)

    mode = obj.get("operationMode")
    if mode == "single":
        _validate_single_flight(obj, errors)
        if "traffic" in obj:
            errors.append("traffic: single 모드에서 허용되지 않음")
    elif mode == "traffic":
        if "singleFlight" in obj:
            errors.append("singleFlight: traffic 모드에서 허용되지 않음")
        if "traffic" in obj:
            errors.append("traffic: traffic 모드에서 허용되지 않음")

    return (len(errors) == 0), errors, obj
