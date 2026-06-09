"""VehicleModule: UAM flight trajectory generator and DTAM 4001 publisher.

Package layout:
  app/
    server.py                 FastAPI app factory
    web/                      Frontend assets
    services/                 Integrated flight service and 4001 payload builder
      integrated_service.py
      msg4001.py
    domain/
      dynamics/               Flight trajectory simulation
      transform/              WGS84 to local NED coordinate conversion
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
