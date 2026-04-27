"""DTAMAirMobility — UAM flight trajectory generator + DTAM 4001 송신.

구성:
 - ``simpleDynamics`` : 비행체(트래젝토리) 시뮬레이터
 - ``transform``      : WGS84 ↔ local NED 좌표 변환
 - ``publisher``      : MSG 4001 페이로드 빌더 (송신은 SDK ``DtamModule`` 이 담당)
 - ``service``        : 비행계획 + 시계 → 10 Hz 4001 스트리머
"""

from .service.integrated_service import (
    ClockMode,
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

__all__ = [
    "ClockMode",
    "FleetStatus",
    "IntegratedAirMobilityService",
    "VehicleSession",
    "VehicleState",
    "VehicleStatus",
    "LocalNEDFrame",
    "VehiclePublishContext",
    "build_4001_message",
    "build_vehicle_payload",
]

__version__ = "0.1.0"
