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
    Msg4002_VehicleWarningEvent,
    Msg4101_CameraImageFrame,
    Msg4102_CameraStreamDescriptor,
    Msg4103_VehicleCollisionEvent,
)
from .msg_phase6 import (
    Msg3002_StrategicSeparation,
    Msg3003_TacticalSeparation,
)
from .msg_phase7 import (
    Msg5001_OperatorControlInput,
    Msg5002_CameraControlCommand,
    Msg5003_AbnormalSituationCommand,
)

# mid → dataclass 매핑 (단일 권위)
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
    "4002": Msg4002_VehicleWarningEvent,
    "4101": Msg4101_CameraImageFrame,
    "4102": Msg4102_CameraStreamDescriptor,
    "4103": Msg4103_VehicleCollisionEvent,
    "5001": Msg5001_OperatorControlInput,
    "5002": Msg5002_CameraControlCommand,
    "5003": Msg5003_AbnormalSituationCommand,
}

# 역방향 매핑: dataclass type → mid. DtamModule.send 가 dataclass 인스턴스
# 한 줄로 받아 mid 를 추론할 때 사용.
_DATACLASS_TO_MID: Dict[Type, str] = {cls: mid for mid, cls in ICD_REGISTRY.items()}


def get_icd_class(mid: str) -> Optional[Type]:
    """메시지 ID에 해당하는 dataclass 반환."""
    return ICD_REGISTRY.get(mid)


def mid_for_dataclass(cls: Type) -> Optional[str]:
    """dataclass type → 메시지 ID 역방향 lookup.

    SDK 가 dataclass 인스턴스만 받아 mid 를 자동으로 결정할 때 사용.
    매칭되지 않으면 None.
    """
    return _DATACLASS_TO_MID.get(cls)


def _dict_to_dataclass(cls: Type, data: Dict[str, Any]) -> Any:
    """중첩 dict 를 재귀적으로 dataclass 인스턴스로 변환.

    sub-dataclass 필드는 dict 일 때 재귀적으로 변환. ``List[X]``, ``Dict[k, X]``,
    ``Optional[X]`` 도 처리한다. ``from __future__ import annotations`` 로 인해
    field type 이 문자열일 수 있어 ``typing.get_type_hints`` 로 실제 타입 객체를 얻는다.
    """
    if not dataclasses.is_dataclass(cls) or not isinstance(data, dict):
        return data

    resolved_types = _resolve_field_types(cls)
    kwargs: Dict[str, Any] = {}

    for fname, ftype in resolved_types.items():
        if fname not in data:
            continue
        kwargs[fname] = _coerce_value(data[fname], ftype)

    return cls(**kwargs)


def _resolve_field_types(cls: Type) -> Dict[str, Any]:
    """dataclass 의 모든 field 의 실제 타입(문자열 annotation 해소)."""
    import typing
    try:
        hints = typing.get_type_hints(cls)
    except Exception:
        hints = {}
    resolved: Dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        resolved[f.name] = hints.get(f.name, f.type)
    return resolved


def _coerce_value(val: Any, target_type: Any) -> Any:
    """``val`` 을 ``target_type`` 에 맞춰 변환. dataclass 인 경우 재귀."""
    import typing
    if target_type is None:
        return val
    origin = typing.get_origin(target_type)
    args = typing.get_args(target_type)

    # Optional[X] / Union[X, None] — None 이면 그대로, 아니면 첫 비-None arg 로
    if origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        if val is None:
            return None
        if non_none:
            return _coerce_value(val, non_none[0])
        return val

    # List[X]
    if origin in (list, typing.List) and isinstance(val, list):
        if not args:
            return list(val)
        item_type = args[0]
        return [_coerce_value(v, item_type) for v in val]

    # Dict[k, V]
    if origin in (dict, typing.Dict) and isinstance(val, dict):
        if len(args) == 2:
            v_type = args[1]
            return {k: _coerce_value(v, v_type) for k, v in val.items()}
        return dict(val)

    # nested dataclass
    if dataclasses.is_dataclass(target_type) and isinstance(val, dict):
        return _dict_to_dataclass(target_type, val)

    return val


def parse_payload(mid: str, data: Dict[str, Any]) -> Any:
    """wire dict payload 를 해당 ICD dataclass 인스턴스로 변환.

    dataclass 가 ``from_wire(cls, data)`` classmethod 를 정의하면 우선 사용.
    이 hook 으로 4001 처럼 ICD wire 모양과 dataclass 모양이 다른 메시지를
    SDK 한 곳에서 정렬한다. 일반 메시지는 ``_dict_to_dataclass`` 로 자동 매핑.

    변환 실패 시 원본 dict 를 그대로 반환.
    """
    cls = ICD_REGISTRY.get(mid)
    if cls is None:
        return data
    custom = getattr(cls, "from_wire", None)
    if callable(custom):
        try:
            return custom(data)
        except Exception:
            return data
    try:
        return _dict_to_dataclass(cls, data)
    except Exception:
        return data


def to_dict(obj: Any) -> Dict[str, Any]:
    """dataclass 인스턴스를 wire dict 로 변환.

    인스턴스가 ``to_wire()`` 메서드를 가지면 우선 사용 (4001 처럼 wire 모양이
    dataclass 와 다른 경우). 일반 dataclass 는 ``dataclasses.asdict``.
    """
    custom = getattr(obj, "to_wire", None)
    if callable(custom):
        try:
            return custom()
        except Exception:
            pass
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, dict):
        return obj
    return {"_raw": repr(obj)}


def get_example_payload(mid: str) -> Dict[str, Any]:
    """메시지 ID 에 대한 기본값 예시 wire payload 생성.

    ``to_wire`` 가 있으면 wire 포맷으로, 아니면 ``asdict`` 로 직렬화.
    """
    cls = ICD_REGISTRY.get(mid)
    if cls is None:
        return {}
    try:
        instance = cls()
        return to_dict(instance)
    except Exception:
        return {}
