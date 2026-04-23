"""Sim Mode Setup (MSG 1001) 스키마 — 운용 모드별 시뮬레이션 설정.

모드:
  - "single"     : singleFlight 블록 필수
  - "traffic"    : traffic 블록 필수
  - "integrated" : singleFlight + traffic 둘 다 필수
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .common import (
    Field,
    ISO_DATETIME_PATTERN,
    validate_field,
)


# ===== 열거형 =====
OPERATION_MODES = ["single", "traffic", "integrated"]
DYNAMICS_CHOICES = ["simple", "multirotor", "highFidelity"]
CONTROLLER_TYPES = ["Joystick", "Keyboard", "Autopilot"]
TRAFFIC_SCENARIOS = ["low", "middle", "high", "customed"]


# ===== 필드 정의 =====

TOP_FIELDS: Dict[str, Field] = {
    "timestamp":     Field("iso_datetime", "UTC", "송신 시각", "Send time",      pattern=ISO_DATETIME_PATTERN),
    "operationMode": Field("str", "",             "운용 모드", "Operation mode", choices=OPERATION_MODES),
}

VEHICLE_SIM_TYPE_FIELDS: Dict[str, Field] = {
    "dynamics": Field("str", "", "동역학 모델", "Dynamics model", choices=DYNAMICS_CHOICES),
    "mainVehicleController": Field("str", "", "비행체 제어방식", "Aircraft controller", choices=CONTROLLER_TYPES),
}

TRAFFIC_FIELDS: Dict[str, Field] = {
    "trafficScenario": Field("str", "", "교통 시나리오", "Traffic scenario", choices=TRAFFIC_SCENARIOS),
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


def _validate_traffic(obj: Dict[str, Any], errors: List[str]) -> None:
    tr = obj.get("traffic")
    if tr is None:
        errors.append("traffic: 누락")
        return
    if not isinstance(tr, dict):
        errors.append("traffic: dict 필요")
        return
    for fname, fspec in TRAFFIC_FIELDS.items():
        if fname not in tr:
            errors.append(f"traffic.{fname}: 누락")
            continue
        validate_field(tr[fname], fspec, f"traffic.{fname}", errors)


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
        _validate_traffic(obj, errors)
        if "singleFlight" in obj:
            errors.append("singleFlight: traffic 모드에서 허용되지 않음")
    elif mode == "integrated":
        _validate_single_flight(obj, errors)
        _validate_traffic(obj, errors)

    return (len(errors) == 0), errors, obj
