from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


SCHEMA_VERSION = "mission-icd.v1"


class MissionProfileCode(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"
    I = "I"
    J = "J"
    K = "K"


class MissionState(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    ERROR = "ERROR"


class ExecutionMode(str, Enum):
    SIM_SITL = "SIM_SITL"
    AIRSIM = "AIRSIM"
    EXTERNAL_ENGINE = "EXTERNAL_ENGINE"
    AUTOPILOT = "AUTOPILOT"


class CoordinateFrame(str, Enum):
    WGS84 = "WGS84"
    LOCAL_NED = "LOCAL_NED"


class StartCondition(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    AT_SIM_TIME = "AT_SIM_TIME"
    AT_STD = "AT_STD"
    AT_EVENT = "AT_EVENT"


class ResourceType(str, Enum):
    GATE = "GATE"
    FATO = "FATO"
    PAD = "PAD"
    CORRIDOR = "CORRIDOR"
    HOLD_FIX = "HOLD_FIX"


class ResourceUsage(str, Enum):
    DEP_OCCUPANCY = "DEP_OCCUPANCY"
    ARR_OCCUPANCY = "ARR_OCCUPANCY"
    TRANSIT = "TRANSIT"
    HOLD = "HOLD"


@dataclass
class GeoPosition:
    lat_deg: float
    lon_deg: float
    alt_m: float
    alt_ref: str = "MSL"
    x_m: Optional[float] = None
    y_m: Optional[float] = None
    z_m: Optional[float] = None


@dataclass
class NedPosition:
    north_m: float
    east_m: float
    down_m: float


@dataclass
class VehicleInfo:
    aircraft_id: str
    vehicle_type: str
    callsign: Optional[str] = None
    passenger_count: Optional[int] = None
    seat_capacity: Optional[int] = None
    performance_profile: Optional[str] = None


@dataclass
class MissionSchedule:
    timezone: str
    std: str
    start_condition: StartCondition = StartCondition.AT_SIM_TIME
    sta: Optional[str] = None
    etot: Optional[str] = None
    eldt: Optional[str] = None


@dataclass
class MissionEndpoint:
    vertiport_id: str
    gate_id: Optional[str] = None
    fato_id: Optional[str] = None
    position: Optional[GeoPosition] = None


@dataclass
class OperationalIntent:
    priority: int = 0
    corridor_id: Optional[str] = None
    entry_point_id: Optional[str] = None
    exit_point_id: Optional[str] = None
    lane_id: Optional[str] = None
    conformance_h_radius_m: float = 40.0
    conformance_v_radius_m: float = 30.0
    replan_policy: str = "GROUND_ONLY"


@dataclass
class MissionLeg:
    seq: int
    segment_id: MissionProfileCode
    phase: str
    start_ref: Optional[str] = None
    end_ref: Optional[str] = None
    lane_id: Optional[str] = None
    target_alt_m: Optional[float] = None
    target_speed_mps: Optional[float] = None
    duration_sec: Optional[float] = None
    acceptance_radius_m: Optional[float] = None
    hold_allowed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrajectoryPoint:
    seq: int
    lat_deg: float
    lon_deg: float
    alt_m: float
    alt_ref: str = "MSL"
    name: Optional[str] = None
    role: Optional[str] = None
    segment_id: Optional[MissionProfileCode] = None
    target_speed_mps: Optional[float] = None
    eta: Optional[str] = None
    lane_id: Optional[str] = None
    hold_sec: Optional[float] = None
    conformance_radius_m: Optional[float] = None
    ned: Optional[NedPosition] = None


@dataclass
class ResourceReservation:
    resource_type: ResourceType
    resource_id: str
    usage: ResourceUsage
    window_start: str
    window_end: str
    location_owner: Optional[str] = None


@dataclass
class ExecutionPolicy:
    execution_mode: ExecutionMode
    coordinate_frame: CoordinateFrame = CoordinateFrame.WGS84
    relative_to_start: bool = False
    body_relative: bool = False
    yaw_follow: bool = True
    auto_takeoff: bool = True
    auto_land: bool = True
    abort_behavior: str = "HOVER"
    lost_link_behavior: str = "HOLD"
    replan_allowed: bool = False


@dataclass
class SimPolicy:
    clock_id: str
    sim_start_time: str
    sim_speed: float = 1.0
    tick_period_sec: float = 1.0
    publish_period_ms: Optional[int] = None
    paused: bool = False


@dataclass
class MissionPlan:
    mission_id: str
    sortie_id: str
    created_at: str
    aircraft: VehicleInfo
    schedule: MissionSchedule
    origin: MissionEndpoint
    destination: MissionEndpoint
    operational_intent: OperationalIntent
    legs: list[MissionLeg]
    execution_policy: ExecutionPolicy
    planner_id: Optional[str] = None
    trajectory: list[TrajectoryPoint] = field(default_factory=list)
    resource_reservations: list[ResourceReservation] = field(default_factory=list)
    sim_policy: Optional[SimPolicy] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DispatchWaypoint:
    seq: int
    alt_m: float
    name: Optional[str] = None
    segment_id: Optional[MissionProfileCode] = None
    lat_deg: Optional[float] = None
    lon_deg: Optional[float] = None
    ned: Optional[NedPosition] = None
    target_speed_mps: Optional[float] = None
    acceptance_radius_m: Optional[float] = None
    hold_sec: Optional[float] = None


@dataclass
class MissionDispatch:
    dispatch_id: str
    mission_id: str
    aircraft_id: str
    issued_at: str
    execution_policy: ExecutionPolicy
    route: list[DispatchWaypoint]
    valid_after: Optional[str] = None
    sim_clock_ref: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MissionStatus:
    aircraft_id: str
    published_at: str
    state: MissionState
    phase: str
    position: GeoPosition
    mission_id: Optional[str] = None
    sortie_id: Optional[str] = None
    sim_time: Optional[str] = None
    segment_id: Optional[MissionProfileCode] = None
    lane_id: Optional[str] = None
    heading_deg: Optional[float] = None
    ground_speed_mps: Optional[float] = None
    progress_m: Optional[float] = None
    remain_m: Optional[float] = None
    atd: Optional[str] = None
    eta: Optional[str] = None
    origin_vertiport_id: Optional[str] = None
    destination_vertiport_id: Optional[str] = None
    dep_fato_id: Optional[str] = None
    dep_gate_id: Optional[str] = None
    arr_fato_id: Optional[str] = None
    arr_gate_id: Optional[str] = None
    passenger_count: Optional[int] = None
    spacing_distance_m: Optional[float] = None
    spacing_ttc_s: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SimClock:
    clock_id: str
    published_at: str
    sim_time: str
    sim_speed: float
    tick_dt_sim_sec: float
    tick_dt_real_sec: float
    paused: bool
    sequence_no: int
    source: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
