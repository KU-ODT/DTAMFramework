"""ICD 메시지 레지스트리 — mid → dataclass 매핑 + 직렬화/역직렬화 유틸."""
from __future__ import annotations

import dataclasses
from typing import Any, Dict, Optional, Type

from .msg_phase0 import (
    Msg0001_ModuleSettingInfo,
    Msg0002_ModuleStatus,
    Msg0003_CommonTimeInfo,
)
from .msg_phase1 import (
    Msg1001_SimModeSetup,
    Msg1002_SimulationSetup,
    Msg1003_ScenarioSetup,
)
from .msg_phase2 import (
    Msg2001_FlightPlanRequest,
    Msg2002_DtamExecute,
    Msg3001_ScheduledFlight,
)
from .msg_phase5 import (
    Msg4001_VehicleStatus,
    Msg4101_CameraImageFrame,
)
from .msg_phase6 import (
    Msg3002_StrategicSeparation,
    Msg3003_TacticalSeparation,
)

# mid → dataclass 매핑
ICD_REGISTRY: Dict[str, Type] = {
    "0001": Msg0001_ModuleSettingInfo,
    "0002": Msg0002_ModuleStatus,
    "0003": Msg0003_CommonTimeInfo,
    "1001": Msg1001_SimModeSetup,
    "1002": Msg1002_SimulationSetup,
    "1003": Msg1003_ScenarioSetup,
    "2001": Msg2001_FlightPlanRequest,
    "2002": Msg2002_DtamExecute,
    "3001": Msg3001_ScheduledFlight,
    "3002": Msg3002_StrategicSeparation,
    "3003": Msg3003_TacticalSeparation,
    "4001": Msg4001_VehicleStatus,
    "4101": Msg4101_CameraImageFrame,
}


def get_icd_class(mid: str) -> Optional[Type]:
    """메시지 ID에 해당하는 dataclass 반환."""
    return ICD_REGISTRY.get(mid)


def _dict_to_dataclass(cls: Type, data: Dict[str, Any]) -> Any:
    """중첩 dict를 재귀적으로 dataclass 인스턴스로 변환."""
    if not dataclasses.is_dataclass(cls) or not isinstance(data, dict):
        return data

    field_types = {f.name: f.type for f in dataclasses.fields(cls)}
    kwargs = {}

    for fname, ftype in field_types.items():
        if fname not in data:
            continue
        val = data[fname]
        # resolve string type annotations
        resolved = _resolve_type(cls, fname)
        if resolved and dataclasses.is_dataclass(resolved) and isinstance(val, dict):
            kwargs[fname] = _dict_to_dataclass(resolved, val)
        elif isinstance(val, list) and resolved is list:
            # list of dataclass items — best effort
            kwargs[fname] = val
        else:
            kwargs[fname] = val

    return cls(**kwargs)


def _resolve_type(cls: Type, field_name: str) -> Optional[Type]:
    """dataclass 필드의 실제 타입을 반환 (Optional/List 무시)."""
    import typing
    for f in dataclasses.fields(cls):
        if f.name == field_name:
            origin = getattr(f.type, '__origin__', None) if hasattr(f.type, '__origin__') else None
            # handle string annotations
            if isinstance(f.type, str):
                return None
            if origin is typing.Union:
                args = [a for a in f.type.__args__ if a is not type(None)]
                return args[0] if args else None
            if dataclasses.is_dataclass(f.type):
                return f.type
            return None
    return None


def parse_payload(mid: str, data: Dict[str, Any]) -> Any:
    """dict payload를 해당 ICD dataclass 인스턴스로 변환.

    변환 실패 시 원본 dict를 그대로 반환.
    """
    cls = ICD_REGISTRY.get(mid)
    if cls is None:
        return data
    try:
        return _dict_to_dataclass(cls, data)
    except Exception:
        return data


def to_dict(obj: Any) -> Dict[str, Any]:
    """dataclass 인스턴스를 dict로 변환 (재귀)."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, dict):
        return obj
    return {"_raw": repr(obj)}


def get_example_payload(mid: str) -> Dict[str, Any]:
    """메시지 ID에 대한 기본값 예시 payload 생성."""
    cls = ICD_REGISTRY.get(mid)
    if cls is None:
        return {}
    try:
        instance = cls()
        return dataclasses.asdict(instance)
    except Exception:
        return {}
