"""DTAM ICD 스키마 — 단일 권위.

모든 모듈이 이 패키지의 dataclass 만 사용합니다. dict 직접 송신은 하지 않음.

표준 사용:

    from dtam_client.schema import (
        Msg4001_VehicleStatus,
        Msg3001_ScheduledFlight,
        Position, Attitude, GPS,
    )

    payload = Msg4001_VehicleStatus(timestamp=..., vehicles={"UAM0001": {...}})
    mod.send(payload)         # SDK 가 자동으로 dict 직렬화 + mid 추론

서버측 검증/직렬화 헬퍼:

    from dtam_client.schema import parse_payload, to_dict, mid_for_dataclass
"""
from __future__ import annotations

# ── 공용 sub-dataclass (모든 메시지가 재사용) ──────────────────
from .icd_common import LLA, Vec3, Quaternion

# ── Phase 0: 0001/0002/0003 ────────────────────────────────────
from .msg_phase0 import (
    Msg0001_ModuleSettingInfo,
    Msg0002_ModuleStatus,
    Msg0003_CommonTimeInfo,
)

# ── Phase 1: 1001/1002/1003 ────────────────────────────────────
from .msg_phase1 import (
    Msg1001_SimModeSetup,
    Msg1002_SimulationSetup,
    Msg1003_ScenarioSetup,
    VehicleSimType, SingleFlight, Traffic,
    Precipitation, Fog, WeatherEffect, Gust, Wind,
    OperationTime, Vertiport, ScenarioWaypoint, RouteNetwork,
)

# ── Phase 2: 2001/2002/3001 ────────────────────────────────────
from .msg_phase2 import (
    Msg2001_FlightPlanRequest,
    Msg2002_DtamExecute,
    Msg3001_ScheduledFlight,
    DepartureInfo, ArrivalInfo, EnRouteSegment,
)

# ── Phase 5: 4001/4101 ────────────────────────────────────────
from .msg_phase5 import (
    Msg4001_VehicleStatus,
    Msg4101_CameraImageFrame,
    Position, Attitude, Actuator, Propulsion,
    GPS, IMU, Barometer, VehicleData,
)

# ── Phase 6: 3002/3003 ────────────────────────────────────────
from .msg_phase6 import (
    Msg3002_StrategicSeparation,
    Msg3003_TacticalSeparation,
    DirectToTarget, HoldAction, LandAction, TacticalAction,
)

# ── 레지스트리 + 직렬화 헬퍼 ───────────────────────────────────
from .icd_registry import (
    ICD_REGISTRY,
    get_icd_class,
    mid_for_dataclass,
    parse_payload,
    to_dict,
    get_example_payload,
)


__all__ = [
    # 공용
    "LLA", "Vec3", "Quaternion",
    # 메시지
    "Msg0001_ModuleSettingInfo", "Msg0002_ModuleStatus", "Msg0003_CommonTimeInfo",
    "Msg1001_SimModeSetup", "Msg1002_SimulationSetup", "Msg1003_ScenarioSetup",
    "Msg2001_FlightPlanRequest", "Msg2002_DtamExecute", "Msg3001_ScheduledFlight",
    "Msg4001_VehicleStatus", "Msg4101_CameraImageFrame",
    "Msg3002_StrategicSeparation", "Msg3003_TacticalSeparation",
    # Phase 1 sub-dataclass
    "VehicleSimType", "SingleFlight", "Traffic",
    "Precipitation", "Fog", "WeatherEffect", "Gust", "Wind",
    # Phase 2 sub-dataclass
    "OperationTime", "Vertiport", "ScenarioWaypoint", "RouteNetwork",
    "DepartureInfo", "ArrivalInfo", "EnRouteSegment",
    # Phase 5 sub-dataclass
    "Position", "Attitude", "Actuator", "Propulsion",
    "GPS", "IMU", "Barometer", "VehicleData",
    # Phase 6 sub-dataclass
    "DirectToTarget", "HoldAction", "LandAction", "TacticalAction",
    # 레지스트리/헬퍼
    "ICD_REGISTRY",
    "get_icd_class",
    "mid_for_dataclass",
    "parse_payload",
    "to_dict",
    "get_example_payload",
]
