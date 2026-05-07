"""DTAMAirMobility — UAM flight trajectory generator + DTAM 4001 송신.

표준 layout:
  app/
    server.py                 — FastAPI app factory
    services/                 — 통합 비행 서비스 + 4001 페이로드 빌더
      integrated_service.py
      msg4001.py
    domain/
      dynamics/               — 비행체(트래젝토리) 시뮬레이터
      transform/              — WGS84 ↔ local NED 좌표 변환
  web/                        — 프런트엔드
"""

from .app.services.integrated_service import (
    ClockMode,
    FleetStatus,
    IntegratedAirMobilityService,
    VehicleSession,
    VehicleState,
    VehicleStatus,
)
from .app.domain.transform.coord_transform import LocalNEDFrame
from .app.services.msg4001 import (
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
