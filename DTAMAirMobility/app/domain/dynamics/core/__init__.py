"""Core simulation engine — types, geometry, wind, kinematics, dynamics."""

from .types import (
    LLA,
    XY,
    Phase,
    FlightMode,
    FlightPlan,
    FlightTrajectoryPoint,
    FlightState,
    FlightStatus,
    SimulationConfig,
    Departure,
    Arrival,
    EnRouteSegment,
    SegmentProfile,
    TURN_PHASES,
    NON_TURN_PHASES,
    FT_TO_M,
    M_TO_FT,
    KNOT_TO_MPS,
    MPS_TO_KNOT,
)
from .geo import LocalProjection, heading_between, distance_xy, wrap_heading
from .wind_model import WindModel, WindVector
from .flight_profile import SegmentKinematics, build_kinematics, total_flight_time, find_segment_at_time
from .flight_dynamics import DynamicsEngine
from .path_builder import build_segment_profiles
