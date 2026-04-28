"""UAM Flight Simulator — Data types and models."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ── Unit constants ──────────────────────────────────────────────
FT_TO_M = 0.3048
M_TO_FT = 1.0 / FT_TO_M
KNOT_TO_MPS = 0.514444
MPS_TO_KNOT = 1.0 / KNOT_TO_MPS


# ── ICD Phase codes ─────────────────────────────────────────────
class Phase(str, Enum):
    A = "A"  # gate-out taxi
    B = "B"  # vertical takeoff
    C = "C"  # departure transition
    D = "D"  # departure turn
    E = "E"  # climb out
    F = "F"  # cruise
    G = "G"  # arrival transition
    H = "H"  # arrival turn
    I = "I"  # final approach
    J = "J"  # landing
    K = "K"  # gate-in taxi

TURN_PHASES = {Phase.D, Phase.H}
NON_TURN_PHASES = {Phase.A, Phase.B, Phase.C, Phase.E, Phase.F,
                   Phase.G, Phase.I, Phase.J, Phase.K}


# ── Simulation flight modes ─────────────────────────────────────
class FlightMode(str, Enum):
    WAITING = "waiting"
    GATE_TAXI = "gate_taxi"
    VERTICAL_CLIMB = "vertical_climb"
    TRANSITION = "transition"
    CLIMB = "climb"
    CRUISE = "cruise"
    DESCENT = "descent"
    APPROACH = "approach"
    VERTICAL_DESCENT = "vertical_descent"
    GATE_IN = "gate_in"
    ENDED = "ended"


# ── Coordinate types ────────────────────────────────────────────
@dataclass(frozen=True)
class LLA:
    """Latitude / Longitude / Altitude coordinate."""
    lat: float
    lon: float
    alt: float  # metres

    def distance_to(self, other: LLA) -> float:
        """Haversine great-circle distance in metres (ignores altitude)."""
        R = 6_378_137.0
        d_lat = math.radians(other.lat - self.lat)
        d_lon = math.radians(other.lon - self.lon)
        a = (math.sin(d_lat / 2) ** 2
             + math.cos(math.radians(self.lat))
             * math.cos(math.radians(other.lat))
             * math.sin(d_lon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass(frozen=True)
class XY:
    """Local projected coordinate in km."""
    x: float
    y: float


# ── ICD data structures ─────────────────────────────────────────
@dataclass
class Departure:
    vertiport: str
    std: str          # HH:MM:SS
    dep_gate_number: str
    eobt: str
    dep_fato_number: str
    etot: str


@dataclass
class Arrival:
    vertiport: str
    sta: str
    arr_gate_number: str
    eibt: str
    arr_fato_number: str
    eldt: str


@dataclass
class EnRouteSegment:
    seq: int
    phase: Phase
    start_lla: LLA
    end_lla: LLA
    target_speed: float           # m/s
    turn_direction: Optional[str] = None   # "CW" or "CCW"
    center_lla: Optional[LLA] = None


@dataclass
class FlightPlan:
    flight_plan_number: int
    aircraft_id: str
    departure: Departure
    en_route: List[EnRouteSegment]
    arrival: Arrival


# ── Simulation data structures ──────────────────────────────────
@dataclass
class SegmentProfile:
    """Pre-computed kinematic profile for one ICD segment."""
    phase: Phase
    start_lla: LLA
    end_lla: LLA
    target_speed_mps: float
    distance_m: float             # 3-D path length
    duration_s: float             # estimated time to traverse
    points_lla: List[LLA] = field(default_factory=list)  # densified waypoints
    cum_dist_m: List[float] = field(default_factory=list)


@dataclass
class FlightTrajectoryPoint:
    """Single output record of the trajectory."""
    time_s: float         # seconds since simulation start
    clock: str            # HH:MM:SS wall-clock
    phase: str            # ICD phase code
    mode: str             # simulation flight mode
    lat: float
    lon: float
    alt_m: float
    speed_mps: float
    heading_deg: float
    track_heading_deg: float
    wind_e_mps: float = 0.0
    wind_n_mps: float = 0.0
    lateral_dev_m: float = 0.0
    battery_pct: float = 100.0


@dataclass
class SimulationConfig:
    """Tuneable simulation parameters."""
    tick_s: float = 0.1             # simulation time step (seconds)
    accel_mps2: float = 1.5        # longitudinal acceleration
    turn_rate_deg_s: float = 3.0   # standard rate turn
    vertical_climb_rate_mps: float = 2.54   # ~500 fpm
    vertical_descent_rate_mps: float = 2.54
    transition_speed_mps: float = 35.97     # ~70 knots
    min_safe_speed_mps: float = 25.0
    battery_capacity_s: float = 1800.0  # 30 min
    taxi_speed_mps: float = 5.0         # ground taxi speed

    # Wind parameters
    wind_enabled: bool = True
    wind_preset: str = "good"       # good / fair / bad / serious
    wind_time_speed: float = 60.0
    wind_cross_gain: float = 0.6
    wind_cross_return_s: float = 12.0
    wind_cross_max_m: float = 600.0
    wind_along_gain: float = 0.5
    wind_along_max_mps: float = 8.0
    wind_crab_max_deg: float = 12.0

    # Path densification
    densify_step_m: float = 20.0    # metres between interpolated points
    arc_step_deg: float = 1.0       # degrees per arc sample for turns

    # Trajectory smoothing
    trajectory_smoothing_enabled: bool = True
    trajectory_smoothing_tau_s: float = 0.45
    trajectory_smoothing_passes: int = 2
    trajectory_turn_smoothing_radius_m: float = 400.0
    trajectory_heading_lookahead_m: float = 400.0


# ── Async runtime types ────────────────────────────────────────
class FlightState(str, Enum):
    """Lifecycle state of a managed flight session."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class FlightStatus:
    """Status snapshot of one managed flight."""
    flight_id: str
    aircraft_id: str
    flight_plan_number: int
    state: FlightState
    current_point: Optional[FlightTrajectoryPoint]
    elapsed_s: float
    total_duration_s: float
