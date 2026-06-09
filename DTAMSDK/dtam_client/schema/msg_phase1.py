"""Phase 1 메시지 — 1001 Sim Mode Setup, 1002 Simulation Setup, 1003 Scenario Setup."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .icd_common import LLA


# ── MSG 1001 ─────────────────────────────────────────────

@dataclass
class VehicleSimType:
    dynamics: str = "simple"           # simple | highFidelity (KP-2A)
    mainVehicleController: str = "Autopilot"  # Joystick | Keyboard | Autopilot


@dataclass
class MissionPlanningEntry:
    aircraftName: str = ""
    departureTime: str = ""            # HH:MM:SS per-aircraft STD
    std: str = ""                      # alias used by Mission ICD export
    departureName: str = ""
    arrivalName: str = ""
    routeData: Optional[Dict[str, Any]] = None
    # Optional per-aircraft dynamics/controller override. If None, inherit singleFlight.vehicleSimType.
    vehicleSimType: Optional[VehicleSimType] = None


@dataclass
class MissionPlanning:
    activeMissionId: str = ""
    missions: List[MissionPlanningEntry] = field(default_factory=list)


@dataclass
class SingleFlight:
    vehicleSimType: VehicleSimType = field(default_factory=VehicleSimType)
    missionPlanning: Optional[MissionPlanning] = None


@dataclass
class Traffic:
    trafficScenario: str = "low"       # low | middle | high | customed


@dataclass
class Msg1001_SimModeSetup:
    """MSG 1001: 시뮬레이션 모드 설정."""
    timestamp: str = ""
    operationMode: str = "single"      # single | traffic | integrated
    singleFlight: Optional[SingleFlight] = None
    traffic: Optional[Traffic] = None


# ── MSG 1002 ─────────────────────────────────────────────

@dataclass
class Precipitation:
    type: str = "none"                 # none | rainy | snow
    intensity: float = 0.0            # 0.0 ~ 1.0 (0.1 step)


@dataclass
class Fog:
    intensity: float = 0.0            # 0.0 ~ 1.0 (0.1 step)


@dataclass
class WeatherEffect:
    precipitation: Precipitation = field(default_factory=Precipitation)
    fog: Fog = field(default_factory=Fog)


@dataclass
class Gust:
    lat: float = 0.0
    lon: float = 0.0
    radius: float = 0.0


@dataclass
class Wind:
    grade: str = "normal"              # normal | warning | serious
    gust: Optional[Gust] = None


@dataclass
class Msg1002_SimulationSetup:
    """MSG 1002: 시뮬레이션 통제 — 재생, 날씨, 바람."""
    timestamp: str = ""
    simulationStartTime: str = ""
    simulationTime: str = ""
    simTimeOfDay: str = ""
    simSecondsOfDay: Optional[float] = None
    timeSource: str = ""
    playbackSpeed: int = 1             # 1 | 2 | 4 | 8
    playState: str = "play"            # play | pause | reset
    weatherEffect: WeatherEffect = field(default_factory=WeatherEffect)
    wind: Wind = field(default_factory=Wind)


# ── MSG 1003 ─────────────────────────────────────────────

@dataclass
class OperationTime:
    startTime: str = "09:00:00"        # HH:MM:SS
    endTime: str = "18:00:00"


@dataclass
class Vertiport:
    name: str = ""
    vertiportClass: str = "port"       # port | hub  (class는 예약어)
    lat: float = 0.0
    lon: float = 0.0
    angleDegrees: float = 0.0


@dataclass
class ScenarioWaypoint:
    waypointId: str = ""
    waypointName: str = ""
    lat: float = 0.0
    lon: float = 0.0
    altFt: float = 0.0
    links: List[str] = field(default_factory=list)


@dataclass
class RouteNetwork:
    waypoints: List[ScenarioWaypoint] = field(default_factory=list)


@dataclass
class Msg1003_ScenarioSetup:
    """MSG 1003: 시나리오 설정 — 버티포트, 경로망, 운용 시간."""
    timestamp: str = ""
    scenarioFileName: str = ""
    totalAircraftCount: int = 1
    mainVehicleType: str = "KP2A"      # KP2A | JobyS4
    operationTime: OperationTime = field(default_factory=OperationTime)
    vertiports: List[Vertiport] = field(default_factory=list)
    routeNetwork: RouteNetwork = field(default_factory=RouteNetwork)
