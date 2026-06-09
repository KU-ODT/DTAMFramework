"""DTAMAirVehicle — UAM flight trajectory generator + DTAM 4001 publisher.

구성:
 - ``simpleDynamics`` : 비행체(트래젝토리) 시뮬레이터 (odt_mp 에서 분리)
 - ``transform``      : WGS84 ↔ local NED 좌표 변환
 - ``publisher``      : DTAM SDK 기반 MSG 4001 송신기
 - ``service``        : 비행계획 + 시계 → 10 Hz 4001 스트리머
 - ``gui``            : 얇은 Qt 대시보드
"""

from .service.integrated_service import (
    ClockMode,
    ControlMode,
    FleetStatus,
    IntegratedAirMobilityService,
    VehicleSession,
    VehicleState,
    VehicleStatus,
)
from .transform.coord_transform import LocalNEDFrame
from .publisher.msg4001 import (
    VehiclePublishContext,
    build_4001_message,
    build_vehicle_payload,
)
from .publisher.publisher import DtamVehiclePublisher

__all__ = [
    "ClockMode",
    "ControlMode",
    "FleetStatus",
    "IntegratedAirMobilityService",
    "VehicleSession",
    "VehicleState",
    "VehicleStatus",
    "LocalNEDFrame",
    "VehiclePublishContext",
    "build_4001_message",
    "build_vehicle_payload",
    "DtamVehiclePublisher",
]

__version__ = "0.1.0"
