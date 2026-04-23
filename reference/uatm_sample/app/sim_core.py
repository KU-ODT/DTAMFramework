from __future__ import annotations

import bisect
import math
import random
from dataclasses import dataclass, replace
from typing import Callable

from app.schedule_flightplan_mode import (
    build_flightplan_state,
    normalize_flightplan_schedule,
)
from app.schedule_random_mode import build_random_schedule
from app.pathplanner import RoutePlanner
from app.wind_model import WindModel

# === Constants ===
SIM_START_SECONDS = 6 * 3600 + 30 * 60
SIM_DURATION_S = 15 * 3600
SIM_TICK_MS = 100
ACCEL_MPS2 = 1.5
FT_TO_M = 0.3048
M_TO_FT = 1.0 / FT_TO_M
KNOT_TO_MPS = 0.514444
STANDARD_CLIMB_RATE_FPM = 500.0
STANDARD_CLIMB_RATE_MPS = STANDARD_CLIMB_RATE_FPM * FT_TO_M / 60.0
TRANSITION_ALT_FT = 50.0
TRANSITION_ALT_M = TRANSITION_ALT_FT * FT_TO_M
TRANSITION_SPEED_KNOT = 70.0
TRANSITION_SPEED_MPS = TRANSITION_SPEED_KNOT * KNOT_TO_MPS
FLIGHT_ALT_M = 1000 * FT_TO_M
VERTIPORT_ALT_M = 5.0
PREFLIGHT_WAIT_S = 10
DEFAULT_GATE_WAIT_S = 60
DEFAULT_GROUND_TAXI_S = 5 * 60
DEFAULT_FATO_PREP_S = 2 * 60
DEFAULT_TURNAROUND_S = 12 * 60
BATTERY_CAPACITY_S = 30 * 60
EMERGENCY_SPEED_MIN_RATIO = 0.3
FAST_SPEEDS = (1, 2, 5, 10, 20, 30)
PLANE_ICON_IDS = ["plane1", "plane2", "plane3", "plane4"]
TRAFFIC_LEVELS = {
    "Low": 100,
    "Middle": 2500,
    "High": 25000,
}
MODE_WAITING = "waiting"
MODE_TAKEOFF = "takeoff"
MODE_CRUISE = "cruise"
MODE_LANDING = "landing"
MODE_HOLD = "hold"
MODE_ENDED = "ended"
MODE_FAILED = "failed"
HOLD_RADIUS_M = 1500.0
HOLD_RADIUS_KM = HOLD_RADIUS_M / 1000.0
FLIGHT_PATH_OFFSET_M = 250.0
FLIGHT_PATH_OFFSET_KM = FLIGHT_PATH_OFFSET_M / 1000.0
FLIGHT_PATH_DENSIFY_KM = 0.2
EMERGENCY_PATH_DENSIFY_KM = 0.05
FLIGHT_PATH_MIN_TURN_RADIUS_FACTOR = 2.5
FLIGHT_PATH_FILLET_ANGLE_DEG = 3.0
TURN_RADIUS_SPEED_MPS = 30.0
MIN_SAFE_SPEED_MPS = 25.0
RISK_PREDICT_HORIZON_S = 20.0
RISK_LATERAL_M = 50.0
RISK_DIRECTION_COS = 0.5
RISK_UPDATE_INTERVAL_S = 2.0
PREDICTION_STEP_S = 4.0
RISK_PROX_LV1_M = 450.0
RISK_PROX_LV2_M = 300.0
RISK_PROX_LV3_M = 150.0
RISK_BATT_LV1_PCT = 30.0
RISK_BATT_LV2_PCT = 25.0
RISK_BATT_LV3_PCT = 10.0
OPS_METRICS_INTERVAL_S = 10.0
WIND_ENABLED = 1
WIND_TIME_SPEED = 60.0
WIND_SMOOTH_S = 2.0
WIND_CROSS_GAIN = 0.6
WIND_CROSS_RETURN_S = 12.0
WIND_CROSS_MAX_M = 600.0
WIND_ALONG_GAIN = 0.5
WIND_ALONG_MAX_MPS = 8.0
WIND_CRAB_MAX_DEG = 12.0
WIND_EFFECT_SCALE = 1.0

UTURN_TRIGGER_COS = -0.90   # -0.90이면 약 154도 이상부터 유턴 취급
UTURN_ARC_STEP_KM = 0.02    # 20m 간격(더 둥글게). 성능 걱정이면 0.05 유지해도 됨


# === Data models ===
@dataclass
class SimulationRules:
    speed_mps: float
    accel_mps2: float
    climb_rate_fpm: float
    transition_alt_ft: float
    transition_speed_knot: float
    holding_s: int
    takeoff_s: int
    landing_s: int
    battery_capacity_s: float
    min_safe_speed_mps: float
    turn_rate_deg_s: float
    separation_m: int
    warning_m: int
    warning_ec_s: int
    warning_trailing_circles: int
    warning_leading_knot_delta: int
    caution_m: int
    caution_ec_s: int
    caution_trailing_knot_delta: int
    caution_leading_knot_delta: int
    risk_predict_horizon_s: float
    risk_lateral_m: float
    risk_direction_cos: float
    risk_update_interval_s: float
    risk_proximity_lv1_m: float
    risk_proximity_lv2_m: float
    risk_proximity_lv3_m: float
    risk_battery_lv1_pct: float
    risk_battery_lv2_pct: float
    risk_battery_lv3_pct: float
    rnp_max_lat_m: float
    rnp_max_ver_m: float
    rnp_r_lv1: float
    rnp_r_lv2: float
    rnp_r_lv3: float
    rnp_ttv_lv1_s: float
    rnp_ttv_lv2_s: float
    wind_enabled: int
    wind_time_speed: float
    wind_smooth_s: float
    wind_cross_gain: float
    wind_cross_return_s: float
    wind_cross_max_m: float
    wind_along_gain: float
    wind_along_max_mps: float
    wind_crab_max_deg: float
    operation_start_min: int
    operation_end_min: int
    operation_goal_count: int


@dataclass
class AutopilotSettings:
    enabled: bool
    duration_s: float
    lv1_delta_knot: float
    lv2_delta_knot: float
    lv3_delta_knot: float


DEFAULT_RULES = SimulationRules(
    speed_mps=100.0 * KNOT_TO_MPS,
    accel_mps2=ACCEL_MPS2,
    climb_rate_fpm=STANDARD_CLIMB_RATE_FPM,
    transition_alt_ft=TRANSITION_ALT_FT,
    transition_speed_knot=TRANSITION_SPEED_KNOT,
    holding_s=2 * 60,
    takeoff_s=60,
    landing_s=2 * 60,
    battery_capacity_s=BATTERY_CAPACITY_S,
    min_safe_speed_mps=MIN_SAFE_SPEED_MPS,
    turn_rate_deg_s=3.0,
    separation_m=300,
    warning_m=150,
    warning_ec_s=5,
    warning_trailing_circles=1,
    warning_leading_knot_delta=10,
    caution_m=300,
    caution_ec_s=10,
    caution_trailing_knot_delta=-10,
    caution_leading_knot_delta=10,
    risk_predict_horizon_s=RISK_PREDICT_HORIZON_S,
    risk_lateral_m=RISK_LATERAL_M,
    risk_direction_cos=RISK_DIRECTION_COS,
    risk_update_interval_s=RISK_UPDATE_INTERVAL_S,
    risk_proximity_lv1_m=RISK_PROX_LV1_M,
    risk_proximity_lv2_m=RISK_PROX_LV2_M,
    risk_proximity_lv3_m=RISK_PROX_LV3_M,
    risk_battery_lv1_pct=RISK_BATT_LV1_PCT,
    risk_battery_lv2_pct=RISK_BATT_LV2_PCT,
    risk_battery_lv3_pct=RISK_BATT_LV3_PCT,
    rnp_max_lat_m=54.0,
    rnp_max_ver_m=0.0,
    rnp_r_lv1=0.4,
    rnp_r_lv2=0.7,
    rnp_r_lv3=1.0,
    rnp_ttv_lv1_s=10.0,
    rnp_ttv_lv2_s=5.0,
    wind_enabled=WIND_ENABLED,
    wind_time_speed=WIND_TIME_SPEED,
    wind_smooth_s=WIND_SMOOTH_S,
    wind_cross_gain=WIND_CROSS_GAIN,
    wind_cross_return_s=WIND_CROSS_RETURN_S,
    wind_cross_max_m=WIND_CROSS_MAX_M,
    wind_along_gain=WIND_ALONG_GAIN,
    wind_along_max_mps=WIND_ALONG_MAX_MPS,
    wind_crab_max_deg=WIND_CRAB_MAX_DEG,
    operation_start_min=6 * 60 + 30,
    operation_end_min=21 * 60 + 30,
    operation_goal_count=2500,
)

DEFAULT_AUTOPILOT = AutopilotSettings(
    enabled=False,
    duration_s=10.0,
    lv1_delta_knot=10.0,
    lv2_delta_knot=20.0,
    lv3_delta_knot=30.0,
)


# === Flight data ===
@dataclass
class FlightProfile:
    transition_alt_m: float
    transition_speed_mps: float
    peak_speed_mps: float
    vert_time_s: float
    diag_time_s: float
    accel_time_s: float
    cruise_time_s: float
    takeoff_time_s: float
    cruise_total_time_s: float
    landing_time_s: float
    total_time_s: float
    dist_takeoff_diag_m: float
    dist_accel_m: float
    dist_cruise_m: float
    dist_landing_diag_m: float


@dataclass
class Flight:
    flight_id: int
    name: str
    origin: str
    destination: str
    risk: str
    icon_id: str
    start_offset_s: int
    speed_mps: float
    points_xy: list[tuple[float, float]]
    points_alt_m: list[float]
    cum_dist_m: list[float]
    total_dist_m: float
    accel_time_s: float
    cruise_time_s: float
    total_time_s: float
    peak_speed_mps: float
    path_nodes: list[str]
    path_segment_idx: list[int] | None = None
    profile: FlightProfile | None = None
    preflight_wait_s: float = PREFLIGHT_WAIT_S
    aircraft_id: str = ""
    local_id: str = ""
    dep_fato_no: str = ""
    dep_gate_no: str = ""
    arr_fato_no: str = ""
    arr_gate_no: str = ""
    source_file: str = ""
    scheduled_takeoff_s: int | None = None
    actual_takeoff_s: int | None = None
    std_s: float | None = None
    sta_s: float | None = None
    ata_s: float | None = None


@dataclass
class FlightControl:
    speed_override_mps: float | None = None
    manual_active: bool = False
    manual_dist_m: float | None = None
    manual_arrival_s: float | None = None
    manual_landing_alt_m: float | None = None
    emergency_active: bool = False
    hold_active: bool = False
    hold_loops_total: int = 0
    hold_start_time_s: float = 0.0
    hold_start_dist_m: float = 0.0
    hold_center_xy: tuple[float, float] | None = None
    hold_start_angle_rad: float = 0.0
    hold_speed_mps: float = 0.0
    hold_alt_m: float = FLIGHT_ALT_M
    hold_radius_m: float = HOLD_RADIUS_M
    wind_effect_scale: float = 1.0
    wind_effect_target_scale: float | None = None
    wind_effect_start_scale: float = 1.0
    wind_effect_start_s: float = 0.0
    wind_effect_ramp_s: float = 0.0
    autopilot_active: bool = False
    autopilot_level: int = 0
    autopilot_start_s: float = 0.0
    autopilot_duration_s: float = 0.0
    autopilot_delta_mps: float = 0.0
    autopilot_base_speed_mps: float = 0.0
    no_route_active: bool = False
    no_route_reason: str = ""


@dataclass
class FlightSchedule:
    schedule_id: int
    risk: str
    start_offset_s: int
    origin: str
    destination: str
    aircraft_id: str = ""
    local_id: str = ""
    dep_fato_no: str = ""
    dep_gate_no: str = ""
    arr_fato_no: str = ""
    arr_gate_no: str = ""
    source_file: str = ""
    planned_takeoff_offset_s: int | None = None
    preflight_wait_s: int = PREFLIGHT_WAIT_S
    turnaround_s: int = DEFAULT_TURNAROUND_S


# === Geometry & path helpers ===
def _cumulative_dist_m(points_xy: list[tuple[float, float]]) -> list[float]:
    if not points_xy:
        return [0.0]
    cumulative = [0.0]
    for (x1, y1), (x2, y2) in zip(points_xy, points_xy[1:]):
        dx = (x2 - x1) * 1000.0
        dy = (y2 - y1) * 1000.0
        cumulative.append(cumulative[-1] + math.hypot(dx, dy))
    return cumulative


def _densify_points_xy(
    points_xy: list[tuple[float, float]],
    step_km: float,
) -> list[tuple[float, float]]:
    if step_km <= 0 or len(points_xy) < 2:
        return points_xy
    densified = [points_xy[0]]
    for (x1, y1), (x2, y2) in zip(points_xy, points_xy[1:]):
        dx = x2 - x1
        dy = y2 - y1
        seg_len = math.hypot(dx, dy)
        if seg_len <= 0:
            continue
        steps = int(seg_len / step_km)
        for step in range(1, steps + 1):
            t = (step * step_km) / seg_len
            if t >= 1:
                break
            densified.append((x1 + dx * t, y1 + dy * t))
        densified.append((x2, y2))
    return densified


def _polyline_length_m(points_xy: list[tuple[float, float]]) -> float:
    if len(points_xy) < 2:
        return 0.0
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points_xy, points_xy[1:]):
        total += math.hypot(x2 - x1, y2 - y1) * 1000.0
    return total


# === Numeric helpers ===
def _approach_value(current: float, target: float, step: float) -> float:
    if not math.isfinite(current):
        return target
    if not math.isfinite(target):
        return current
    if step <= 0.0:
        return current
    if current < target:
        return min(target, current + step)
    if current > target:
        return max(target, current - step)
    return current


def _exp_smooth_alpha(delta_s: float, tau_s: float) -> float:
    if delta_s <= 0.0:
        return 0.0
    if tau_s <= 0.0:
        return 1.0
    return 1.0 - math.exp(-delta_s / tau_s)


def _apply_min_safe_speed(speed_mps: float, min_speed_mps: float) -> float:
    if not math.isfinite(speed_mps):
        return speed_mps
    if not math.isfinite(min_speed_mps) or min_speed_mps <= 0.0:
        return speed_mps
    return max(float(min_speed_mps), float(speed_mps))


def _wrap_heading_deg(value: float) -> float:
    heading = float(value) % 360.0
    return heading + 360.0 if heading < 0.0 else heading


def _angle_delta_deg(current: float, target: float) -> float:
    delta = (float(target) - float(current) + 180.0) % 360.0 - 180.0
    return delta


# === Path projection helpers ===
def _project_point_to_polyline_m(
    points_xy: list[tuple[float, float]],
    px: float,
    py: float,
) -> tuple[float, float]:
    best_dist = math.inf
    best_along = 0.0
    along = 0.0
    for (ax, ay), (bx, by) in zip(points_xy, points_xy[1:]):
        dx = bx - ax
        dy = by - ay
        seg_len = math.hypot(dx, dy)
        if seg_len <= 1e-9:
            continue
        t = ((px - ax) * dx + (py - ay) * dy) / (seg_len * seg_len)
        t = max(0.0, min(1.0, t))
        proj_x = ax + dx * t
        proj_y = ay + dy * t
        dist = math.hypot(px - proj_x, py - proj_y)
        if dist < best_dist:
            best_dist = dist
            best_along = along + seg_len * t
        along += seg_len
    return best_dist * 1000.0, best_along * 1000.0


def _heading_vector(heading_deg: float) -> tuple[float, float]:
    rad = math.radians(float(heading_deg))
    return math.sin(rad), math.cos(rad)


def _distance_to_segment_km(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = ax + dx * t
    proj_y = ay + dy * t
    return math.hypot(px - proj_x, py - proj_y)


# === Segment mapping helpers ===
def _segment_index_map_monotone(
    points_xy: list[tuple[float, float]],
    node_xy: list[tuple[float, float]],
) -> list[int]:
    if len(node_xy) < 2:
        return [0 for _ in points_xy]
    cum_node_m = _cumulative_dist_m(node_xy)
    out: list[int] = []
    prev_seg = 0
    for px, py in points_xy:
        _, along_m = _project_point_to_polyline_m(node_xy, px, py)
        seg = bisect.bisect_right(cum_node_m, along_m) - 1
        seg = max(0, min(seg, len(node_xy) - 2))
        if seg < prev_seg:
            seg = prev_seg
        prev_seg = seg
        out.append(seg)
    return out


# === Flight profile helpers ===
def _build_flight_profile(
    total_dist_m: float,
    target_speed_mps: float,
    rules: SimulationRules | None = None,
) -> FlightProfile:
    def _accel_distance(v0: float, v1: float, accel: float) -> float:
        if accel <= 0.0 or v1 <= v0:
            return 0.0
        return (v1 * v1 - v0 * v0) / (2.0 * accel)

    def _solve_peak_speed(
        distance_m: float,
        v_trans: float,
        diag_time_s: float,
        accel: float,
    ) -> float:
        if accel <= 0.0:
            return v_trans
        coef_a = 1.0 / (2.0 * accel)
        coef_b = 0.5 * diag_time_s
        coef_c = diag_time_s * v_trans - (v_trans * v_trans) / (2.0 * accel) - distance_m
        disc = coef_b * coef_b - 4.0 * coef_a * coef_c
        if disc <= 0.0:
            return v_trans
        peak = (-coef_b + math.sqrt(disc)) / (2.0 * coef_a)
        return max(v_trans, peak)

    total_dist_m = max(0.0, float(total_dist_m))
    target_speed_mps = max(0.0, float(target_speed_mps))

    accel_mps2 = ACCEL_MPS2
    climb_rate_fpm = STANDARD_CLIMB_RATE_FPM
    transition_alt_ft = TRANSITION_ALT_FT
    transition_speed_knot = TRANSITION_SPEED_KNOT
    if rules is not None:
        accel_mps2 = float(rules.accel_mps2)
        climb_rate_fpm = float(rules.climb_rate_fpm)
        transition_alt_ft = float(rules.transition_alt_ft)
        transition_speed_knot = float(rules.transition_speed_knot)

    if not math.isfinite(accel_mps2):
        accel_mps2 = ACCEL_MPS2
    if not math.isfinite(climb_rate_fpm):
        climb_rate_fpm = STANDARD_CLIMB_RATE_FPM
    if not math.isfinite(transition_alt_ft):
        transition_alt_ft = TRANSITION_ALT_FT
    if not math.isfinite(transition_speed_knot):
        transition_speed_knot = TRANSITION_SPEED_KNOT

    accel_mps2 = max(0.0, accel_mps2)
    climb_rate_fpm = max(0.0, climb_rate_fpm)
    transition_alt_ft = max(0.0, transition_alt_ft)
    transition_speed_knot = max(0.0, transition_speed_knot)

    transition_alt_m = transition_alt_ft * FT_TO_M
    transition_alt_m = min(max(transition_alt_m, VERTIPORT_ALT_M), FLIGHT_ALT_M)

    vert_rate = float(climb_rate_fpm * FT_TO_M / 60.0)
    vert_time = 0.0
    diag_time = 0.0
    if vert_rate > 0.0:
        vert_time = max(0.0, transition_alt_m - VERTIPORT_ALT_M) / vert_rate
        diag_time = max(0.0, FLIGHT_ALT_M - transition_alt_m) / vert_rate

    if total_dist_m <= 0.0 or target_speed_mps <= 0.0:
        return FlightProfile(
            transition_alt_m=transition_alt_m,
            transition_speed_mps=0.0,
            peak_speed_mps=0.0,
            vert_time_s=0.0,
            diag_time_s=0.0,
            accel_time_s=0.0,
            cruise_time_s=0.0,
            takeoff_time_s=0.0,
            cruise_total_time_s=0.0,
            landing_time_s=0.0,
            total_time_s=0.0,
            dist_takeoff_diag_m=0.0,
            dist_accel_m=0.0,
            dist_cruise_m=0.0,
            dist_landing_diag_m=0.0,
        )

    transition_speed_mps = transition_speed_knot * KNOT_TO_MPS
    transition_speed = min(target_speed_mps, transition_speed_mps)
    if diag_time <= 0.0:
        transition_speed = 0.0

    peak_speed = target_speed_mps
    if diag_time > 0.0:
        dist_diag_up = 0.5 * transition_speed * diag_time
        dist_accel_target = _accel_distance(transition_speed, peak_speed, accel_mps2)
        dist_diag_down_target = 0.5 * (peak_speed + transition_speed) * diag_time
        dist_noncruise = dist_diag_up + dist_accel_target + dist_diag_down_target
        if total_dist_m < dist_noncruise:
            dist_min = 1.5 * transition_speed * diag_time
            if total_dist_m >= dist_min and accel_mps2 > 0.0:
                peak_speed = _solve_peak_speed(
                    total_dist_m,
                    transition_speed,
                    diag_time,
                    accel_mps2,
                )
                peak_speed = min(peak_speed, target_speed_mps)
            else:
                transition_speed = total_dist_m / (1.5 * diag_time) if diag_time > 0.0 else 0.0
                transition_speed = min(transition_speed, target_speed_mps)
                peak_speed = transition_speed
    elif accel_mps2 > 0.0:
        dist_accel_target = _accel_distance(0.0, peak_speed, accel_mps2)
        if total_dist_m < dist_accel_target:
            peak_speed = math.sqrt(max(0.0, 2.0 * accel_mps2 * total_dist_m))
            peak_speed = min(peak_speed, target_speed_mps)

    accel_time = 0.0
    if peak_speed > transition_speed and accel_mps2 > 0.0:
        accel_time = (peak_speed - transition_speed) / accel_mps2

    dist_takeoff_diag = 0.5 * transition_speed * diag_time
    dist_landing_diag = 0.5 * (peak_speed + transition_speed) * diag_time
    dist_accel = 0.5 * (transition_speed + peak_speed) * accel_time
    dist_cruise = max(0.0, total_dist_m - dist_takeoff_diag - dist_accel - dist_landing_diag)
    cruise_time = dist_cruise / peak_speed if peak_speed > 0.0 else 0.0

    takeoff_time = vert_time + diag_time
    cruise_total_time = accel_time + cruise_time
    landing_time = diag_time + vert_time
    total_time = takeoff_time + cruise_total_time + landing_time

    return FlightProfile(
        transition_alt_m=transition_alt_m,
        transition_speed_mps=transition_speed,
        peak_speed_mps=peak_speed,
        vert_time_s=vert_time,
        diag_time_s=diag_time,
        accel_time_s=accel_time,
        cruise_time_s=cruise_time,
        takeoff_time_s=takeoff_time,
        cruise_total_time_s=cruise_total_time,
        landing_time_s=landing_time,
        total_time_s=total_time,
        dist_takeoff_diag_m=dist_takeoff_diag,
        dist_accel_m=dist_accel,
        dist_cruise_m=dist_cruise,
        dist_landing_diag_m=dist_landing_diag,
    )


def _distance_at_time_profile(profile: FlightProfile, t_s: float) -> float:
    if t_s <= 0.0:
        return 0.0
    dist_total = (
        profile.dist_takeoff_diag_m
        + profile.dist_accel_m
        + profile.dist_cruise_m
        + profile.dist_landing_diag_m
    )
    if profile.vert_time_s > 0.0 and t_s <= profile.vert_time_s:
        return 0.0
    t = max(0.0, t_s - profile.vert_time_s)
    if profile.diag_time_s > 0.0 and t <= profile.diag_time_s:
        accel = profile.transition_speed_mps / profile.diag_time_s
        return 0.5 * accel * t * t

    dist = profile.dist_takeoff_diag_m
    t = max(0.0, t - profile.diag_time_s)
    if profile.accel_time_s > 0.0 and t <= profile.accel_time_s:
        accel = (profile.peak_speed_mps - profile.transition_speed_mps) / profile.accel_time_s
        return dist + profile.transition_speed_mps * t + 0.5 * accel * t * t

    dist += profile.dist_accel_m
    t = max(0.0, t - profile.accel_time_s)
    if t <= profile.cruise_time_s:
        return dist + profile.peak_speed_mps * t

    dist += profile.dist_cruise_m
    t = max(0.0, t - profile.cruise_time_s)
    if profile.diag_time_s > 0.0 and t <= profile.diag_time_s:
        accel = (profile.transition_speed_mps - profile.peak_speed_mps) / profile.diag_time_s
        return dist + profile.peak_speed_mps * t + 0.5 * accel * t * t

    return dist_total


def _speed_at_time_profile(profile: FlightProfile, t_s: float) -> float:
    if t_s <= 0.0:
        return 0.0
    if profile.vert_time_s > 0.0 and t_s <= profile.vert_time_s:
        return 0.0
    t = max(0.0, t_s - profile.vert_time_s)
    if profile.diag_time_s > 0.0 and t <= profile.diag_time_s:
        return profile.transition_speed_mps * (t / profile.diag_time_s)
    t = max(0.0, t - profile.diag_time_s)
    if profile.accel_time_s > 0.0 and t <= profile.accel_time_s:
        return profile.transition_speed_mps + (
            (profile.peak_speed_mps - profile.transition_speed_mps) * (t / profile.accel_time_s)
        )
    t = max(0.0, t - profile.accel_time_s)
    if t <= profile.cruise_time_s:
        return profile.peak_speed_mps
    t = max(0.0, t - profile.cruise_time_s)
    if profile.diag_time_s > 0.0 and t <= profile.diag_time_s:
        return profile.peak_speed_mps + (
            (profile.transition_speed_mps - profile.peak_speed_mps) * (t / profile.diag_time_s)
        )
    return 0.0


def _altitude_at_time_profile(profile: FlightProfile, t_s: float) -> float:
    if t_s <= 0.0:
        return VERTIPORT_ALT_M
    if profile.vert_time_s > 0.0 and t_s <= profile.vert_time_s:
        ratio = min(1.0, t_s / profile.vert_time_s)
        return VERTIPORT_ALT_M + (profile.transition_alt_m - VERTIPORT_ALT_M) * ratio
    t = max(0.0, t_s - profile.vert_time_s)
    if profile.diag_time_s > 0.0 and t <= profile.diag_time_s:
        ratio = min(1.0, t / profile.diag_time_s)
        return profile.transition_alt_m + (FLIGHT_ALT_M - profile.transition_alt_m) * ratio
    t = max(0.0, t - profile.diag_time_s)
    cruise_span = profile.accel_time_s + profile.cruise_time_s
    if t <= cruise_span:
        return FLIGHT_ALT_M
    t = max(0.0, t - cruise_span)
    if profile.diag_time_s > 0.0 and t <= profile.diag_time_s:
        ratio = min(1.0, t / profile.diag_time_s)
        return FLIGHT_ALT_M - (FLIGHT_ALT_M - profile.transition_alt_m) * ratio
    t = max(0.0, t - profile.diag_time_s)
    if profile.vert_time_s > 0.0 and t <= profile.vert_time_s:
        ratio = min(1.0, t / profile.vert_time_s)
        return profile.transition_alt_m - (profile.transition_alt_m - VERTIPORT_ALT_M) * ratio
    return VERTIPORT_ALT_M


# === Path sampling helpers ===
def _bisect_index(cum_dist_m: list[float], dist_m: float) -> int:
    if not cum_dist_m:
        return 0
    if dist_m <= 0:
        return 0
    if dist_m >= cum_dist_m[-1]:
        return len(cum_dist_m) - 1
    return bisect.bisect_left(cum_dist_m, dist_m)


def _position_at_distance(
    points_xy: list[tuple[float, float]],
    cum_dist_m: list[float],
    dist_m: float,
) -> tuple[float, float]:
    if not points_xy:
        return 0.0, 0.0
    if dist_m <= 0:
        return points_xy[0]
    if dist_m >= cum_dist_m[-1]:
        return points_xy[-1]
    idx = _bisect_index(cum_dist_m, dist_m)
    if idx <= 0:
        return points_xy[0]
    idx = min(idx, len(points_xy) - 1)
    prev_dist = cum_dist_m[idx - 1]
    seg_dist = cum_dist_m[idx] - prev_dist
    if seg_dist <= 0:
        return points_xy[idx]
    ratio = (dist_m - prev_dist) / seg_dist
    x1, y1 = points_xy[idx - 1]
    x2, y2 = points_xy[idx]
    return x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio


def _heading_at_distance(
    points_xy: list[tuple[float, float]],
    cum_dist_m: list[float],
    dist_m: float,
) -> float:
    if len(points_xy) < 2:
        return 0.0
    if dist_m <= 0:
        x1, y1 = points_xy[0]
        x2, y2 = points_xy[1]
    elif dist_m >= cum_dist_m[-1]:
        x1, y1 = points_xy[-2]
        x2, y2 = points_xy[-1]
    else:
        idx = _bisect_index(cum_dist_m, dist_m)
        idx = max(1, min(idx, len(points_xy) - 1))
        x1, y1 = points_xy[idx - 1]
        x2, y2 = points_xy[idx]
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return 0.0
    heading = math.degrees(math.atan2(dx, dy))
    if heading < 0:
        heading += 360.0
    return heading

def _heading_at_distance_smooth(
    points_xy: list[tuple[float, float]],
    cum_dist_m: list[float],
    dist_m: float,
    lookahead_m: float = 120.0,
) -> float:
    """
    폴리라인 경로에서 세그먼트 경계(코너)에서도 heading이 튀지 않도록,
    dist_m 주변 lookahead 구간 양 끝 점을 이용해 접선 방향을 계산합니다.
    wind의 cross offset을 적용할 때 코너에서 순간 점프가 생기는 문제를 줄입니다.
    """
    if len(points_xy) < 2:
        return 0.0
    if not cum_dist_m:
        return 0.0

    total = float(cum_dist_m[-1])
    if total <= 0.0 or lookahead_m <= 0.0:
        return _heading_at_distance(points_xy, cum_dist_m, dist_m)

    d = float(dist_m)
    d0 = max(0.0, d - float(lookahead_m))
    d1 = min(total, d + float(lookahead_m))
    if d1 - d0 <= 1e-3:
        return _heading_at_distance(points_xy, cum_dist_m, dist_m)

    x0, y0 = _position_at_distance(points_xy, cum_dist_m, d0)
    x1, y1 = _position_at_distance(points_xy, cum_dist_m, d1)
    dx = x1 - x0
    dy = y1 - y0
    if abs(dx) <= 1e-12 and abs(dy) <= 1e-12:
        return _heading_at_distance(points_xy, cum_dist_m, dist_m)

    heading = math.degrees(math.atan2(dx, dy))
    if heading < 0.0:
        heading += 360.0
    return heading


def _value_at_distance(
    values: list[float],
    cum_dist_m: list[float],
    dist_m: float,
) -> float:
    if not values:
        return 0.0
    if dist_m <= 0:
        return values[0]
    if dist_m >= cum_dist_m[-1]:
        return values[-1]
    idx = _bisect_index(cum_dist_m, dist_m)
    if idx <= 0:
        return values[0]
    idx = min(idx, len(values) - 1)
    prev_dist = cum_dist_m[idx - 1]
    seg_dist = cum_dist_m[idx] - prev_dist
    if seg_dist <= 0:
        return values[idx]
    ratio = (dist_m - prev_dist) / seg_dist
    return values[idx - 1] + (values[idx] - values[idx - 1]) * ratio


# === Prediction sampling helpers ===
def _prediction_time_steps(horizon_s: float) -> list[float]:
    horizon = float(horizon_s)
    if not math.isfinite(horizon) or horizon <= 0.0:
        return []
    step = float(PREDICTION_STEP_S)
    if not math.isfinite(step) or step <= 0.0:
        return [horizon]
    steps = int(horizon // step)
    dts = [step] * steps
    remainder = horizon - step * steps
    if remainder > 1e-6:
        dts.append(remainder)
    if not dts:
        dts = [horizon]
    return dts


def _path_has_uturn(
    points_xy: list[tuple[float, float]],
    trigger_cos: float = UTURN_TRIGGER_COS,
) -> bool:
    if len(points_xy) < 3:
        return False
    for (ax, ay), (bx, by), (cx, cy) in zip(points_xy, points_xy[1:], points_xy[2:]):
        v1x, v1y = bx - ax, by - ay
        v2x, v2y = cx - bx, cy - by
        l1 = math.hypot(v1x, v1y)
        l2 = math.hypot(v2x, v2y)
        if l1 <= 1e-9 or l2 <= 1e-9:
            continue
        dot = (v1x * v2x + v1y * v2y) / (l1 * l2)
        if dot <= float(trigger_cos):
            return True
    return False


# === Polyline cleanup helpers ===
def _clean_polyline_xy(
    points_xy: list[tuple[float, float]],
    min_dist_km: float = 1e-6,
) -> list[tuple[float, float]]:
    if not points_xy:
        return []
    cleaned: list[tuple[float, float]] = [points_xy[0]]
    last_x, last_y = points_xy[0]
    for x, y in points_xy[1:]:
        if math.hypot(x - last_x, y - last_y) >= float(min_dist_km):
            cleaned.append((x, y))
            last_x, last_y = x, y
    if len(cleaned) >= 2 and math.hypot(
        cleaned[-1][0] - cleaned[-2][0],
        cleaned[-1][1] - cleaned[-2][1],
    ) < float(min_dist_km):
        cleaned.pop()
    return cleaned


def _remove_backtracking_xy(
    points_xy: list[tuple[float, float]],
    reverse_cos: float = 0.0,
    min_seg_km: float = 1e-9,
    max_passes: int = 10,
) -> list[tuple[float, float]]:
    """
    드물게 생기는 '앞으로 가다가 잠깐 뒤로 갔다가 다시 앞으로 가는' 스파이크를 제거합니다.
    - reverse_cos: 연속 두 구간의 방향 코사인이 이 값보다 작으면(기본: 0.0 -> 90도 초과) 중간점을 제거
    - max_passes: 한 번 제거로 해결 안 되는 경우가 있어 여러 번 반복
    """
    pts = _clean_polyline_xy(points_xy, min_dist_km=min_seg_km)
    if len(pts) < 3:
        return pts

    for _ in range(max_passes):
        changed = False
        out: list[tuple[float, float]] = [pts[0]]

        for i in range(1, len(pts) - 1):
            p0x, p0y = out[-1]
            p1x, p1y = pts[i]
            p2x, p2y = pts[i + 1]

            v1x = p1x - p0x
            v1y = p1y - p0y
            v2x = p2x - p1x
            v2y = p2y - p1y

            l1 = math.hypot(v1x, v1y)
            l2 = math.hypot(v2x, v2y)

            if l1 <= float(min_seg_km):
                changed = True
                continue
            if l2 <= float(min_seg_km):
                changed = True
                continue

            dot = (v1x * v2x + v1y * v2y) / (l1 * l2)
            if dot < float(reverse_cos):
                changed = True
                continue

            out.append((p1x, p1y))

        out.append(pts[-1])

        pts = _clean_polyline_xy(out, min_dist_km=min_seg_km)
        if not changed or len(pts) < 3:
            break

    return pts


def _clip_tail_intersections_xy(
    points_xy: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """
    Tail-only self-intersection trim.
    Keeps earlier segments intact and shortens only the new (tail) segment.
    """
    if len(points_xy) < 4:
        return points_xy

    def cross(ax: float, ay: float, bx: float, by: float) -> float:
        return ax * by - ay * bx

    def segment_intersection(
        p1: tuple[float, float],
        p2: tuple[float, float],
        q1: tuple[float, float],
        q2: tuple[float, float],
    ) -> tuple[bool, tuple[float, float], float]:
        px, py = p1
        rx, ry = (p2[0] - p1[0], p2[1] - p1[1])
        qx, qy = q1
        sx, sy = (q2[0] - q1[0], q2[1] - q1[1])
        denom = cross(rx, ry, sx, sy)
        if abs(denom) <= 1e-12:
            return False, (0.0, 0.0), 0.0
        qmpx = qx - px
        qmpy = qy - py
        t = cross(qmpx, qmpy, sx, sy) / denom
        u = cross(qmpx, qmpy, rx, ry) / denom
        if t <= 1e-6 or t >= 1.0 - 1e-6:
            return False, (0.0, 0.0), 0.0
        if u <= 1e-6 or u >= 1.0 - 1e-6:
            return False, (0.0, 0.0), 0.0
        return True, (px + t * rx, py + t * ry), t

    out: list[tuple[float, float]] = [points_xy[0]]
    for point in points_xy[1:]:
        start = out[-1]
        hit_pt: tuple[float, float] | None = None
        hit_t = None
        for idx in range(1, len(out) - 1):
            hit, pt, t = segment_intersection(start, point, out[idx - 1], out[idx])
            if not hit:
                continue
            if hit_t is None or t < hit_t:
                hit_t = t
                hit_pt = pt
        if hit_pt is not None:
            point = hit_pt
        if point != out[-1]:
            out.append(point)
    return out


def _enforce_monotone_along_xy(
    points_xy: list[tuple[float, float]],
    ref_xy: list[tuple[float, float]],
    max_backstep_m: float = 5.0,
) -> list[tuple[float, float]]:
    if len(points_xy) < 3 or len(ref_xy) < 2:
        return points_xy

    out: list[tuple[float, float]] = [points_xy[0]]
    _, last_along_m = _project_point_to_polyline_m(ref_xy, points_xy[0][0], points_xy[0][1])

    for px, py in points_xy[1:-1]:
        _, along_m = _project_point_to_polyline_m(ref_xy, px, py)
        if along_m + float(max_backstep_m) < last_along_m:
            continue
        out.append((px, py))
        if along_m > last_along_m:
            last_along_m = along_m

    out.append(points_xy[-1])
    out = _clean_polyline_xy(out, min_dist_km=1e-9)
    return out if len(out) >= 2 else points_xy


def _simplify_polyline_xy(
    points_xy: list[tuple[float, float]],
    angle_tol_deg: float = 2.0,
    min_dist_km: float = 1e-6,
) -> list[tuple[float, float]]:
    points = _clean_polyline_xy(points_xy, min_dist_km=min_dist_km)
    if len(points) < 3:
        return points
    tol_rad = math.radians(float(angle_tol_deg))
    simplified: list[tuple[float, float]] = [points[0]]
    for i in range(1, len(points) - 1):
        ax, ay = simplified[-1]
        bx, by = points[i]
        cx, cy = points[i + 1]
        v1x, v1y = bx - ax, by - ay
        v2x, v2y = cx - bx, cy - by
        l1 = math.hypot(v1x, v1y)
        l2 = math.hypot(v2x, v2y)
        if l1 <= 1e-9 or l2 <= 1e-9:
            continue
        dot = (v1x * v2x + v1y * v2y) / (l1 * l2)
        dot = max(-1.0, min(1.0, dot))
        angle = math.acos(dot)
        if dot > 0 and angle < tol_rad:
            continue
        simplified.append((bx, by))
    simplified.append(points[-1])
    return simplified


# === Turn / offset helpers ===
def _turn_radius_km_for_path(
    speed_mps: float,
    turn_rate_deg_s: float,
    offset_km: float,
) -> float:
    min_r = max(0.001, float(offset_km) * FLIGHT_PATH_MIN_TURN_RADIUS_FACTOR)
    rate = float(turn_rate_deg_s)
    if not math.isfinite(rate) or rate <= 1e-6:
        return min_r
    omega = math.radians(rate)
    v = float(speed_mps)
    if not math.isfinite(v) or v <= 0:
        return min_r
    r_km = (v / omega) / 1000.0
    if not math.isfinite(r_km) or r_km <= 0:
        return min_r
    return max(r_km, min_r)


def _fillet_polyline_xy(
    points_xy: list[tuple[float, float]],
    radius_km: float,
    step_km: float,
    angle_threshold_deg: float = FLIGHT_PATH_FILLET_ANGLE_DEG,
) -> list[tuple[float, float]]:
    points = _clean_polyline_xy(points_xy, min_dist_km=1e-9)
    if radius_km <= 0 or len(points) < 3:
        return points
    step = max(1e-6, float(step_km))
    angle_threshold_rad = math.radians(float(angle_threshold_deg))

    def _append_unique(items: list[tuple[float, float]], x: float, y: float) -> None:
        if items:
            lx, ly = items[-1]
            if math.hypot(x - lx, y - ly) <= 1e-9:
                return
        items.append((x, y))

    result: list[tuple[float, float]] = [points[0]]
    for i in range(1, len(points) - 1):
        ax, ay = points[i - 1]
        bx, by = points[i]
        cx, cy = points[i + 1]

        v1x, v1y = bx - ax, by - ay
        v2x, v2y = cx - bx, cy - by
        len1 = math.hypot(v1x, v1y)
        len2 = math.hypot(v2x, v2y)
        if len1 <= 1e-9 or len2 <= 1e-9:
            _append_unique(result, bx, by)
            continue

        d1x, d1y = v1x / len1, v1y / len1
        d2x, d2y = v2x / len2, v2y / len2

        dot = d1x * d2x + d1y * d2y
        dot = max(-1.0, min(1.0, dot))
        theta = math.acos(dot)

        if theta < angle_threshold_rad or abs(math.pi - theta) < angle_threshold_rad:
            _append_unique(result, bx, by)
            continue

        tan_half = math.tan(theta / 2.0)
        if abs(tan_half) <= 1e-9:
            _append_unique(result, bx, by)
            continue

        t = float(radius_km) * tan_half
        max_t = min(len1, len2) * 0.45
        if t > max_t:
            t = max_t
            radius_eff = t / tan_half
        else:
            radius_eff = float(radius_km)

        if t <= 1e-6 or radius_eff <= 1e-6:
            _append_unique(result, bx, by)
            continue

        p1x, p1y = bx - d1x * t, by - d1y * t
        p2x, p2y = bx + d2x * t, by + d2y * t
        _append_unique(result, p1x, p1y)

        cross = d1x * d2y - d1y * d2x
        if abs(cross) <= 1e-9:
            _append_unique(result, p2x, p2y)
            continue

        turn_left = cross > 0.0
        if turn_left:
            n1x, n1y = -d1y, d1x
            n2x, n2y = -d2y, d2x
        else:
            n1x, n1y = d1y, -d1x
            n2x, n2y = d2y, -d2x

        c1x, c1y = p1x + n1x * radius_eff, p1y + n1y * radius_eff
        c2x, c2y = p2x + n2x * radius_eff, p2y + n2y * radius_eff
        center_x = (c1x + c2x) * 0.5
        center_y = (c1y + c2y) * 0.5

        a1 = math.atan2(p1y - center_y, p1x - center_x)
        a2 = math.atan2(p2y - center_y, p2x - center_x)

        if turn_left:
            if a2 < a1:
                a2 += 2.0 * math.pi
        else:
            if a2 > a1:
                a2 -= 2.0 * math.pi

        sweep = a2 - a1
        arc_len = abs(sweep) * radius_eff
        steps = max(2, int(math.ceil(arc_len / step)))

        for s in range(1, steps):
            ang = a1 + sweep * (s / steps)
            _append_unique(
                result,
                center_x + radius_eff * math.cos(ang),
                center_y + radius_eff * math.sin(ang),
            )

        _append_unique(result, p2x, p2y)

    _append_unique(result, points[-1][0], points[-1][1])
    return result


def _offset_curve_by_normal_xy(points_xy, offset_km, turn_radius_km: float | None = None):
    if offset_km == 0 or len(points_xy) < 2:
        return points_xy

    out = []
    prev_n = None
    prev_t = None

    def _append_unique(x, y):
        if out:
            lx, ly = out[-1]
            if math.hypot(x - lx, y - ly) <= 1e-9:
                return
        out.append((x, y))

    for i, (x, y) in enumerate(points_xy):
        # 1) "거의 180도 유턴" 감지: 인접 두 세그먼트의 방향 내적이 -1에 가까우면
        if 0 < i < len(points_xy) - 1 and abs(offset_km) > 1e-9:
            ax, ay = points_xy[i - 1]
            bx, by = points_xy[i + 1]

            v1x, v1y = x - ax, y - ay          # (i-1)->i
            v2x, v2y = bx - x, by - y          # i->(i+1)

            l1 = math.hypot(v1x, v1y)
            l2 = math.hypot(v2x, v2y)

            if l1 > 1e-9 and l2 > 1e-9:
                d1x, d1y = v1x / l1, v1y / l1
                d2x, d2y = v2x / l2, v2y / l2

                seg_dot = d1x * d2x + d1y * d2y
                if seg_dot <= UTURN_TRIGGER_COS:
                    # 들어오는/나가는 세그먼트 각각의 "우측 노말"
                    n1x, n1y = d1y, -d1x
                    n2x, n2y = d2y, -d2x

                    # 유턴 원호의 시작/끝점(오프셋 적용된 점)
                    start_x = x + n1x * offset_km
                    start_y = y + n1y * offset_km
                    end_x   = x + n2x * offset_km
                    end_y   = y + n2y * offset_km

                    _append_unique(start_x, start_y)

                    r = abs(float(offset_km))  # 기본은 오프셋 반경
                    if (
                        isinstance(turn_radius_km, (int, float))
                        and math.isfinite(turn_radius_km)
                        and turn_radius_km > 0.0
                    ):
                        r = max(r, float(turn_radius_km))
                    if r > 1e-9:
                        a0 = math.atan2(start_y - y, start_x - x)
                        a1 = math.atan2(end_y - y, end_x - x)

                        # offset_km>0(우측 오프셋)이면 CCW가 진행방향 접선이 자연스럽고,
                        # offset_km<0(좌측 오프셋)이면 CW가 자연스럽습니다.
                        delta_ccw = (a1 - a0) % (2.0 * math.pi)
                        sweep = delta_ccw if offset_km > 0 else (delta_ccw - 2.0 * math.pi)

                        arc_len = abs(sweep) * r
                        step = min(float(UTURN_ARC_STEP_KM), max(0.005, r / 12.0))  # r=0.25면 0.02~0.03대
                        steps = max(24, int(math.ceil(arc_len / step)))

                        for s in range(1, steps):
                            ang = a0 + sweep * (s / steps)
                            _append_unique(x + r * math.cos(ang), y + r * math.sin(ang))

                        _append_unique(end_x, end_y)
                    else:
                        _append_unique(end_x, end_y)

                    # 다음 점들 계산이 튀지 않도록 prev 상태 갱신
                    prev_n = (n2x, n2y)
                    prev_t = (d2x, d2y)
                    continue

        # 2) 일반 구간: 기존 방식대로 중앙차분으로 접선 만들고 우측 노말 오프셋
        if i == 0:
            tx = points_xy[1][0] - points_xy[0][0]
            ty = points_xy[1][1] - points_xy[0][1]
        elif i == len(points_xy) - 1:
            tx = points_xy[-1][0] - points_xy[-2][0]
            ty = points_xy[-1][1] - points_xy[-2][1]
        else:
            tx = points_xy[i + 1][0] - points_xy[i - 1][0]
            ty = points_xy[i + 1][1] - points_xy[i - 1][1]

        length = math.hypot(tx, ty)
        if length <= 1e-9:
            if prev_n is None:
                _append_unique(x, y)
                continue
            nx, ny = prev_n
        else:
            tx /= length
            ty /= length
            nx, ny = ty, -tx  # 우측 노말

            # 급격한 노말 반전 방지(유턴 급반전은 위에서 처리)
            if prev_n is not None:
                turn_dot = 1.0
                if prev_t is not None:
                    turn_dot = tx * prev_t[0] + ty * prev_t[1]
                allow_flip = turn_dot <= -0.85
                if not allow_flip and (nx * prev_n[0] + ny * prev_n[1]) < 0.0:
                    nx, ny = -nx, -ny

            prev_n = (nx, ny)
            prev_t = (tx, ty)

        _append_unique(x + nx * offset_km, y + ny * offset_km)

    return out

# === Simulation ===
class Simulation:
    # --- Setup / configuration ---
    def __init__(
        self,
        planner: RoutePlanner,
        rules: SimulationRules,
        get_traffic_selection: Callable[[], str | None],
        update_time: Callable[[int], None] | None = None,
        set_dashboard_data: Callable[[list[list[str]] | None], None] | None = None,
        add_dashboard_row: Callable[[list[str]], None] | None = None,
        update_dashboard_status: Callable[[list[dict[str, object]]], None] | None = None,
        update_speed: Callable[[int], None] | None = None,
        update_map: Callable[[list[dict[str, object]]], None] | None = None,
        add_human_event: Callable[[dict[str, object]], None] | None = None,
        add_failure_event: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.planner = planner
        self.rules = rules
        self.get_traffic_selection = get_traffic_selection
        self.update_time = update_time or (lambda _value: None)
        self.set_dashboard_data = set_dashboard_data or (lambda _rows: None)
        self.add_dashboard_row = add_dashboard_row or (lambda _row: None)
        self.update_dashboard_status = update_dashboard_status or (lambda _rows: None)
        self.update_speed = update_speed or (lambda _value: None)
        self.update_map = update_map or (lambda _rows: None)
        self.add_human_event = add_human_event
        self.add_failure_event = add_failure_event

        self.flights: list[Flight] = []
        self.schedule: list[FlightSchedule] = []
        self.schedule_index = 0
        self.sim_elapsed_s = 0.0
        self.running = False
        self.speed_multiplier = 1
        self.port_names = list(self.planner.ports.keys())
        self.flight_controls: dict[int, FlightControl] = {}
        self.flight_state: dict[int, dict[str, object]] = {}
        self.flight_ops_metrics: dict[int, dict[str, object]] = {}
        self.last_positions_time_s: float | None = None
        self.last_risk_update_s: float | None = None
        self.last_ops_metrics_update_s: float | None = None
        self.pending_schedule: list[FlightSchedule] = []
        self.next_takeoff_by_origin: dict[str, float] = {}
        self.next_available_by_aircraft: dict[str, float] = {}
        self.aircraft_icons: dict[str, str] = {}
        self.flightplan_schedule: list[FlightSchedule] = []
        self.flightplan_name = ""
        self.flightplan_enabled = False
        self.autopilot = replace(DEFAULT_AUTOPILOT)
        self.wind_model = WindModel(
            seed=20260121,
            time_speed=float(self.rules.wind_time_speed),
            preset="good",
            start_local_hour=SIM_START_SECONDS / 3600.0,
        )
        self.sim_duration_s = self._operation_window_s()

        self.update_speed(self.speed_multiplier)
        self.update_time(0)

    def _operation_window_s(self) -> int:
        start_min = int(self.rules.operation_start_min)
        end_min = int(self.rules.operation_end_min)
        start_min = max(0, min(24 * 60, start_min))
        end_min = max(0, min(24 * 60, end_min))
        if end_min >= start_min:
            duration_min = end_min - start_min
        else:
            duration_min = 24 * 60 - start_min + end_min
        return max(0, duration_min) * 60

    def update_rules(self, rules: SimulationRules) -> None:
        self.rules = rules
        self.sim_duration_s = self._operation_window_s()
        if self.wind_model:
            self.wind_model.time_speed = float(self.rules.wind_time_speed)

    def set_wind_preset(self, preset: str) -> None:
        if self.wind_model:
            self.wind_model.set_preset(preset)

    def add_local_wind(self, lon: float, lat: float, radius_m: float, preset: str) -> None:
        if self.wind_model:
            self.wind_model.add_local_zone(lon, lat, radius_m, preset)

    def clear_local_wind(self) -> None:
        if self.wind_model:
            self.wind_model.clear_local_zones()

    def update_planner(self, planner: RoutePlanner) -> None:
        self.planner = planner
        self.port_names = list(self.planner.ports.keys())

    def set_flightplan_schedule(
        self,
        schedule: list[FlightSchedule],
        name: str = "",
    ) -> None:
        normalized = [
            item
            for item in schedule
            if isinstance(item, FlightSchedule)
        ]
        normalized = normalize_flightplan_schedule(normalized)
        self.flightplan_schedule = normalized
        self.flightplan_name = str(name or "").strip()
        self.flightplan_enabled = bool(normalized)

    def clear_flightplan_schedule(self) -> None:
        self.flightplan_schedule = []
        self.flightplan_name = ""
        self.flightplan_enabled = False

    def has_flightplan_schedule(self) -> bool:
        return bool(self.flightplan_enabled and self.flightplan_schedule)

    def get_flightplan_state(self) -> dict[str, object]:
        return build_flightplan_state(
            self.flightplan_schedule,
            self.flightplan_enabled,
            self.flightplan_name,
        )

    # --- Path building ---
    def _build_flight_path(
        self,
        geometry: list[tuple[float, float]],
        path_nodes: list[str],
        speed_mps: float | None = None,
        offset_km: float | None = None,
        densify_km: float | None = None,
    ) -> tuple[list[tuple[float, float]], list[float], list[float], list[int]]:
        """
        경로 생성 로직
        - (1) 원본 경로 단순화 -> (2) 선회반경 기반 필렛(원호) 적용 -> (3) densify -> (4) 접선 기반 우측 오프셋
        - (5) 아주 드물게 생기는 역행 스파이크 제거(앞으로 갔다가 잠깐 뒤로 가는 구간)
        - (6) tail-only 교차 클립(이전 구간 보존)
        """
        projection = self.planner.projection
        center_xy = [projection.to_xy_km(lon, lat) for lon, lat in geometry]
        center_xy = _clean_polyline_xy(center_xy, min_dist_km=1e-6)
        if len(center_xy) < 2:
            return [], [], [0.0], []
        raw_center_xy = list(center_xy)

        node_xy = [
            self.planner.node_xy[name]
            for name in path_nodes
            if name in self.planner.node_xy
        ]
        if len(node_xy) < 2:
            node_xy = center_xy

        center_xy = _simplify_polyline_xy(center_xy, angle_tol_deg=2.0, min_dist_km=1e-6)

        base_speed = speed_mps
        if not isinstance(base_speed, (int, float)) or not math.isfinite(base_speed):
            base_speed = float(self.rules.speed_mps)
        eff_offset_km = offset_km
        if not isinstance(eff_offset_km, (int, float)) or not math.isfinite(eff_offset_km):
            eff_offset_km = float(FLIGHT_PATH_OFFSET_KM)
        eff_offset_km = float(eff_offset_km)
        turn_speed_mps = float(base_speed)
        if math.isfinite(TURN_RADIUS_SPEED_MPS) and TURN_RADIUS_SPEED_MPS > 0.0:
            turn_speed_mps = min(turn_speed_mps, float(TURN_RADIUS_SPEED_MPS))
        turn_radius_km = _turn_radius_km_for_path(
            speed_mps=turn_speed_mps,
            turn_rate_deg_s=float(self.rules.turn_rate_deg_s),
            offset_km=eff_offset_km,
        )

        step_km = FLIGHT_PATH_DENSIFY_KM
        if isinstance(densify_km, (int, float)) and math.isfinite(densify_km) and densify_km > 0:
            step_km = float(densify_km)

        # 추가: 필렛(원호) 샘플링은 더 촘촘하게
        fillet_step_km = min(step_km, 0.05)  # 0.05km = 50m, 필요하면 0.03(30m)도 가능

        smoothed_center = _fillet_polyline_xy(
            center_xy,
            radius_km=turn_radius_km,
            step_km=fillet_step_km,                 # 여기만 변경
            angle_threshold_deg=FLIGHT_PATH_FILLET_ANGLE_DEG,
        )
        densified_center = _densify_points_xy(smoothed_center, step_km)
        if abs(eff_offset_km) <= 1e-9:
            offset_xy = list(densified_center)
        else:
            offset_xy = _offset_curve_by_normal_xy(
                densified_center,
                eff_offset_km,
                turn_radius_km,
            )

        offset_xy = _clean_polyline_xy(offset_xy, min_dist_km=1e-9)

        # 핵심: 드물게 생기는 "다음 점이 뒤로 찍히는" 스파이크 제거
        offset_xy = _remove_backtracking_xy(
            offset_xy,
            reverse_cos=0.0,
            min_seg_km=1e-9,
            max_passes=10,
        )

        uturn_ref = node_xy if len(node_xy) >= 3 else raw_center_xy
        uturn_ref = _clean_polyline_xy(uturn_ref, min_dist_km=1e-9)
        if not _path_has_uturn(uturn_ref):
            offset_xy = _enforce_monotone_along_xy(
                offset_xy,
                densified_center,
                max_backstep_m=50.0,
            )

        offset_xy = _clip_tail_intersections_xy(offset_xy)

        offset_xy = _clean_polyline_xy(offset_xy, min_dist_km=1e-9)
        if len(offset_xy) < 2:
            return [], [], [0.0], []

        segment_map = _segment_index_map_monotone(offset_xy, node_xy)
        points_alt_m = [FLIGHT_ALT_M] * len(offset_xy)
        cum_dist_m = _cumulative_dist_m(offset_xy)
        return offset_xy, points_alt_m, cum_dist_m, segment_map


    # --- Lifecycle / time control ---
    def start(self) -> None:
        if not self.schedule or self.sim_elapsed_s >= self.sim_duration_s:
            self.set_speed(1)
            self._reset_state()
            self.sim_elapsed_s = 0.0
            self.flights = []
            self.schedule = self._generate_schedule()
            self.schedule_index = 0
            self.pending_schedule = []
            self.next_takeoff_by_origin = {}
            self.next_available_by_aircraft = {}
            self.aircraft_icons = {}
            self.flight_controls.clear()
            self.flight_state.clear()
            self.flight_ops_metrics.clear()
            self.last_positions_time_s = None
            self.last_ops_metrics_update_s = None
            self.set_dashboard_data([])
            self.update_time(0)
        if not self.schedule:
            return
        self.running = True
        self._update_positions()

    def pause(self) -> None:
        self.running = False

    def stop(self) -> None:
        self.pause()
        self.sim_elapsed_s = 0.0
        self.flights = []
        self.schedule = []
        self.schedule_index = 0
        self.pending_schedule = []
        self.next_takeoff_by_origin = {}
        self.next_available_by_aircraft = {}
        self.aircraft_icons = {}
        self.flight_controls.clear()
        self.flight_state.clear()
        self.flight_ops_metrics.clear()
        self.set_dashboard_data(None)
        self.update_map([])
        self.update_time(0)
        self.last_positions_time_s = None
        self.last_risk_update_s = None
        self.last_ops_metrics_update_s = None

    def fast(self) -> None:
        try:
            idx = FAST_SPEEDS.index(self.speed_multiplier)
        except ValueError:
            idx = -1
        next_speed = FAST_SPEEDS[(idx + 1) % len(FAST_SPEEDS)]
        self.set_speed(next_speed)

    def set_speed(self, multiplier: int) -> None:
        self.speed_multiplier = max(1, int(multiplier))
        self.update_speed(self.speed_multiplier)

    def step(self, delta_s: float) -> None:
        if not self.running:
            return
        if delta_s <= 0:
            return
        self.sim_elapsed_s += float(delta_s) * self.speed_multiplier
        if self.sim_elapsed_s >= self.sim_duration_s:
            self.sim_elapsed_s = self.sim_duration_s
            self._update_positions()
            self.update_time(int(self.sim_elapsed_s))
            self.running = False
            return
        self._update_positions()
        self.update_time(int(self.sim_elapsed_s))

    # --- Flight lookup / state helpers ---
    def _get_flight(self, flight_id: int) -> Flight | None:
        for flight in self.flights:
            if flight.flight_id == flight_id:
                return flight
        return None

    def get_flight_by_name(self, name: str) -> Flight | None:
        target = name.strip()
        if not target:
            return None
        for flight in self.flights:
            if flight.name == target:
                return flight
        return None

    def _get_control(self, flight_id: int) -> FlightControl:
        control = self.flight_controls.get(flight_id)
        if not control:
            control = FlightControl()
            self.flight_controls[flight_id] = control
        return control

    def _get_profile(self, flight: Flight) -> FlightProfile:
        profile = flight.profile
        if profile is None:
            profile = _build_flight_profile(flight.total_dist_m, flight.speed_mps, self.rules)
            flight.profile = profile
            flight.accel_time_s = profile.accel_time_s
            flight.cruise_time_s = profile.cruise_time_s
            flight.total_time_s = profile.total_time_s
            flight.peak_speed_mps = profile.peak_speed_mps
        return profile

    # --- Speed / holding / emergency controls ---
    def set_flight_speed(self, flight_id: int, speed_mps: float) -> None:
        flight = self._get_flight(flight_id)
        if not flight:
            return
        speed = float(speed_mps)
        if speed <= 0:
            return
        speed = _apply_min_safe_speed(speed, float(self.rules.min_safe_speed_mps))
        control = self._get_control(flight_id)
        control.speed_override_mps = speed
        control.manual_active = True
        state = self.flight_state.get(flight_id)
        dist_m = state.get("dist_m") if state else None
        if isinstance(dist_m, (int, float)):
            control.manual_dist_m = float(dist_m)
        control.manual_arrival_s = None
        control.manual_landing_alt_m = None
        if control.hold_active:
            control.hold_speed_mps = speed

    def clear_flight_speed(self, flight_id: int) -> None:
        control = self.flight_controls.get(flight_id)
        if not control:
            return
        control.speed_override_mps = None
        control.manual_active = True
        control.manual_arrival_s = None
        control.manual_landing_alt_m = None
        if control.hold_active:
            flight = self._get_flight(flight_id)
            control.hold_speed_mps = flight.speed_mps if flight else 0.0

    def _holding_radius_m(self, speed_mps: float) -> float:
        rate_deg = float(self.rules.turn_rate_deg_s)
        if speed_mps <= 0 or rate_deg <= 0:
            return HOLD_RADIUS_M
        omega = math.radians(rate_deg)
        if omega <= 0:
            return HOLD_RADIUS_M
        radius = speed_mps / omega
        if not math.isfinite(radius) or radius <= 0:
            return HOLD_RADIUS_M
        return radius

    def start_holding(self, flight_id: int, loops: int) -> float | None:
        flight = self._get_flight(flight_id)
        if not flight:
            return None
        count = max(1, int(loops))
        state = self.flight_state.get(flight_id)
        if not state or state.get("phase") != MODE_CRUISE:
            return None
        pos_xy = state.get("pos_xy")
        heading = state.get("track_heading_deg", state.get("heading_deg"))
        dist_m = state.get("dist_m")
        alt_m = state.get("alt_m")
        if not isinstance(pos_xy, tuple) or len(pos_xy) != 2:
            return None
        if not isinstance(heading, (int, float)):
            return None
        if not isinstance(dist_m, (int, float)):
            return None
        control = self._get_control(flight_id)
        control.manual_active = True
        if control.manual_dist_m is None:
            control.manual_dist_m = float(dist_m)
        heading_rad = math.radians(float(heading))
        right_vec = (math.cos(heading_rad), -math.sin(heading_rad))
        base_speed = float(state.get("speed_mps") or 0.0)
        speed = control.speed_override_mps or base_speed or flight.peak_speed_mps
        speed = _apply_min_safe_speed(float(speed), float(self.rules.min_safe_speed_mps))
        radius_m = self._holding_radius_m(speed)
        radius_km = radius_m / 1000.0
        center = (
            pos_xy[0] + right_vec[0] * radius_km,
            pos_xy[1] + right_vec[1] * radius_km,
        )
        start_angle = math.atan2(pos_xy[1] - center[1], pos_xy[0] - center[0])
        control.hold_active = True
        control.hold_loops_total = count
        control.hold_start_time_s = self.sim_elapsed_s
        control.hold_start_dist_m = float(dist_m)
        control.hold_center_xy = center
        control.hold_start_angle_rad = start_angle
        control.hold_speed_mps = float(speed)
        control.hold_alt_m = float(alt_m) if isinstance(alt_m, (int, float)) else FLIGHT_ALT_M
        control.hold_radius_m = float(radius_m)
        return radius_m

    def stop_holding(self, flight_id: int) -> None:
        control = self.flight_controls.get(flight_id)
        if not control:
            return
        if not control.hold_active or not control.hold_center_xy:
            control.hold_active = False
            control.hold_loops_total = 0
            control.hold_start_time_s = 0.0
            control.hold_center_xy = None
            control.hold_start_angle_rad = 0.0
            control.hold_speed_mps = 0.0
            return
        radius_m = control.hold_radius_m if control.hold_radius_m > 0 else HOLD_RADIUS_M
        loop_length = 2.0 * math.pi * radius_m
        if loop_length <= 0 or control.hold_speed_mps <= 0:
            control.hold_active = False
            control.hold_loops_total = 0
            control.hold_start_time_s = 0.0
            control.hold_center_xy = None
            control.hold_start_angle_rad = 0.0
            control.hold_speed_mps = 0.0
            return
        hold_elapsed = max(0.0, self.sim_elapsed_s - control.hold_start_time_s)
        loops_done = hold_elapsed * control.hold_speed_mps / loop_length
        target_loops = max(1, int(math.ceil(loops_done - 1e-6)))
        if control.hold_loops_total <= 0:
            control.hold_loops_total = target_loops
        else:
            control.hold_loops_total = min(control.hold_loops_total, target_loops)

    def set_emergency_landing(
        self,
        flight_id: int,
        lon: float,
        lat: float,
        label: str = "",
        alt_m: float | None = None,
    ) -> bool:
        flight = self._get_flight(flight_id)
        if not flight:
            return False
        if not math.isfinite(lon) or not math.isfinite(lat):
            return False
        state = self.flight_state.get(flight_id)
        start_label = None
        dist_m = state.get("dist_m") if state else None
        segment = None
        if flight.path_nodes and flight.cum_dist_m and isinstance(dist_m, (int, float)):
            segment = self._route_segment_for_distance(
                flight.path_nodes,
                flight.cum_dist_m,
                float(dist_m),
                flight.path_segment_idx,
            )
        if segment:
            start_label = segment[0]
        if not start_label:
            start_label = flight.origin
        pos_xy = state.get("pos_xy") if state else None
        if not isinstance(pos_xy, tuple) or len(pos_xy) != 2:
            pos_xy = flight.points_xy[0] if flight.points_xy else None
        target_xy = self.planner.projection.to_xy_km(lon, lat)
        if not pos_xy:
            pos_xy = target_xy
        alt_start = state.get("alt_m") if state else None
        if not isinstance(alt_start, (int, float)) or not math.isfinite(alt_start):
            alt_start = FLIGHT_ALT_M
        alt_target = float(alt_m) if alt_m is not None else VERTIPORT_ALT_M
        if not math.isfinite(alt_target):
            alt_target = VERTIPORT_ALT_M
        control = self._get_control(flight_id)
        speed_base = state.get("speed_mps") if state else None
        speed = control.speed_override_mps or speed_base or flight.speed_mps
        if not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed <= 0:
            speed = flight.speed_mps

        heading_deg = state.get("track_heading_deg", state.get("heading_deg")) if state else None
        if not isinstance(heading_deg, (int, float)) or not math.isfinite(heading_deg):
            if flight.points_xy and flight.cum_dist_m and isinstance(dist_m, (int, float)):
                heading_deg = _heading_at_distance(
                    flight.points_xy,
                    flight.cum_dist_m,
                    float(dist_m),
                )
        heading_vec = None
        if isinstance(heading_deg, (int, float)) and math.isfinite(heading_deg):
            heading_vec = _heading_vector(float(heading_deg))

        geometry_xy = [tuple(pos_xy), tuple(target_xy)]
        dist_km = math.hypot(target_xy[0] - pos_xy[0], target_xy[1] - pos_xy[1])
        if heading_vec and dist_km > 1e-6:
            turn_radius_km = _turn_radius_km_for_path(
                speed_mps=float(speed),
                turn_rate_deg_s=float(self.rules.turn_rate_deg_s),
                offset_km=float(FLIGHT_PATH_OFFSET_KM),
            )
            lead_km = max(0.1, turn_radius_km * 0.8)
            lead_km = min(lead_km, dist_km * 0.7)
            if lead_km > 1e-6:
                lead_xy = (
                    pos_xy[0] + heading_vec[0] * lead_km,
                    pos_xy[1] + heading_vec[1] * lead_km,
                )
                geometry_xy = [tuple(pos_xy), lead_xy, tuple(target_xy)]

        projection = self.planner.projection
        geometry = [projection.to_lonlat(x, y) for x, y in geometry_xy]
        target_label = str(label or "").strip() or "Emergency"
        points_xy, points_alt_m, cum_dist_m, segment_map = self._build_flight_path(
            geometry,
            [start_label, target_label],
            speed_mps=float(speed),
            offset_km=0.0,
            densify_km=EMERGENCY_PATH_DENSIFY_KM,
        )
        if len(points_xy) < 2 or not cum_dist_m:
            points_xy = [tuple(pos_xy), tuple(target_xy)]
            cum_dist_m = _cumulative_dist_m(points_xy)
            segment_map = [0 for _ in points_xy]
        total_dist_m = float(cum_dist_m[-1]) if cum_dist_m else 0.0
        if total_dist_m > 0:
            alt_span = float(alt_target) - float(alt_start)
            points_alt_m = [
                float(alt_start) + alt_span * (dist / total_dist_m) for dist in cum_dist_m
            ]
        else:
            points_alt_m = [float(alt_target) for _ in points_xy]

        profile = _build_flight_profile(total_dist_m, float(speed), self.rules)
        flight.points_xy = points_xy
        flight.points_alt_m = points_alt_m
        flight.cum_dist_m = cum_dist_m
        flight.total_dist_m = total_dist_m
        flight.accel_time_s = profile.accel_time_s
        flight.cruise_time_s = profile.cruise_time_s
        flight.total_time_s = profile.total_time_s
        flight.peak_speed_mps = profile.peak_speed_mps
        flight.profile = profile
        flight.destination = target_label
        flight.path_nodes = [start_label, target_label]
        flight.path_segment_idx = segment_map
        control.manual_active = True
        control.emergency_active = True
        control.manual_dist_m = 0.0
        control.manual_arrival_s = None
        control.manual_landing_alt_m = None
        if control.hold_active:
            control.hold_active = False
            control.hold_loops_total = 0
            control.hold_start_time_s = 0.0
            control.hold_start_dist_m = 0.0
            control.hold_center_xy = None
            control.hold_start_angle_rad = 0.0
            control.hold_speed_mps = 0.0
        return True

    def force_move_via(self, flight_id: int, waypoint: str) -> bool:
        flight = self._get_flight(flight_id)
        if not flight:
            return False
        wp_name = str(waypoint or "").strip()
        if not wp_name or wp_name not in self.planner.node_xy:
            return False
        state = self.flight_state.get(flight_id) or {}
        pos_xy = state.get("pos_xy")
        if not isinstance(pos_xy, tuple) or len(pos_xy) != 2:
            pos_xy = None
        if pos_xy is None:
            dist_m = state.get("dist_m")
            if (
                flight.points_xy
                and flight.cum_dist_m
                and isinstance(dist_m, (int, float))
                and math.isfinite(dist_m)
            ):
                pos_xy = _position_at_distance(
                    flight.points_xy,
                    flight.cum_dist_m,
                    float(dist_m),
                )
            elif flight.points_xy:
                pos_xy = flight.points_xy[0]
        if not isinstance(pos_xy, tuple) or len(pos_xy) != 2:
            return False

        wp_xy = self.planner.node_xy.get(wp_name)
        if not isinstance(wp_xy, tuple) or len(wp_xy) != 2:
            return False

        speed_mps = state.get("speed_base_mps", state.get("speed_mps"))
        if (
            not isinstance(speed_mps, (int, float))
            or not math.isfinite(speed_mps)
            or speed_mps <= 0.0
        ):
            speed_mps = flight.speed_mps

        heading_deg = state.get("track_heading_deg", state.get("heading_deg")) if state else None
        heading_vec = (
            _heading_vector(float(heading_deg))
            if isinstance(heading_deg, (int, float)) and math.isfinite(heading_deg)
            else None
        )

        geometry_xy = [tuple(pos_xy), tuple(wp_xy)]
        dist_km = math.hypot(wp_xy[0] - pos_xy[0], wp_xy[1] - pos_xy[1])
        if heading_vec and dist_km > 1e-6:
            turn_radius_km = _turn_radius_km_for_path(
                speed_mps=float(speed_mps),
                turn_rate_deg_s=float(self.rules.turn_rate_deg_s),
                offset_km=0.0,
            )
            lead_km = max(0.1, turn_radius_km * 0.8)
            lead_km = min(lead_km, dist_km * 0.7)
            if lead_km > 1e-6:
                lead_xy = (
                    pos_xy[0] + heading_vec[0] * lead_km,
                    pos_xy[1] + heading_vec[1] * lead_km,
                )
                geometry_xy = [tuple(pos_xy), lead_xy, tuple(wp_xy)]

        try:
            result = self.planner.find_route(wp_name, flight.destination)
        except Exception:
            self._enter_no_route_hold(flight, state)
            return False
        route_geometry = list(result.points)
        if not route_geometry:
            self._enter_no_route_hold(flight, state)
            return False

        projection = self.planner.projection
        wp_lon, wp_lat = projection.to_lonlat(float(wp_xy[0]), float(wp_xy[1]))
        if route_geometry and route_geometry[0] != (wp_lon, wp_lat):
            route_geometry.insert(0, (wp_lon, wp_lat))

        geometry = [projection.to_lonlat(x, y) for x, y in geometry_xy]
        if geometry and route_geometry:
            if route_geometry[0] == geometry[-1]:
                geometry.extend(route_geometry[1:])
            else:
                geometry.extend(route_geometry)

        points_xy, points_alt_m, cum_dist_m, segment_map = self._build_flight_path(
            geometry,
            list(result.path),
            speed_mps=float(speed_mps),
            offset_km=0.0,
            densify_km=EMERGENCY_PATH_DENSIFY_KM,
        )
        if len(points_xy) < 2 or not cum_dist_m:
            self._enter_no_route_hold(flight, state)
            return False
        total_dist_m = float(cum_dist_m[-1])
        if total_dist_m <= 0:
            self._enter_no_route_hold(flight, state)
            return False

        if (
            isinstance(speed_mps, (int, float))
            and math.isfinite(speed_mps)
            and speed_mps > 0.0
        ):
            flight.speed_mps = float(speed_mps)
        flight.points_xy = points_xy
        flight.points_alt_m = points_alt_m
        flight.cum_dist_m = cum_dist_m
        flight.total_dist_m = total_dist_m
        flight.path_nodes = list(result.path)
        flight.path_segment_idx = segment_map
        profile = _build_flight_profile(total_dist_m, flight.speed_mps, self.rules)
        flight.accel_time_s = profile.accel_time_s
        flight.cruise_time_s = profile.cruise_time_s
        flight.total_time_s = profile.total_time_s
        flight.peak_speed_mps = profile.peak_speed_mps
        flight.profile = profile

        control = self._get_control(flight.flight_id)
        if control.hold_active:
            control.hold_active = False
            control.hold_loops_total = 0
            control.hold_start_time_s = 0.0
            control.hold_start_dist_m = 0.0
            control.hold_center_xy = None
            control.hold_start_angle_rad = 0.0
            control.hold_speed_mps = 0.0
        control.manual_active = True
        control.manual_dist_m = 0.0
        control.manual_arrival_s = None
        control.manual_landing_alt_m = None
        self._clear_no_route_hold(flight.flight_id)
        return True

    def set_wind_hold(self, flight_id: int, target_scale: float, ramp_s: float) -> None:
        flight = self._get_flight(flight_id)
        if not flight:
            return
        control = self._get_control(flight_id)
        current = control.wind_effect_scale
        if not isinstance(current, (int, float)) or not math.isfinite(current):
            current = 1.0
        target = float(target_scale)
        if not math.isfinite(target):
            return
        target = max(0.0, min(0.5, target))
        ramp = float(ramp_s)
        if not math.isfinite(ramp):
            ramp = 0.0
        ramp = max(0.0, ramp)
        control.wind_effect_start_scale = float(current)
        control.wind_effect_target_scale = float(target)
        control.wind_effect_start_s = float(self.sim_elapsed_s)
        control.wind_effect_ramp_s = float(ramp)

    def set_autopilot(
        self,
        enabled: bool,
        duration_s: float | None = None,
        lv1_delta_knot: float | None = None,
        lv2_delta_knot: float | None = None,
        lv3_delta_knot: float | None = None,
    ) -> None:
        current = self.autopilot

        def _read(value: float | None, fallback: float) -> float:
            if value is None:
                return float(fallback)
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                return float(fallback)
            return parsed if math.isfinite(parsed) else float(fallback)

        duration_value = max(0.0, _read(duration_s, current.duration_s))
        lv1_value = max(0.0, _read(lv1_delta_knot, current.lv1_delta_knot))
        lv2_value = max(0.0, _read(lv2_delta_knot, current.lv2_delta_knot))
        lv3_value = max(0.0, _read(lv3_delta_knot, current.lv3_delta_knot))

        self.autopilot = AutopilotSettings(
            enabled=bool(enabled),
            duration_s=duration_value,
            lv1_delta_knot=lv1_value,
            lv2_delta_knot=lv2_value,
            lv3_delta_knot=lv3_value,
        )

        if not self.autopilot.enabled:
            for control in self.flight_controls.values():
                self._clear_autopilot_state(control)

    def _clear_autopilot_state(self, control: FlightControl) -> None:
        control.autopilot_active = False
        control.autopilot_level = 0
        control.autopilot_start_s = 0.0
        control.autopilot_duration_s = 0.0
        control.autopilot_delta_mps = 0.0
        control.autopilot_base_speed_mps = 0.0

    def _autopilot_delta_for_level(self, level: int) -> float:
        if level >= 3:
            delta_knot = self.autopilot.lv3_delta_knot
        elif level == 2:
            delta_knot = self.autopilot.lv2_delta_knot
        elif level == 1:
            delta_knot = self.autopilot.lv1_delta_knot
        else:
            delta_knot = 0.0
        delta_knot = max(0.0, float(delta_knot))
        return float(delta_knot) * KNOT_TO_MPS

    def _start_autopilot(
        self,
        flight: Flight,
        control: FlightControl,
        level: int,
        base_speed_hint_mps: float | None = None,
    ) -> None:
        delta_mps = self._autopilot_delta_for_level(level)
        if delta_mps <= 0.0:
            self._clear_autopilot_state(control)
            return

        base_speed = None
        if isinstance(base_speed_hint_mps, (int, float)) and math.isfinite(base_speed_hint_mps):
            base_speed = float(base_speed_hint_mps)
        elif isinstance(control.speed_override_mps, (int, float)) and math.isfinite(
            control.speed_override_mps
        ):
            base_speed = float(control.speed_override_mps)
        else:
            base_speed = float(flight.speed_mps)

        if not math.isfinite(base_speed) or base_speed <= 0.0:
            self._clear_autopilot_state(control)
            return

        max_reduction = max(0.0, float(base_speed) - float(self.rules.min_safe_speed_mps))
        delta_mps = min(float(delta_mps), max_reduction)
        if delta_mps <= 0.0:
            self._clear_autopilot_state(control)
            return
        control.autopilot_active = True
        control.autopilot_level = int(level)
        control.autopilot_start_s = float(self.sim_elapsed_s)
        control.autopilot_duration_s = max(0.0, float(self.autopilot.duration_s))
        control.autopilot_delta_mps = float(delta_mps)
        control.autopilot_base_speed_mps = float(base_speed)

        target_speed = max(float(self.rules.min_safe_speed_mps), float(base_speed) - float(delta_mps))
        if self.add_human_event:
            delta_knot = delta_mps / KNOT_TO_MPS if KNOT_TO_MPS > 0 else 0.0
            self.add_human_event(
                {
                    "kind": "speed",
                    "flight_id": flight.flight_id,
                    "flight_name": flight.name,
                    "action": f"Auto LV{int(level)} (-{delta_knot:.0f}kt)",
                    "speed_mps": target_speed,
                }
            )

    def _autopilot_scale(self, control: FlightControl) -> float:
        if not control.autopilot_active:
            return 1.0
        base_speed = float(control.autopilot_base_speed_mps)
        delta_mps = float(control.autopilot_delta_mps)
        if not math.isfinite(base_speed) or base_speed <= 0.0:
            return 1.0
        if base_speed <= float(self.rules.min_safe_speed_mps):
            return 1.0
        if not math.isfinite(delta_mps) or delta_mps <= 0.0:
            return 1.0
        delta_mps = max(0.0, min(delta_mps, base_speed))
        target_speed = max(float(self.rules.min_safe_speed_mps), base_speed - delta_mps)
        target_scale = target_speed / base_speed if base_speed > 0.0 else 1.0
        duration = float(control.autopilot_duration_s)
        if not math.isfinite(duration) or duration <= 0.0:
            return max(0.0, min(1.0, float(target_scale)))
        elapsed = max(0.0, float(self.sim_elapsed_s) - float(control.autopilot_start_s))
        if elapsed >= duration:
            return 1.0
        phase = max(0.0, min(1.0, elapsed / duration))
        ease = 0.5 - 0.5 * math.cos(2.0 * math.pi * phase)
        diff = 1.0 - float(target_scale)
        scale = 1.0 - diff * ease
        return max(0.0, min(1.0, float(scale)))

    def _sync_autopilot_state(
        self,
        flight: Flight,
        control: FlightControl,
        risk_level: int,
        prev_state: dict[str, object] | None,
        phase: str,
        base_speed_hint_mps: float | None = None,
    ) -> float:
        if not self.autopilot.enabled:
            if control.autopilot_active:
                self._clear_autopilot_state(control)
            return 1.0

        desired_level = int(risk_level) if isinstance(risk_level, int) else int(risk_level or 0)
        desired_level = max(0, min(3, desired_level))
        now_s = float(self.sim_elapsed_s)

        if control.autopilot_active:
            if desired_level > control.autopilot_level:
                self._start_autopilot(flight, control, desired_level, base_speed_hint_mps)
            else:
                duration = float(control.autopilot_duration_s)
                if not math.isfinite(duration) or duration <= 0.0:
                    duration = max(0.0, float(self.autopilot.duration_s))
                    control.autopilot_duration_s = duration
                elapsed = now_s - float(control.autopilot_start_s)
                if elapsed >= duration:
                    if desired_level > 0:
                        control.autopilot_start_s = now_s
                    else:
                        self._clear_autopilot_state(control)
        elif desired_level > 0:
            self._start_autopilot(flight, control, desired_level, base_speed_hint_mps)

        if control.autopilot_active and phase in (MODE_CRUISE, MODE_LANDING):
            if not control.manual_active:
                control.manual_active = True
            if control.manual_dist_m is None and prev_state:
                dist_m = prev_state.get("dist_m")
                if isinstance(dist_m, (int, float)) and math.isfinite(dist_m):
                    control.manual_dist_m = float(dist_m)

        if not control.autopilot_active or phase not in (MODE_CRUISE, MODE_LANDING):
            return 1.0
        return self._autopilot_scale(control)

    def _clear_no_route_hold(self, flight_id: int) -> None:
        control = self.flight_controls.get(flight_id)
        if not control or not control.no_route_active:
            return
        control.no_route_active = False
        control.no_route_reason = ""
        if control.hold_active:
            control.hold_active = False
            control.hold_loops_total = 0
            control.hold_start_time_s = 0.0
            control.hold_start_dist_m = 0.0
            control.hold_center_xy = None
            control.hold_start_angle_rad = 0.0
            control.hold_speed_mps = 0.0
            control.hold_alt_m = FLIGHT_ALT_M
            control.hold_radius_m = HOLD_RADIUS_M

    def _enter_no_route_hold(self, flight: Flight, state: dict[str, object] | None) -> None:
        control = self._get_control(flight.flight_id)
        if control.no_route_active and control.hold_active and control.hold_center_xy:
            return
        pos_xy = state.get("pos_xy") if state else None
        if not isinstance(pos_xy, tuple) or len(pos_xy) != 2:
            pos_xy = flight.points_xy[0] if flight.points_xy else None
        if not isinstance(pos_xy, tuple) or len(pos_xy) != 2:
            return
        heading_deg = state.get("track_heading_deg", state.get("heading_deg")) if state else 0.0
        if not isinstance(heading_deg, (int, float)) or not math.isfinite(heading_deg):
            heading_deg = 0.0
        speed_mps = state.get("speed_mps") if state else None
        if not isinstance(speed_mps, (int, float)) or not math.isfinite(speed_mps) or speed_mps <= 0:
            speed_mps = flight.speed_mps
        if not isinstance(speed_mps, (int, float)) or not math.isfinite(speed_mps) or speed_mps <= 0:
            speed_mps = float(TURN_RADIUS_SPEED_MPS)
        if math.isfinite(TURN_RADIUS_SPEED_MPS) and TURN_RADIUS_SPEED_MPS > 0.0:
            speed_mps = min(float(speed_mps), float(TURN_RADIUS_SPEED_MPS))
        speed_mps = _apply_min_safe_speed(float(speed_mps), float(self.rules.min_safe_speed_mps))
        radius_m = self._holding_radius_m(float(speed_mps))
        radius_km = radius_m / 1000.0
        heading_rad = math.radians(float(heading_deg))
        right_vec = (math.cos(heading_rad), -math.sin(heading_rad))
        center = (
            pos_xy[0] + right_vec[0] * radius_km,
            pos_xy[1] + right_vec[1] * radius_km,
        )
        start_angle = math.atan2(pos_xy[1] - center[1], pos_xy[0] - center[0])
        alt_m = state.get("alt_m") if state else None
        if not isinstance(alt_m, (int, float)) or not math.isfinite(alt_m):
            alt_m = FLIGHT_ALT_M
        dist_m = state.get("dist_m") if state else None
        if not isinstance(dist_m, (int, float)) or not math.isfinite(dist_m):
            dist_m = 0.0

        control.manual_active = True
        control.no_route_active = True
        control.no_route_reason = "경로 없음"
        control.hold_active = True
        control.hold_loops_total = 1000000
        control.hold_start_time_s = self.sim_elapsed_s
        control.hold_start_dist_m = float(dist_m)
        control.hold_center_xy = center
        control.hold_start_angle_rad = float(start_angle)
        control.hold_speed_mps = float(speed_mps)
        control.hold_alt_m = float(alt_m)
        control.hold_radius_m = float(radius_m)
        control.manual_dist_m = float(dist_m)
        control.manual_arrival_s = None
        control.manual_landing_alt_m = None

    # --- Replanning / routing ---
    def set_corridor_closed(self, start: str, end: str, closed: bool) -> bool:
        if not start or not end:
            return False
        changed = self.planner.set_edge_closed(start, end, closed)
        if changed:
            if closed:
                self._replan_flights_for_edge(start, end)
            else:
                self._replan_flights_for_edge_open(start, end)
        return changed

    def set_spare_corridor_open(self, start: str, end: str, open: bool) -> bool:
        if not start or not end:
            return False
        changed = self.planner.set_spare_edge_open(start, end, open)
        if changed:
            if open:
                self._replan_flights_for_edge_open(start, end)
            else:
                self._replan_flights_for_edge(start, end)
        return changed

    def _replan_active_flights(self) -> None:
        for flight in list(self.flights):
            state = self.flight_state.get(flight.flight_id)
            control = self.flight_controls.get(flight.flight_id)
            if control and control.hold_active and not control.no_route_active:
                continue
            phase = state.get("phase") if state else None
            takeoff_replan = phase == MODE_TAKEOFF or (control and control.no_route_active)
            if phase == MODE_CRUISE or takeoff_replan:
                dist_m = state.get("dist_m")
                if not isinstance(dist_m, (int, float)):
                    continue
                if not flight.path_nodes or not flight.cum_dist_m:
                    continue
                idx = self._path_index_for_distance(flight.cum_dist_m, float(dist_m))
                if idx is None:
                    continue
                ok = self._replan_flight_from_state(flight, state, idx)
                if not ok and takeoff_replan:
                    self._enter_no_route_hold(flight, state)
                continue
            if phase == MODE_WAITING or state is None:
                if self._replan_flight_from_origin(flight):
                    if control and control.manual_active:
                        control.manual_dist_m = 0.0
                        control.manual_arrival_s = None
                        control.manual_landing_alt_m = None

    def _replan_flights_for_edge(self, start: str, end: str) -> None:
        key = tuple(sorted((start, end)))
        for flight in list(self.flights):
            state = self.flight_state.get(flight.flight_id)
            control = self.flight_controls.get(flight.flight_id)
            if control and control.hold_active and not control.no_route_active:
                continue
            phase = state.get("phase") if state else None
            takeoff_replan = phase == MODE_TAKEOFF or (control and control.no_route_active)
            if phase == MODE_CRUISE or takeoff_replan:
                dist_m = state.get("dist_m")
                if not isinstance(dist_m, (int, float)):
                    continue
                if not flight.path_nodes or not flight.cum_dist_m:
                    continue
                idx = self._path_index_for_distance(flight.cum_dist_m, float(dist_m))
                if idx is None:
                    continue
                if not self._path_contains_edge(
                    flight.path_nodes,
                    idx,
                    key,
                    flight.path_segment_idx,
                ):
                    continue
                ok = self._replan_flight_from_state(flight, state, idx)
                if not ok and takeoff_replan:
                    self._enter_no_route_hold(flight, state)
                continue
            if phase == MODE_WAITING or state is None:
                if not flight.path_nodes:
                    continue
                if not self._path_contains_edge(
                    flight.path_nodes,
                    0,
                    key,
                    flight.path_segment_idx,
                ):
                    continue
                if self._replan_flight_from_origin(flight):
                    if control and control.manual_active:
                        control.manual_dist_m = 0.0
                        control.manual_arrival_s = None
                        control.manual_landing_alt_m = None
                continue

    def _replan_flights_for_edge_open(self, start: str, end: str) -> None:
        key = tuple(sorted((start, end)))
        for flight in list(self.flights):
            state = self.flight_state.get(flight.flight_id)
            control = self.flight_controls.get(flight.flight_id)
            if control and control.hold_active and not control.no_route_active:
                continue
            phase = state.get("phase") if state else None
            takeoff_replan = phase == MODE_TAKEOFF or (control and control.no_route_active)
            if phase == MODE_CRUISE or takeoff_replan:
                dist_m = state.get("dist_m")
                if not isinstance(dist_m, (int, float)):
                    continue
                if not flight.path_nodes or not flight.cum_dist_m:
                    continue
                idx = self._path_index_for_distance(flight.cum_dist_m, float(dist_m))
                if idx is None:
                    continue
                seg_idx = idx
                if flight.path_segment_idx and idx < len(flight.path_segment_idx):
                    seg_idx = flight.path_segment_idx[idx]
                seg_idx = max(0, min(seg_idx, len(flight.path_nodes) - 2))
                prev_node = flight.path_nodes[seg_idx]
                next_node = flight.path_nodes[seg_idx + 1]
                start_node = next_node
                heading_deg = state.get("track_heading_deg", state.get("heading_deg"))
                heading_vec = (
                    _heading_vector(float(heading_deg))
                    if isinstance(heading_deg, (int, float)) and math.isfinite(heading_deg)
                    else None
                )
                prev_xy = self.planner.node_xy.get(prev_node)
                next_xy = self.planner.node_xy.get(next_node)
                if heading_vec and prev_xy and next_xy:
                    seg_vec = (next_xy[0] - prev_xy[0], next_xy[1] - prev_xy[1])
                    seg_len = math.hypot(seg_vec[0], seg_vec[1])
                    if seg_len > 1e-9:
                        seg_dir = (seg_vec[0] / seg_len, seg_vec[1] / seg_len)
                        if heading_vec[0] * seg_dir[0] + heading_vec[1] * seg_dir[1] < 0.0:
                            start_node = prev_node
                try:
                    result = self.planner.find_route(start_node, flight.destination)
                except Exception:
                    continue
                if not self._path_contains_edge(list(result.path), 0, key, None):
                    continue
                ok = self._replan_flight_from_state(
                    flight,
                    state,
                    idx,
                    allow_snap=False,
                    allow_manual_snap=False,
                )
                if not ok and takeoff_replan:
                    self._enter_no_route_hold(flight, state)
                continue
            if phase == MODE_WAITING or state is None:
                try:
                    result = self.planner.find_route(flight.origin, flight.destination)
                except Exception:
                    continue
                if not self._path_contains_edge(list(result.path), 0, key, None):
                    continue
                if self._replan_flight_from_origin(flight):
                    if control and control.manual_active:
                        control.manual_dist_m = 0.0
                        control.manual_arrival_s = None
                        control.manual_landing_alt_m = None

    def _path_index_for_distance(self, cum_dist_m: list[float], dist_m: float) -> int | None:
        if not cum_dist_m:
            return None
        if dist_m <= 0:
            return 0
        if dist_m >= cum_dist_m[-1]:
            return len(cum_dist_m) - 1
        return bisect.bisect_left(cum_dist_m, dist_m)

    def _route_segment_for_distance(
        self,
        path_nodes: list[str],
        cum_dist_m: list[float],
        dist_m: float,
        segment_map: list[int] | None = None,
    ) -> tuple[str, str] | None:
        if len(path_nodes) < 2:
            return None
        idx = self._path_index_for_distance(cum_dist_m, dist_m)
        if idx is None:
            return None
        seg_idx = idx
        if segment_map and idx < len(segment_map):
            seg_idx = segment_map[idx]
        seg_idx = max(0, min(seg_idx, len(path_nodes) - 2))
        start_idx = seg_idx
        end_idx = seg_idx + 1
        return path_nodes[start_idx], path_nodes[end_idx]

    def _path_contains_edge(
        self,
        path_nodes: list[str],
        idx: int,
        key: tuple[str, str],
        segment_map: list[int] | None = None,
    ) -> bool:
        if len(path_nodes) < 2:
            return False
        seg_idx = idx
        if segment_map and idx < len(segment_map):
            seg_idx = segment_map[idx]
        start_idx = max(0, min(seg_idx, len(path_nodes) - 2))
        for i in range(start_idx, len(path_nodes) - 1):
            edge_key = tuple(sorted((path_nodes[i], path_nodes[i + 1])))
            if edge_key == key:
                return True
        return False

    def _replan_flight_from_state(
        self,
        flight: Flight,
        state: dict[str, object],
        idx: int,
        allow_snap: bool = True,
        allow_manual_snap: bool = True,
    ) -> bool:
        seg_idx = idx
        if flight.path_segment_idx and idx < len(flight.path_segment_idx):
            seg_idx = flight.path_segment_idx[idx]
        if len(flight.path_nodes) < 2:
            return False
        seg_idx = max(0, min(seg_idx, len(flight.path_nodes) - 2))
        pos_xy = state.get("pos_xy")
        if not isinstance(pos_xy, tuple) or len(pos_xy) != 2:
            return False
        prev_node = flight.path_nodes[seg_idx]
        next_node = flight.path_nodes[seg_idx + 1]
        heading_deg = state.get("track_heading_deg", state.get("heading_deg"))
        heading_vec = (
            _heading_vector(float(heading_deg))
            if isinstance(heading_deg, (int, float)) and math.isfinite(heading_deg)
            else None
        )
        start_node = next_node
        if self.planner.is_edge_closed(prev_node, next_node):
            prev_xy = self.planner.node_xy.get(prev_node)
            next_xy = self.planner.node_xy.get(next_node)
            if prev_xy and next_xy:
                dist_prev = math.hypot(pos_xy[0] - prev_xy[0], pos_xy[1] - prev_xy[1])
                dist_next = math.hypot(pos_xy[0] - next_xy[0], pos_xy[1] - next_xy[1])
                start_node = prev_node if dist_prev <= dist_next else next_node
        else:
            prev_xy = self.planner.node_xy.get(prev_node)
            next_xy = self.planner.node_xy.get(next_node)
            if heading_vec and prev_xy and next_xy:
                seg_vec = (next_xy[0] - prev_xy[0], next_xy[1] - prev_xy[1])
                seg_len = math.hypot(seg_vec[0], seg_vec[1])
                if seg_len > 1e-9:
                    seg_dir = (seg_vec[0] / seg_len, seg_vec[1] / seg_len)
                    if heading_vec[0] * seg_dir[0] + heading_vec[1] * seg_dir[1] < 0.0:
                        start_node = prev_node

        try:
            result = self.planner.find_route(start_node, flight.destination)
        except Exception:
            return False
        geometry = list(result.points)
        if len(geometry) < 2:
            return False
        projection = self.planner.projection
        geom_xy = [projection.to_xy_km(float(lon), float(lat)) for lon, lat in geometry]

        def _closest_point_and_dir(
            point_xy: tuple[float, float],
            line_xy: list[tuple[float, float]],
        ) -> tuple[tuple[float, float], tuple[float, float], int, float, float, float] | None:
            best_dist = math.inf
            best_point = None
            best_dir = None
            best_idx = 0
            best_t = 0.0
            best_along_km = 0.0
            along_km = 0.0
            px, py = point_xy
            for idx, ((ax, ay), (bx, by)) in enumerate(zip(line_xy, line_xy[1:])):
                dx = bx - ax
                dy = by - ay
                seg_len2 = dx * dx + dy * dy
                if seg_len2 <= 1e-12:
                    continue
                seg_len = math.sqrt(seg_len2)
                t = ((px - ax) * dx + (py - ay) * dy) / seg_len2
                t = max(0.0, min(1.0, t))
                proj_x = ax + dx * t
                proj_y = ay + dy * t
                dist = math.hypot(px - proj_x, py - proj_y)
                if dist < best_dist:
                    best_dist = dist
                    best_point = (proj_x, proj_y)
                    best_dir = (dx, dy)
                    best_idx = idx
                    best_t = t
                    best_along_km = along_km + seg_len * t
                along_km += seg_len
            if best_point is None or best_dir is None:
                return None
            return best_point, best_dir, best_idx, best_t, best_along_km, best_dist

        speed_src = state.get("speed_base_mps", state.get("speed_mps"))
        if not isinstance(speed_src, (int, float)) or not math.isfinite(speed_src):
            speed_src = flight.speed_mps
        turn_speed_mps = float(speed_src)
        if math.isfinite(TURN_RADIUS_SPEED_MPS) and TURN_RADIUS_SPEED_MPS > 0.0:
            turn_speed_mps = min(turn_speed_mps, float(TURN_RADIUS_SPEED_MPS))
        turn_radius_km = _turn_radius_km_for_path(
            speed_mps=turn_speed_mps,
            turn_rate_deg_s=float(self.rules.turn_rate_deg_s),
            offset_km=float(FLIGHT_PATH_OFFSET_KM),
        )
        max_join_km = min(2.0, max(0.4, float(turn_radius_km) * 1.2))

        center_pos_xy = pos_xy
        closest_idx = 0
        closest_on_path = False
        if allow_snap and len(geom_xy) >= 2:
            closest = _closest_point_and_dir(pos_xy, geom_xy)
            if closest is not None:
                candidate_xy = closest[0]
                candidate_idx = closest[2]
                candidate_along_km = closest[4]
                candidate_dist_km = closest[5]
                if (candidate_along_km <= max_join_km and candidate_dist_km <= max_join_km and candidate_idx == 0):
                    center_pos_xy = candidate_xy
                    closest_idx = candidate_idx
                    closest_on_path = True
        geom_tail = geometry[closest_idx + 1:]
        if not geom_tail:
            geom_tail = geometry[closest_idx:]
        if center_pos_xy == pos_xy and isinstance(heading_deg, (int, float)) and FLIGHT_PATH_OFFSET_KM > 0:
            heading_rad = math.radians(float(heading_deg))
            right_vec = (math.cos(heading_rad), -math.sin(heading_rad))
            offset_km = float(FLIGHT_PATH_OFFSET_KM)
            wind_cross_m = state.get("wind_cross_m")
            if isinstance(wind_cross_m, (int, float)) and math.isfinite(wind_cross_m):
                offset_km += float(wind_cross_m) / 1000.0
            center_pos_xy = (
                float(pos_xy[0]) - right_vec[0] * offset_km,
                float(pos_xy[1]) - right_vec[1] * offset_km,
            )
        cur_lon, cur_lat = projection.to_lonlat(center_pos_xy[0], center_pos_xy[1])
        path_nodes = list(result.path)
        new_points = [(cur_lon, cur_lat)]
        if closest_on_path:
            proj_lon, proj_lat = projection.to_lonlat(center_pos_xy[0], center_pos_xy[1])
            if (proj_lon, proj_lat) != new_points[-1]:
                new_points.append((proj_lon, proj_lat))
            new_points.extend(geom_tail)
        else:
            new_points.extend(geometry)
        points_xy, points_alt_m, cum_dist_m, segment_map = self._build_flight_path(
            new_points,
            path_nodes,
        )
        if len(points_xy) < 2 or not cum_dist_m:
            return False
        total_dist_m = float(cum_dist_m[-1])
        if total_dist_m <= 0:
            return False
        if allow_snap and heading_vec and len(points_xy) >= 2:
            seg_dx = points_xy[1][0] - points_xy[0][0]
            seg_dy = points_xy[1][1] - points_xy[0][1]
            seg_len = math.hypot(seg_dx, seg_dy)
            if seg_len > 1e-9:
                seg_dir = (seg_dx / seg_len, seg_dy / seg_len)
                turn_cos = heading_vec[0] * seg_dir[0] + heading_vec[1] * seg_dir[1]
                if turn_cos < math.cos(math.radians(60.0)):
                    join_m = max(150.0, min(600.0, float(turn_radius_km) * 350.0))
                    join_m = min(join_m, total_dist_m * 0.4)
                    if join_m > 1.0 and total_dist_m > join_m:
                        join_idx = _bisect_index(cum_dist_m, join_m)
                        join_xy = _position_at_distance(points_xy, cum_dist_m, join_m)
                        join_alt = _value_at_distance(points_alt_m, cum_dist_m, join_m)
                        points_xy = [join_xy] + points_xy[join_idx:]
                        points_alt_m = [join_alt] + points_alt_m[join_idx:]
                        if segment_map:
                            seg_idx = min(join_idx, len(segment_map) - 1)
                            segment_map = [segment_map[seg_idx]] + segment_map[join_idx:]
                        cum_dist_m = _cumulative_dist_m(points_xy)
        arc_joined = False
        if heading_vec and len(points_xy) >= 2 and cum_dist_m:
            seg_dx = points_xy[1][0] - points_xy[0][0]
            seg_dy = points_xy[1][1] - points_xy[0][1]
            seg_len = math.hypot(seg_dx, seg_dy)
            if seg_len > 1e-9 and isinstance(heading_deg, (int, float)):
                path_heading_deg = _wrap_heading_deg(math.degrees(math.atan2(seg_dx, seg_dy)))
                delta_deg = _angle_delta_deg(float(heading_deg), path_heading_deg)
                if abs(delta_deg) >= 20.0 and turn_radius_km > 0:
                    heading_rad = math.radians(float(heading_deg))
                    right_vec = (math.cos(heading_rad), -math.sin(heading_rad))
                    turn_left = delta_deg > 0.0
                    center_x = pos_xy[0] + (-right_vec[0] if turn_left else right_vec[0]) * turn_radius_km
                    center_y = pos_xy[1] + (-right_vec[1] if turn_left else right_vec[1]) * turn_radius_km
                    a0 = math.atan2(pos_xy[1] - center_y, pos_xy[0] - center_x)
                    sweep = math.radians(float(delta_deg))
                    arc_len = abs(sweep) * turn_radius_km
                    arc_step_km = min(0.05, max(0.01, float(turn_radius_km) / 25.0))
                    steps = max(2, int(arc_len / arc_step_km))
                    arc_points = [pos_xy]
                    for s in range(1, steps + 1):
                        ang = a0 + sweep * (s / steps)
                        arc_points.append(
                            (
                                center_x + turn_radius_km * math.cos(ang),
                                center_y + turn_radius_km * math.sin(ang),
                            )
                        )
                    arc_end = arc_points[-1]
                    proj_dist_m, proj_along_m = _project_point_to_polyline_m(
                        points_xy,
                        arc_end[0],
                        arc_end[1],
                    )
                    max_join_m = float(max_join_km) * 1000.0
                    if (
                        math.isfinite(proj_dist_m)
                        and math.isfinite(proj_along_m)
                        and proj_dist_m <= max_join_m
                        and 0.0 <= proj_along_m <= max_join_m
                    ):
                        proj_xy = _position_at_distance(points_xy, cum_dist_m, proj_along_m)
                        join_idx = _bisect_index(cum_dist_m, proj_along_m)
                        merged_xy = arc_points[:-1] + [proj_xy] + points_xy[join_idx + 1:]
                        merged_xy = _clean_polyline_xy(merged_xy, min_dist_km=1e-9)
                        if len(merged_xy) >= 2:
                            points_xy = merged_xy
                            alt_src = state.get("alt_m")
                            if not isinstance(alt_src, (int, float)) or not math.isfinite(alt_src):
                                alt_src = FLIGHT_ALT_M
                            points_alt_m = [float(alt_src)] * len(points_xy)
                            cum_dist_m = _cumulative_dist_m(points_xy)
                            node_xy = [
                                self.planner.node_xy[name]
                                for name in path_nodes
                                if name in self.planner.node_xy
                            ]
                            if len(node_xy) < 2:
                                node_xy = points_xy
                            segment_map = _segment_index_map_monotone(points_xy, node_xy)
                            arc_joined = True
        dist_to_start_km = math.hypot(
            pos_xy[0] - points_xy[0][0],
            pos_xy[1] - points_xy[0][1],
        )
        if dist_to_start_km > 0.001 and not arc_joined:
            turn_radius_km = _turn_radius_km_for_path(
                speed_mps=turn_speed_mps,
                turn_rate_deg_s=float(self.rules.turn_rate_deg_s),
                offset_km=float(FLIGHT_PATH_OFFSET_KM),
            )
            lead_step_km = min(
                0.05,
                max(0.01, float(turn_radius_km) / 25.0),
            )
            lead_points: list[tuple[float, float]] = [pos_xy]
            if heading_vec:
                lead_km = min(max(0.05, turn_radius_km * 0.8), dist_to_start_km * 0.7)
                if lead_km > 0.02:
                    lead_points.append(
                        (
                            pos_xy[0] + heading_vec[0] * lead_km,
                            pos_xy[1] + heading_vec[1] * lead_km,
                        )
                    )
            lead_points.append(points_xy[0])
            lead_arc = _fillet_polyline_xy(
                lead_points,
                radius_km=turn_radius_km,
                step_km=lead_step_km,
                angle_threshold_deg=0.0,
            )
            lead_arc = _densify_points_xy(lead_arc, lead_step_km)
            lead_arc = _clean_polyline_xy(lead_arc, min_dist_km=1e-9)
            if len(lead_arc) >= 2:
                lead_prefix = lead_arc[:-1]
                points_xy = lead_prefix + points_xy
                alt_src = state.get("alt_m")
                if not isinstance(alt_src, (int, float)) or not math.isfinite(alt_src):
                    alt_src = FLIGHT_ALT_M
                points_alt_m = [float(alt_src) for _ in lead_prefix] + points_alt_m
                if segment_map:
                    segment_map = [segment_map[0] for _ in lead_prefix] + segment_map
                cum_dist_m = _cumulative_dist_m(points_xy)
        total_dist_m = float(cum_dist_m[-1])
        if total_dist_m <= 0:
            return False
        speed_mps = state.get("speed_base_mps", state.get("speed_mps"))
        if isinstance(speed_mps, (int, float)) and math.isfinite(speed_mps) and speed_mps > 0:
            flight.speed_mps = float(speed_mps)
        flight.points_xy = points_xy
        flight.points_alt_m = points_alt_m
        flight.cum_dist_m = cum_dist_m
        flight.total_dist_m = total_dist_m
        flight.path_nodes = path_nodes
        flight.path_segment_idx = segment_map
        profile = _build_flight_profile(total_dist_m, flight.speed_mps, self.rules)
        flight.accel_time_s = profile.accel_time_s
        flight.cruise_time_s = profile.cruise_time_s
        flight.total_time_s = profile.total_time_s
        flight.peak_speed_mps = profile.peak_speed_mps
        flight.profile = profile
        control = self._get_control(flight.flight_id)
        control.manual_active = True
        manual_dist_m = 0.0
        if allow_manual_snap and isinstance(pos_xy, tuple) and len(pos_xy) == 2:
            proj_dist_m, along_m = _project_point_to_polyline_m(
                points_xy,
                pos_xy[0],
                pos_xy[1],
            )
            max_join_m = float(max_join_km) * 1000.0
            if (
                math.isfinite(proj_dist_m)
                and math.isfinite(along_m)
                and proj_dist_m <= max_join_m
                and along_m <= max_join_m
            ):
                manual_dist_m = max(0.0, min(float(total_dist_m), float(along_m)))
        control.manual_dist_m = manual_dist_m
        control.manual_arrival_s = None
        self._clear_no_route_hold(flight.flight_id)
        return True


    def _replan_flight_from_origin(self, flight: Flight) -> bool:
        try:
            result = self.planner.find_route(flight.origin, flight.destination)
        except Exception:
            return False
        geometry = list(result.points)
        if len(geometry) < 2:
            return False
        speed_mps = flight.speed_mps
        control = self.flight_controls.get(flight.flight_id)
        if control and isinstance(control.speed_override_mps, (int, float)):
            if control.speed_override_mps > 0:
                speed_mps = float(control.speed_override_mps)
        points_xy, points_alt_m, cum_dist_m, segment_map = self._build_flight_path(
            geometry,
            list(result.path),
        )
        if len(points_xy) < 2 or not cum_dist_m:
            return False
        total_dist_m = float(cum_dist_m[-1])
        if total_dist_m <= 0:
            return False
        profile = _build_flight_profile(total_dist_m, float(speed_mps), self.rules)
        flight.points_xy = points_xy
        flight.points_alt_m = points_alt_m
        flight.cum_dist_m = cum_dist_m
        flight.total_dist_m = total_dist_m
        flight.accel_time_s = profile.accel_time_s
        flight.cruise_time_s = profile.cruise_time_s
        flight.total_time_s = profile.total_time_s
        flight.peak_speed_mps = profile.peak_speed_mps
        flight.profile = profile
        flight.path_nodes = list(result.path)
        flight.path_segment_idx = segment_map
        self._clear_no_route_hold(flight.flight_id)
        return True

    # --- Prediction / risk helpers ---
    def _flight_phase(self, flight: Flight, elapsed_s: float) -> tuple[str, str, float]:
        wait_s = max(0.0, float(getattr(flight, "preflight_wait_s", PREFLIGHT_WAIT_S)))
        profile = self._get_profile(flight)
        if elapsed_s < wait_s:
            return MODE_WAITING, MODE_WAITING, elapsed_s
        t_since_start = elapsed_s - wait_s
        if t_since_start < profile.takeoff_time_s:
            return MODE_TAKEOFF, MODE_TAKEOFF, t_since_start
        t_since_start -= profile.takeoff_time_s
        if t_since_start < profile.cruise_total_time_s:
            return MODE_CRUISE, MODE_CRUISE, t_since_start
        t_since_start -= profile.cruise_total_time_s
        if t_since_start < profile.landing_time_s:
            return MODE_LANDING, MODE_LANDING, t_since_start
        t_since_start -= profile.landing_time_s
        return MODE_ENDED, MODE_ENDED, t_since_start

    def _build_prediction_path_xy(
        self,
        flight: Flight,
        dist_m: float,
        speed_mps: float,
        horizon_s: float,
    ) -> list[tuple[float, float]]:
        if speed_mps <= 0 or horizon_s <= 0:
            return []
        total_dist_m = float(flight.total_dist_m)
        start_dist = float(dist_m)
        remaining_m = total_dist_m - start_dist
        if remaining_m <= 0.0:
            return []
        max_horizon_s = remaining_m / float(speed_mps)
        horizon_s = min(float(horizon_s), max_horizon_s)
        step_list = _prediction_time_steps(horizon_s)
        if not step_list:
            return []
        points: list[tuple[float, float]] = []
        dist = start_dist
        points.append(_position_at_distance(flight.points_xy, flight.cum_dist_m, dist))
        for dt in step_list:
            dist = min(total_dist_m, dist + float(speed_mps) * dt)
            points.append(_position_at_distance(flight.points_xy, flight.cum_dist_m, dist))
            if dist >= total_dist_m:
                break
        return points

    def _build_prediction_path_xy_wind(
        self,
        flight: Flight,
        dist_m: float,
        speed_mps: float,
        horizon_s: float,
    ) -> list[tuple[float, float]]:
        if (
            speed_mps <= 0
            or horizon_s <= 0
            or not flight.points_xy
            or not flight.cum_dist_m
            or float(flight.total_dist_m) <= 0
        ):
            return []
        if int(getattr(self.rules, "wind_enabled", 0)) <= 0:
            return self._build_prediction_path_xy(flight, dist_m, speed_mps, horizon_s)

        total_dist_m = float(flight.total_dist_m)
        step_list = _prediction_time_steps(horizon_s)
        if not step_list:
            return []

        state = self.flight_state.get(flight.flight_id) or {}
        cross_m = float(state.get("wind_cross_m") or 0.0)
        along_m = float(state.get("wind_along_m") or 0.0)
        prev_e = state.get("wind_e_mps")
        prev_n = state.get("wind_n_mps")
        w_e_prev = float(prev_e) if isinstance(prev_e, (int, float)) else 0.0
        w_n_prev = float(prev_n) if isinstance(prev_n, (int, float)) else 0.0

        smooth_s = max(0.0, float(getattr(self.rules, "wind_smooth_s", 0.0)))
        cross_gain = max(0.0, float(getattr(self.rules, "wind_cross_gain", 0.0)))
        cross_return = max(0.0, float(getattr(self.rules, "wind_cross_return_s", 0.0)))
        cross_max = max(0.0, float(getattr(self.rules, "wind_cross_max_m", 0.0)))
        along_gain = max(0.0, float(getattr(self.rules, "wind_along_gain", 0.0)))
        projection = self.planner.projection
        base_speed_mps = float(speed_mps)
        sim_base_s = float(self.sim_elapsed_s)
        wind_scale = 1.0
        control = self.flight_controls.get(flight.flight_id)
        if control and isinstance(control.wind_effect_scale, (int, float)):
            if math.isfinite(control.wind_effect_scale):
                wind_scale = max(0.0, min(1.0, float(control.wind_effect_scale)))

        points: list[tuple[float, float]] = []
        elapsed_s = 0.0
        effective_dist = max(0.0, min(total_dist_m, float(dist_m) + along_m))
        base_pos = _position_at_distance(
            flight.points_xy,
            flight.cum_dist_m,
            effective_dist,
        )
        track_heading = _heading_at_distance_smooth(
            flight.points_xy,
            flight.cum_dist_m,
            effective_dist,
        )
        heading_rad = math.radians(float(track_heading))
        right_vec = (math.cos(heading_rad), -math.sin(heading_rad))
        pos_xy = (
            base_pos[0] + right_vec[0] * (cross_m / 1000.0),
            base_pos[1] + right_vec[1] * (cross_m / 1000.0),
        )
        points.append(pos_xy)
        for dt in step_list:
            sim_t = sim_base_s + elapsed_s + dt
            lon, lat = projection.to_lonlat(pos_xy[0], pos_xy[1])
            wind = self.wind_model.wind_at(lon, lat, sim_t)
            w_e = float(wind.u)
            w_n = float(wind.v)
            if smooth_s > 0.0 and (w_e_prev != 0.0 or w_n_prev != 0.0):
                alpha = _exp_smooth_alpha(dt, smooth_s)
                w_e = w_e_prev + (w_e - w_e_prev) * alpha
                w_n = w_n_prev + (w_n - w_n_prev) * alpha

            heading_vec = _heading_vector(track_heading)
            right_heading = (heading_vec[1], -heading_vec[0])
            w_along = w_e * heading_vec[0] + w_n * heading_vec[1]
            w_cross = w_e * right_heading[0] + w_n * right_heading[1]
            effect_scale = float(WIND_EFFECT_SCALE)
            if math.isfinite(effect_scale) and effect_scale > 0.0:
                effect_scale *= wind_scale
                w_along *= effect_scale
                w_cross *= effect_scale

            if cross_return > 0.0:
                cross_m += (w_cross * cross_gain - cross_m / cross_return) * dt
                along_m += (w_along * along_gain - along_m / cross_return) * dt
            else:
                cross_m += w_cross * cross_gain * dt
                along_m += w_along * along_gain * dt
            if cross_max > 0.0:
                cross_m = max(-cross_max, min(cross_max, cross_m))

            dist_m = min(total_dist_m, float(dist_m) + base_speed_mps * dt)

            w_e_prev = w_e
            w_n_prev = w_n
            elapsed_s += dt

            effective_dist = max(0.0, min(total_dist_m, float(dist_m) + along_m))
            base_pos = _position_at_distance(
                flight.points_xy,
                flight.cum_dist_m,
                effective_dist,
            )
            track_heading = _heading_at_distance_smooth(
                flight.points_xy,
                flight.cum_dist_m,
                effective_dist,
            )
            heading_rad = math.radians(float(track_heading))
            right_vec = (math.cos(heading_rad), -math.sin(heading_rad))
            pos_xy = (
                base_pos[0] + right_vec[0] * (cross_m / 1000.0),
                base_pos[1] + right_vec[1] * (cross_m / 1000.0),
            )
            points.append(pos_xy)
            if dist_m >= total_dist_m:
                break

        return points

    def _build_hold_path_xy(self, control: FlightControl) -> list[tuple[float, float]]:
        if not control.hold_center_xy or control.hold_radius_m <= 0:
            return []
        center_x, center_y = control.hold_center_xy
        radius_km = control.hold_radius_m / 1000.0
        steps = 36
        points: list[tuple[float, float]] = []
        for idx in range(steps + 1):
            angle = (2.0 * math.pi * idx) / steps
            points.append(
                (
                    center_x + radius_km * math.cos(angle),
                    center_y + radius_km * math.sin(angle),
                )
            )
        return points

    def _compute_risk_levels(self, flights: list[Flight]) -> dict[int, dict[str, object]]:
        def read_float(value: object, fallback: float) -> float:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                return fallback
            return parsed if math.isfinite(parsed) else fallback

        rules = self.rules
        no_route_ids: set[int] = set()
        no_route_reasons: dict[int, str] = {}
        for flight in flights:
            control = self.flight_controls.get(flight.flight_id)
            if control and control.no_route_active:
                no_route_ids.add(flight.flight_id)
                no_route_reasons[flight.flight_id] = str(
                    control.no_route_reason or "경로 없음"
                )
        predict_horizon_s = read_float(
            getattr(rules, "risk_predict_horizon_s", RISK_PREDICT_HORIZON_S),
            RISK_PREDICT_HORIZON_S,
        )
        if predict_horizon_s <= 0:
            predict_horizon_s = RISK_PREDICT_HORIZON_S
        risk_lateral_m = read_float(
            getattr(rules, "risk_lateral_m", RISK_LATERAL_M),
            RISK_LATERAL_M,
        )
        if risk_lateral_m <= 0:
            risk_lateral_m = RISK_LATERAL_M
        risk_direction_cos = read_float(
            getattr(rules, "risk_direction_cos", RISK_DIRECTION_COS),
            RISK_DIRECTION_COS,
        )
        risk_direction_cos = max(-1.0, min(1.0, risk_direction_cos))
        prox_lv1 = read_float(
            getattr(rules, "risk_proximity_lv1_m", RISK_PROX_LV1_M),
            RISK_PROX_LV1_M,
        )
        prox_lv2 = read_float(
            getattr(rules, "risk_proximity_lv2_m", RISK_PROX_LV2_M),
            RISK_PROX_LV2_M,
        )
        prox_lv3 = read_float(
            getattr(rules, "risk_proximity_lv3_m", RISK_PROX_LV3_M),
            RISK_PROX_LV3_M,
        )
        prox_lv3, prox_lv2, prox_lv1 = sorted(
            [max(0.0, prox_lv3), max(0.0, prox_lv2), max(0.0, prox_lv1)]
        )
        batt_lv1 = read_float(
            getattr(rules, "risk_battery_lv1_pct", RISK_BATT_LV1_PCT),
            RISK_BATT_LV1_PCT,
        )
        batt_lv2 = read_float(
            getattr(rules, "risk_battery_lv2_pct", RISK_BATT_LV2_PCT),
            RISK_BATT_LV2_PCT,
        )
        batt_lv3 = read_float(
            getattr(rules, "risk_battery_lv3_pct", RISK_BATT_LV3_PCT),
            RISK_BATT_LV3_PCT,
        )
        batt_lv3, batt_lv2, batt_lv1 = sorted(
            [max(0.0, batt_lv3), max(0.0, batt_lv2), max(0.0, batt_lv1)]
        )

        rnp_max_lat = read_float(
            getattr(rules, "rnp_max_lat_m", 0.0),
            0.0,
        )
        rnp_max_ver = read_float(
            getattr(rules, "rnp_max_ver_m", 0.0),
            0.0,
        )
        rnp_r_lv1 = read_float(getattr(rules, "rnp_r_lv1", 0.4), 0.4)
        rnp_r_lv2 = read_float(getattr(rules, "rnp_r_lv2", 0.7), 0.7)
        rnp_r_lv3 = read_float(getattr(rules, "rnp_r_lv3", 1.0), 1.0)
        rnp_r_lv1, rnp_r_lv2, rnp_r_lv3 = sorted(
            [max(0.0, rnp_r_lv1), max(0.0, rnp_r_lv2), max(0.0, rnp_r_lv3)]
        )
        rnp_ttv_lv1 = read_float(getattr(rules, "rnp_ttv_lv1_s", 10.0), 10.0)
        rnp_ttv_lv2 = read_float(getattr(rules, "rnp_ttv_lv2_s", 5.0), 5.0)
        rnp_ttv_lv2, rnp_ttv_lv1 = sorted(
            [max(0.0, rnp_ttv_lv2), max(0.0, rnp_ttv_lv1)]
        )

        def _ttv_to_limit(dev_m: float, rate_mps: float, limit_m: float) -> float | None:
            if limit_m <= 0.0:
                return None
            if not math.isfinite(dev_m) or not math.isfinite(rate_mps):
                return None
            abs_dev = abs(float(dev_m))
            if abs_dev >= limit_m:
                return 0.0
            if abs(rate_mps) <= 1e-6:
                return None
            if dev_m * rate_mps <= 0:
                return None
            return max(0.0, (limit_m - abs_dev) / abs(rate_mps))

        def _predict_ttv_from_path(
            flight: Flight,
            dist_m: object,
            speed_mps: object,
            horizon_s: float,
            limit_m: float,
        ) -> float | None:
            if limit_m <= 0.0 or horizon_s <= 0.0:
                return None
            if not isinstance(dist_m, (int, float)) or not math.isfinite(dist_m):
                return None
            if not isinstance(speed_mps, (int, float)) or not math.isfinite(speed_mps):
                return None
            if speed_mps <= 0.0:
                return None
            if not flight.points_xy or not flight.cum_dist_m:
                return None
            path_xy = self._build_prediction_path_xy_wind(
                flight,
                float(dist_m),
                float(speed_mps),
                horizon_s,
            )
            if not path_xy or len(path_xy) < 2:
                return None
            time_steps = _prediction_time_steps(horizon_s)
            if not time_steps:
                return None
            times = [0.0]
            for dt in time_steps:
                times.append(times[-1] + dt)
            if len(times) < len(path_xy):
                times.extend([times[-1]] * (len(path_xy) - len(times)))
            else:
                times = times[:len(path_xy)]
            prev_dev: float | None = None
            for idx, (px, py) in enumerate(path_xy):
                dev_m, _ = _project_point_to_polyline_m(flight.points_xy, px, py)
                if dev_m >= limit_m:
                    if idx == 0 or prev_dev is None:
                        return 0.0
                    if prev_dev >= limit_m:
                        return max(0.0, times[idx])
                    span = dev_m - prev_dev
                    if span <= 1e-6:
                        return max(0.0, times[idx])
                    ratio = (limit_m - prev_dev) / span
                    dt_segment = times[idx] - times[idx - 1] if idx > 0 else 0.0
                    return max(0.0, times[idx - 1] + ratio * dt_segment)
                prev_dev = dev_m
            return None

        rnp_levels: dict[int, dict[str, object]] = {}
        for flight in flights:
            state = self.flight_state.get(flight.flight_id)
            if not state or state.get("phase") not in (MODE_CRUISE, MODE_LANDING):
                continue
            if rnp_max_lat <= 0.0 and rnp_max_ver <= 0.0:
                continue
            lat_dev = state.get("lateral_dev_m")
            ver_dev = state.get("vertical_dev_m")
            lat_rate = state.get("lateral_rate_mps")
            ver_rate = state.get("vertical_rate_mps")
            ratio_lat = 0.0
            ratio_ver = 0.0
            if rnp_max_lat > 0.0 and isinstance(lat_dev, (int, float)) and math.isfinite(lat_dev):
                ratio_lat = abs(float(lat_dev)) / rnp_max_lat
            if rnp_max_ver > 0.0 and isinstance(ver_dev, (int, float)) and math.isfinite(ver_dev):
                ratio_ver = abs(float(ver_dev)) / rnp_max_ver
            r_value = max(ratio_lat, ratio_ver)
            r_level = 0
            if r_value >= rnp_r_lv3:
                r_level = 3
            elif r_value >= rnp_r_lv2:
                r_level = 2
            elif r_value >= rnp_r_lv1:
                r_level = 1

            dist_m = state.get("dist_m")
            speed_mps = state.get("speed_mps")
            ttv_lat = _predict_ttv_from_path(
                flight,
                dist_m,
                speed_mps,
                float(predict_horizon_s),
                rnp_max_lat,
            )
            ttv_ver = _ttv_to_limit(
                float(ver_dev) if isinstance(ver_dev, (int, float)) else math.nan,
                float(ver_rate) if isinstance(ver_rate, (int, float)) else math.nan,
                rnp_max_ver,
            )
            ttv_candidates = [val for val in (ttv_lat, ttv_ver) if val is not None]
            ttv_corr = min(ttv_candidates) if ttv_candidates else None
            ttv_level = 0
            if ttv_corr is not None:
                if ttv_corr < rnp_ttv_lv2:
                    ttv_level = 3
                elif ttv_corr < rnp_ttv_lv1:
                    ttv_level = 2
                else:
                    ttv_level = 1

            level = max(r_level, ttv_level)
            reason = ""
            if level > 0:
                reason = f"RNP r={r_value:.2f}"
                if ttv_corr is not None:
                    reason = f"{reason}, TTV {ttv_corr:.0f}s"
            rnp_levels[flight.flight_id] = {"level": level, "reason": reason}

        entries: list[dict[str, object]] = []
        others: list[dict[str, object]] = []
        for flight in flights:
            if flight.flight_id in no_route_ids:
                continue
            state = self.flight_state.get(flight.flight_id)
            if not state:
                continue
            pos_xy = state.get("pos_xy")
            if not isinstance(pos_xy, (list, tuple)) or len(pos_xy) != 2:
                continue
            heading_deg = state.get("track_heading_deg", state.get("heading_deg"))
            heading_vec = None
            if isinstance(heading_deg, (int, float)) and math.isfinite(heading_deg):
                heading_vec = _heading_vector(float(heading_deg))
            phase = state.get("phase")
            if phase not in (MODE_CRUISE, MODE_LANDING):
                continue
            others.append(
                {
                    "flight_id": flight.flight_id,
                    "pos_xy": (float(pos_xy[0]), float(pos_xy[1])),
                    "heading_vec": heading_vec,
                }
            )
            dist_m = state.get("dist_m")
            speed_mps = state.get("speed_mps")
            battery_pct = state.get("battery_pct")
            control = self.flight_controls.get(flight.flight_id)
            path_xy: list[tuple[float, float]] = []
            if control and control.hold_active:
                path_xy = self._build_hold_path_xy(control)
            elif (
                isinstance(dist_m, (int, float))
                and isinstance(speed_mps, (int, float))
            ):
                path_xy = self._build_prediction_path_xy(
                    flight,
                    float(dist_m),
                    float(speed_mps),
                    predict_horizon_s,
                )
            if len(path_xy) < 2:
                continue
            xs = [pt[0] for pt in path_xy]
            ys = [pt[1] for pt in path_xy]
            entries.append(
                {
                    "flight_id": flight.flight_id,
                    "pos_xy": (float(pos_xy[0]), float(pos_xy[1])),
                    "heading_vec": heading_vec,
                    "path_xy": path_xy,
                    "path_len_m": _polyline_length_m(path_xy),
                    "bbox": (min(xs), max(xs), min(ys), max(ys)),
                    "battery_pct": battery_pct,
                }
            )
        risk_levels = {
            flight.flight_id: {"level": 0, "reason": ""} for flight in flights
        }
        lateral_km = risk_lateral_m / 1000.0
        cell_km = max(lateral_km, 0.05)
        other_grid: dict[tuple[int, int], list[dict[str, object]]] = {}
        for other in others:
            ox, oy = other["pos_xy"]
            cell = (
                math.floor(float(ox) / cell_km),
                math.floor(float(oy) / cell_km),
            )
            bucket = other_grid.get(cell)
            if bucket is None:
                other_grid[cell] = [other]
            else:
                bucket.append(other)
        for entry in entries:
            path_len_m = float(entry["path_len_m"])
            if path_len_m <= 0:
                continue
            minx, maxx, miny, maxy = entry["bbox"]
            min_ix = math.floor((minx - lateral_km) / cell_km)
            max_ix = math.floor((maxx + lateral_km) / cell_km)
            min_iy = math.floor((miny - lateral_km) / cell_km)
            max_iy = math.floor((maxy + lateral_km) / cell_km)
            min_sep = math.inf
            count = 0
            px, py = entry["pos_xy"]
            heading_vec = entry["heading_vec"]
            for ix in range(min_ix, max_ix + 1):
                for iy in range(min_iy, max_iy + 1):
                    candidates = other_grid.get((ix, iy))
                    if not candidates:
                        continue
                    for other in candidates:
                        if other["flight_id"] == entry["flight_id"]:
                            continue
                        ox, oy = other["pos_xy"]
                        if (
                            ox < minx - lateral_km
                            or ox > maxx + lateral_km
                            or oy < miny - lateral_km
                            or oy > maxy + lateral_km
                        ):
                            continue
                        other_heading = other["heading_vec"]
                        if heading_vec and other_heading:
                            dot = heading_vec[0] * other_heading[0] + heading_vec[1] * other_heading[1]
                            if dot < risk_direction_cos:
                                continue
                        dist_m, along_m = _project_point_to_polyline_m(entry["path_xy"], ox, oy)
                        if dist_m > risk_lateral_m:
                            continue
                        if along_m < 0.0 or along_m > path_len_m:
                            continue
                        count += 1
                        sep_m = math.hypot((px - ox) * 1000.0, (py - oy) * 1000.0)
                        if sep_m < min_sep:
                            min_sep = sep_m
            proximity_level = 0
            proximity_reason = ""
            if min_sep < prox_lv3:
                proximity_level = 3
                proximity_reason = f"근접 <{int(prox_lv3)}m"
            elif min_sep < prox_lv2:
                proximity_level = 2
                proximity_reason = f"근접 <{int(prox_lv2)}m"
            elif min_sep < prox_lv1:
                proximity_level = 1
                proximity_reason = f"근접 <{int(prox_lv1)}m"
            battery_level = 0
            battery_reason = ""
            battery_pct = entry.get("battery_pct")
            if isinstance(battery_pct, (int, float)) and math.isfinite(battery_pct):
                if battery_pct < batt_lv3:
                    battery_level = 3
                    battery_reason = f"전력 <{int(batt_lv3)}%"
                elif battery_pct < batt_lv2:
                    battery_level = 2
                    battery_reason = f"전력 <{int(batt_lv2)}%"
                elif battery_pct < batt_lv1:
                    battery_level = 1
                    battery_reason = f"전력 <{int(batt_lv1)}%"
            density = count / max(path_len_m / 1000.0, 1e-6)
            congestion_level = 0
            if density >= 2.0:
                congestion_level = 3
            elif density >= 1.0:
                congestion_level = 2
            elif density >= 0.5:
                congestion_level = 1
            rnp_info = rnp_levels.get(int(entry["flight_id"]), {"level": 0, "reason": ""})
            rnp_level = int(rnp_info.get("level", 0))
            rnp_reason = str(rnp_info.get("reason", "") or "")
            final_level = max(proximity_level, battery_level, rnp_level)
            reason = ""
            if final_level > 0:
                reasons = []
                if proximity_level == final_level and proximity_reason:
                    reasons.append(proximity_reason)
                if battery_level == final_level and battery_reason:
                    reasons.append(battery_reason)
                if rnp_level == final_level and rnp_reason:
                    reasons.append(rnp_reason)
                if reasons:
                    reason = " + ".join(reasons)
                elif proximity_level == final_level:
                    reason = "근접"
                elif battery_level == final_level:
                    reason = "저전력"
                elif rnp_level == final_level:
                    reason = "RNP"
            risk_levels[int(entry["flight_id"])] = {
                "level": final_level,
                "reason": reason,
            }
        if no_route_ids:
            for flight_id in no_route_ids:
                risk_levels[flight_id] = {
                    "level": 3,
                    "reason": no_route_reasons.get(flight_id, "경로 없음"),
                }
        return risk_levels

    # --- Wind influence ---
    def _update_wind_effect_scale(self, flight_id: int) -> tuple[float, float]:
        control = self.flight_controls.get(flight_id)
        if not control:
            return 1.0, 1.0
        prev_scale = control.wind_effect_scale
        if not isinstance(prev_scale, (int, float)) or not math.isfinite(prev_scale):
            prev_scale = 1.0
        scale = float(prev_scale)
        target = control.wind_effect_target_scale
        if isinstance(target, (int, float)) and math.isfinite(target):
            target = max(0.0, min(1.0, float(target)))
            duration = control.wind_effect_ramp_s
            if not isinstance(duration, (int, float)) or not math.isfinite(duration):
                duration = 0.0
            duration = max(0.0, float(duration))
            start_scale = control.wind_effect_start_scale
            if not isinstance(start_scale, (int, float)) or not math.isfinite(start_scale):
                start_scale = scale
            if duration <= 0.0:
                scale = target
                control.wind_effect_target_scale = None
                control.wind_effect_start_scale = float(scale)
                control.wind_effect_start_s = 0.0
                control.wind_effect_ramp_s = 0.0
            else:
                start_s = control.wind_effect_start_s
                if not isinstance(start_s, (int, float)) or not math.isfinite(start_s):
                    start_s = self.sim_elapsed_s
                elapsed = max(0.0, float(self.sim_elapsed_s) - float(start_s))
                t = min(1.0, elapsed / duration)
                scale = float(start_scale) + (target - float(start_scale)) * t
                if t >= 1.0:
                    control.wind_effect_target_scale = None
                    control.wind_effect_start_scale = float(scale)
                    control.wind_effect_start_s = 0.0
                    control.wind_effect_ramp_s = 0.0
            control.wind_effect_scale = float(scale)
        else:
            control.wind_effect_scale = float(scale)
        scale = max(0.0, min(1.0, float(scale)))
        return scale, float(prev_scale)

    def _apply_wind_influence(
        self,
        flight_id: int,
        mode: str,
        pos_xy: tuple[float, float],
        dist_m: float,
        speed_mps: float,
        heading_deg: float,
        delta_s: float,
        points_xy: list[tuple[float, float]],
        cum_dist_m: list[float],
        total_dist_m: float,
    ) -> tuple[tuple[float, float], float, float, float, dict[str, float]]:
        track_heading_deg = heading_deg
        wind_state: dict[str, float] = {}

        if (
            int(getattr(self.rules, "wind_enabled", 0)) <= 0
            or mode != MODE_CRUISE
            or not points_xy
            or not cum_dist_m
            or total_dist_m <= 0
        ):
            return pos_xy, speed_mps, heading_deg, track_heading_deg, wind_state

        prev_state = self.flight_state.get(flight_id) or {}
        wind_scale, prev_wind_scale = self._update_wind_effect_scale(flight_id)

        # 누적 오프셋(전 tick) 먼저 읽기
        cross_m = float(prev_state.get("wind_cross_m") or 0.0)
        along_m = float(prev_state.get("wind_along_m") or 0.0)
        if prev_wind_scale > 0.0 and wind_scale != prev_wind_scale:
            ratio = wind_scale / prev_wind_scale
            if math.isfinite(ratio):
                cross_m *= ratio
                along_m *= ratio

        if delta_s <= 0.0:
            cross_abs = abs(cross_m)
            cross_max = max(0.0, float(getattr(self.rules, "wind_cross_max_m", 0.0)))
            base_speed = (
                float(speed_mps)
                if isinstance(speed_mps, (int, float)) and math.isfinite(speed_mps)
                else 0.0
            )
            lookahead_m = max(
                30.0,
                min(250.0, max(base_speed, cross_abs * 0.25, cross_max * 0.25)),
            )
            effective_dist = max(0.0, min(float(total_dist_m), float(dist_m) + along_m))
            pos_xy = _position_at_distance(points_xy, cum_dist_m, effective_dist)
            prev_track = prev_state.get("wind_track_deg")
            if isinstance(prev_track, (int, float)) and math.isfinite(prev_track):
                track_heading_deg = float(prev_track)
            else:
                track_heading_deg = _heading_at_distance_smooth(
                    points_xy,
                    cum_dist_m,
                    effective_dist,
                    lookahead_m,
                )
            heading_rad = math.radians(float(track_heading_deg))
            right_vec = (math.cos(heading_rad), -math.sin(heading_rad))
            pos_xy = (
                pos_xy[0] + right_vec[0] * (cross_m / 1000.0),
                pos_xy[1] + right_vec[1] * (cross_m / 1000.0),
            )
            prev_heading = prev_state.get("heading_deg")
            if isinstance(prev_heading, (int, float)) and math.isfinite(prev_heading):
                heading_deg = float(prev_heading)
            else:
                heading_deg = _wrap_heading_deg(track_heading_deg)
            prev_speed = prev_state.get("speed_mps")
            if isinstance(prev_speed, (int, float)) and math.isfinite(prev_speed):
                speed_mps = float(prev_speed)
            wind_state = {}
            prev_e = prev_state.get("wind_e_mps")
            prev_n = prev_state.get("wind_n_mps")
            if isinstance(prev_e, (int, float)) and math.isfinite(prev_e):
                wind_state["wind_e_mps"] = float(prev_e)
            if isinstance(prev_n, (int, float)) and math.isfinite(prev_n):
                wind_state["wind_n_mps"] = float(prev_n)
            wind_state["wind_cross_m"] = cross_m
            wind_state["wind_along_m"] = along_m
            wind_state["wind_track_deg"] = track_heading_deg
            return pos_xy, speed_mps, heading_deg, track_heading_deg, wind_state

        # 코너에서 heading이 계단식으로 바뀌어 cross offset이 튀지 않도록 lookahead 사용
        cross_abs = abs(cross_m)
        cross_max = max(0.0, float(getattr(self.rules, "wind_cross_max_m", 0.0)))
        base_speed = float(speed_mps) if isinstance(speed_mps, (int, float)) and math.isfinite(speed_mps) else 0.0
        lookahead_m = max(30.0, min(250.0, max(base_speed, cross_abs * 0.25, cross_max * 0.25)))

        projection = self.planner.projection
        lon, lat = projection.to_lonlat(pos_xy[0], pos_xy[1])
        wind = self.wind_model.wind_at(lon, lat, self.sim_elapsed_s)

        smooth_s = float(getattr(self.rules, "wind_smooth_s", 0.0))
        smooth_s = max(0.0, smooth_s)

        w_e = float(wind.u)
        w_n = float(wind.v)

        if smooth_s > 0.0:
            prev_e = prev_state.get("wind_e_mps")
            prev_n = prev_state.get("wind_n_mps")
            if isinstance(prev_e, (int, float)) and math.isfinite(prev_e):
                alpha = _exp_smooth_alpha(delta_s, smooth_s)
                w_e = float(prev_e) + (w_e - float(prev_e)) * alpha
            if isinstance(prev_n, (int, float)) and math.isfinite(prev_n):
                alpha = _exp_smooth_alpha(delta_s, smooth_s)
                w_n = float(prev_n) + (w_n - float(prev_n)) * alpha

        # 바람 성분 분해에 사용할 트랙 헤딩도 smooth heading으로
        effective_dist0 = max(0.0, min(float(total_dist_m), float(dist_m) + along_m))
        track_heading_deg = _heading_at_distance_smooth(points_xy, cum_dist_m, effective_dist0, lookahead_m)

        heading_vec = _heading_vector(track_heading_deg)
        right_vec = (heading_vec[1], -heading_vec[0])
        w_along = w_e * heading_vec[0] + w_n * heading_vec[1]
        w_cross = w_e * right_vec[0] + w_n * right_vec[1]
        effect_scale = float(WIND_EFFECT_SCALE)
        if math.isfinite(effect_scale) and effect_scale > 0.0:
            effect_scale *= wind_scale
            w_along *= effect_scale
            w_cross *= effect_scale

        cross_gain = max(0.0, float(getattr(self.rules, "wind_cross_gain", 0.0)))
        cross_return = max(0.0, float(getattr(self.rules, "wind_cross_return_s", 0.0)))
        cross_max = max(0.0, float(getattr(self.rules, "wind_cross_max_m", 0.0)))
        along_gain = max(0.0, float(getattr(self.rules, "wind_along_gain", 0.0)))
        along_max_mps = max(0.0, float(getattr(self.rules, "wind_along_max_mps", 0.0)))

        if cross_return > 0.0:
            cross_m += (w_cross * cross_gain - cross_m / cross_return) * delta_s
            along_m += (w_along * along_gain - along_m / cross_return) * delta_s
        else:
            cross_m += w_cross * cross_gain * delta_s
            along_m += w_along * along_gain * delta_s

        if cross_max > 0.0:
            cross_m = max(-cross_max, min(cross_max, cross_m))

        effective_dist = float(dist_m) + along_m
        effective_dist = max(0.0, min(float(total_dist_m), effective_dist))

        # base 위치 및 트랙 헤딩도 smooth heading으로 (코너 튐 방지 핵심)
        pos_xy = _position_at_distance(points_xy, cum_dist_m, effective_dist)
        track_heading_deg = _heading_at_distance_smooth(points_xy, cum_dist_m, effective_dist, lookahead_m)

        smooth_track_deg = track_heading_deg
        if smooth_s > 0.0:
            prev_track = prev_state.get("wind_track_deg")
            if isinstance(prev_track, (int, float)) and math.isfinite(prev_track):
                alpha = _exp_smooth_alpha(delta_s, smooth_s)
                smooth_track_deg = _wrap_heading_deg(
                    float(prev_track) + _angle_delta_deg(prev_track, track_heading_deg) * alpha
                )

        heading_rad = math.radians(float(smooth_track_deg))
        right_vec = (math.cos(heading_rad), -math.sin(heading_rad))

        pos_xy = (
            pos_xy[0] + right_vec[0] * (cross_m / 1000.0),
            pos_xy[1] + right_vec[1] * (cross_m / 1000.0),
        )

        speed_delta = max(-along_max_mps, min(along_max_mps, w_along * along_gain))
        speed_mps = max(0.0, float(speed_mps) + speed_delta)

        crab_max = max(0.0, float(getattr(self.rules, "wind_crab_max_deg", 0.0)))
        if crab_max > 0.0 and speed_mps > 0.1:
            crab = math.degrees(math.atan2(w_cross, max(speed_mps, 1e-3)))
            crab = max(-crab_max, min(crab_max, crab))
            heading_deg = _wrap_heading_deg(smooth_track_deg + crab)
        else:
            heading_deg = _wrap_heading_deg(smooth_track_deg)

        wind_state = {
            "wind_e_mps": w_e,
            "wind_n_mps": w_n,
            "wind_cross_m": cross_m,
            "wind_along_m": along_m,
            "wind_track_deg": smooth_track_deg,
        }
        return pos_xy, speed_mps, heading_deg, track_heading_deg, wind_state

    def _finite_float(self, value: object) -> float | None:
        if isinstance(value, (int, float)) and math.isfinite(value):
            return float(value)
        return None

    def _estimate_hold_remaining_s(self, control: FlightControl) -> float | None:
        if not control.hold_active:
            return 0.0
        total_loops = int(control.hold_loops_total or 0)
        if total_loops >= 100000:
            return None
        speed_mps = self._finite_float(control.hold_speed_mps)
        radius_m = self._finite_float(control.hold_radius_m)
        if speed_mps is None or radius_m is None or speed_mps <= 0.0 or radius_m <= 0.0:
            return None
        loop_length_m = 2.0 * math.pi * float(radius_m)
        if loop_length_m <= 0.0:
            return None
        hold_elapsed_s = max(0.0, float(self.sim_elapsed_s) - float(control.hold_start_time_s))
        loops_done = hold_elapsed_s * float(speed_mps) / loop_length_m
        loops_left = max(0.0, float(total_loops) - loops_done)
        return loops_left * (loop_length_m / float(speed_mps))

    def _estimate_eta_remaining_s(
        self,
        flight: Flight,
        mode: str,
        phase: str,
        elapsed_s: float,
        wait_s: float,
        dist_m: float,
        speed_mps: float,
        control: FlightControl | None,
    ) -> float | None:
        if mode in (MODE_ENDED, MODE_FAILED):
            return 0.0
        hold_remaining_s = 0.0
        if control and control.hold_active:
            hold_remaining = self._estimate_hold_remaining_s(control)
            if hold_remaining is None:
                return None
            hold_remaining_s = max(0.0, float(hold_remaining))

        if phase == MODE_WAITING:
            remaining_wait_s = max(0.0, float(wait_s) - float(elapsed_s))
            return hold_remaining_s + remaining_wait_s + max(0.0, float(flight.total_time_s))

        total_dist_m = max(0.0, float(flight.total_dist_m))
        current_dist_m = float(dist_m) if math.isfinite(dist_m) else 0.0
        current_dist_m = max(0.0, min(total_dist_m, current_dist_m))
        remaining_dist_m = max(0.0, total_dist_m - current_dist_m)

        speed_candidates = [
            self._finite_float(speed_mps),
            self._finite_float(flight.speed_mps),
            self._finite_float(self.rules.min_safe_speed_mps),
        ]
        effective_speed_mps = next(
            (value for value in speed_candidates if value is not None and value > 0.0),
            1.0,
        )
        move_remaining_s = remaining_dist_m / max(1.0, float(effective_speed_mps))
        airborne_elapsed_s = max(0.0, float(elapsed_s) - float(wait_s))
        profile_remaining_s = max(0.0, float(flight.total_time_s) - airborne_elapsed_s)
        if phase in (MODE_TAKEOFF, MODE_LANDING):
            remaining_s = profile_remaining_s
        else:
            remaining_s = max(move_remaining_s, profile_remaining_s)
        return hold_remaining_s + max(0.0, remaining_s)

    def _build_ops_metrics_payload(
        self,
        metrics: dict[str, object] | None,
        updated: bool,
    ) -> dict[str, object]:
        values = metrics or {}
        return {
            "std_s": self._finite_float(values.get("std_s")),
            "sta_s": self._finite_float(values.get("sta_s")),
            "eta_s": self._finite_float(values.get("eta_s")),
            "ata_s": self._finite_float(values.get("ata_s")),
            "delay_s": self._finite_float(values.get("delay_s")),
            "tti": self._finite_float(values.get("tti")),
            "remaining_dist_m": self._finite_float(values.get("remaining_dist_m")),
            "remaining_time_s": self._finite_float(values.get("remaining_time_s")),
            "ops_metrics_updated": bool(updated),
        }

    def _update_flight_ops_metrics(
        self,
        flight: Flight,
        mode: str,
        phase: str,
        elapsed_s: float,
        wait_s: float,
        dist_m: float,
        speed_mps: float,
        control: FlightControl | None,
        force_update: bool = False,
        finalize_arrival: bool = False,
    ) -> tuple[dict[str, object], bool]:
        now_s = float(self.sim_elapsed_s)
        prev = self.flight_ops_metrics.get(flight.flight_id, {})
        std_s = self._finite_float(prev.get("std_s"))
        if std_s is None:
            std_s = self._finite_float(flight.std_s)
        if std_s is None:
            std_s = float(flight.start_offset_s)

        sta_s = self._finite_float(prev.get("sta_s"))
        if sta_s is None:
            sta_s = self._finite_float(flight.sta_s)
        if sta_s is None:
            sta_s = float(std_s) + max(0.0, float(wait_s)) + max(0.0, float(flight.total_time_s))

        ata_s = self._finite_float(prev.get("ata_s"))
        if ata_s is None:
            ata_s = self._finite_float(flight.ata_s)
        if finalize_arrival and ata_s is None:
            ata_s = now_s
            flight.ata_s = ata_s

        update_now = bool(force_update) or not prev
        eta_s = self._finite_float(prev.get("eta_s"))
        remaining_time_s = self._finite_float(prev.get("remaining_time_s"))
        remaining_dist_m = self._finite_float(prev.get("remaining_dist_m"))
        if update_now or eta_s is None:
            remaining = self._estimate_eta_remaining_s(
                flight,
                mode,
                phase,
                elapsed_s,
                wait_s,
                dist_m,
                speed_mps,
                control,
            )
            if remaining is None:
                remaining_time_s = None
                eta_s = None
            else:
                remaining_time_s = max(0.0, float(remaining))
                eta_s = now_s + remaining_time_s
            if isinstance(dist_m, (int, float)) and math.isfinite(dist_m):
                remaining_dist_m = max(0.0, float(flight.total_dist_m) - float(dist_m))
            else:
                remaining_dist_m = None

        if ata_s is not None:
            eta_s = ata_s
            remaining_time_s = 0.0
            remaining_dist_m = 0.0

        delay_s = None
        if eta_s is not None and sta_s is not None:
            delay_s = float(eta_s) - float(sta_s)

        tti = None
        if eta_s is not None and sta_s is not None:
            # Keep a stable final TTI after arrival:
            #   TTI_final = actual_total_time / planned_total_time
            if ata_s is not None:
                planned_total_s = max(0.0, float(sta_s) - float(std_s))
                actual_total_s = max(0.0, float(ata_s) - float(std_s))
                if planned_total_s > 1e-6:
                    tti = actual_total_s / planned_total_s
                elif actual_total_s <= 1e-6:
                    tti = 1.0
            if tti is None:
                eta_remaining_s = max(0.0, float(eta_s) - now_s)
                sta_remaining_s = max(0.0, float(sta_s) - now_s)
                if sta_remaining_s > 1e-6:
                    tti = eta_remaining_s / sta_remaining_s
                elif eta_remaining_s <= 1e-6:
                    tti = 1.0

        next_metrics = {
            "std_s": float(std_s),
            "sta_s": float(sta_s),
            "eta_s": eta_s,
            "ata_s": ata_s,
            "delay_s": delay_s,
            "tti": tti,
            "remaining_dist_m": remaining_dist_m,
            "remaining_time_s": remaining_time_s,
            "updated_s": now_s if update_now else self._finite_float(prev.get("updated_s")) or now_s,
        }
        flight.std_s = float(std_s)
        flight.sta_s = float(sta_s)
        flight.ata_s = ata_s
        self.flight_ops_metrics[flight.flight_id] = next_metrics
        return next_metrics, update_now


    # --- Main update loop ---
    def _update_positions(self) -> None:
        self._spawn_ready_flights()
        positions: list[dict[str, object]] = []
        statuses: list[dict[str, object]] = []
        active_flights: list[Flight] = []
        ops_metrics_due = (
            self.last_ops_metrics_update_s is None
            or self.sim_elapsed_s - self.last_ops_metrics_update_s >= OPS_METRICS_INTERVAL_S
        )
        if ops_metrics_due:
            self.last_ops_metrics_update_s = float(self.sim_elapsed_s)
        landing_s = max(0, int(self.rules.landing_s))
        delta_s = 0.0
        if self.last_positions_time_s is not None:
            delta_s = max(0.0, self.sim_elapsed_s - self.last_positions_time_s)
        self.last_positions_time_s = self.sim_elapsed_s
        for flight in self.flights:
            elapsed = self.sim_elapsed_s - flight.start_offset_s
            if elapsed < 0:
                continue
            wait_s = max(0.0, float(getattr(flight, "preflight_wait_s", PREFLIGHT_WAIT_S)))
            prev_state = self.flight_state.get(flight.flight_id)
            prev_risk = int(prev_state.get("risk_level", 0)) if prev_state else 0
            prev_reason = str(prev_state.get("risk_reason", "")) if prev_state else ""
            mode, phase, phase_t = self._flight_phase(flight, elapsed)
            speed_mps = 0.0
            pos_xy = flight.points_xy[0]
            alt_m = VERTIPORT_ALT_M
            dist_m = 0.0
            heading_deg = 0.0
            control = self.flight_controls.get(flight.flight_id)
            if not control and self.autopilot.enabled and prev_risk > 0:
                control = self._get_control(flight.flight_id)
            manual_active = bool(control and control.manual_active)
            autopilot_scale = 1.0
            base_speed_hint_mps: float | None = None
            if control:
                if not control.autopilot_active and prev_state:
                    prev_speed = prev_state.get("speed_base_mps", prev_state.get("speed_mps"))
                    if isinstance(prev_speed, (int, float)) and math.isfinite(prev_speed):
                        if float(prev_speed) > 0.0:
                            base_speed_hint_mps = float(prev_speed)
                if base_speed_hint_mps is None:
                    override_speed = control.speed_override_mps
                    if isinstance(override_speed, (int, float)) and math.isfinite(override_speed):
                        if float(override_speed) > 0.0:
                            base_speed_hint_mps = float(override_speed)
                if base_speed_hint_mps is None:
                    flight_speed = float(flight.speed_mps)
                    if math.isfinite(flight_speed) and flight_speed > 0.0:
                        base_speed_hint_mps = flight_speed
                autopilot_scale = self._sync_autopilot_state(
                    flight,
                    control,
                    prev_risk,
                    prev_state,
                    phase,
                    base_speed_hint_mps,
                )
                manual_active = bool(control.manual_active)
            target_speed_mps: float | None = None
            profile = self._get_profile(flight)
            t_since_start = max(0.0, elapsed - wait_s)
            if phase == MODE_WAITING:
                mode = MODE_WAITING
                phase = MODE_WAITING
            elif manual_active and (
                phase not in (MODE_TAKEOFF, MODE_WAITING) or (control and control.hold_active)
            ):
                if not control:
                    control = self._get_control(flight.flight_id)
                if control.manual_dist_m is None:
                    base_phase_t = max(0.0, elapsed - wait_s)
                    control.manual_dist_m = _distance_at_time_profile(profile, base_phase_t)
                dist_m = float(control.manual_dist_m or 0.0)
                if control.hold_active and control.hold_center_xy:
                    hold_elapsed = max(0.0, self.sim_elapsed_s - control.hold_start_time_s)
                    radius_m = control.hold_radius_m if control.hold_radius_m > 0 else HOLD_RADIUS_M
                    radius_km = radius_m / 1000.0
                    loop_length = 2.0 * math.pi * radius_m
                    loops_done = (
                        hold_elapsed * control.hold_speed_mps / loop_length if loop_length > 0 else 0.0
                    )
                    if loops_done < control.hold_loops_total:
                        angle = control.hold_start_angle_rad
                        if radius_m > 0:
                            angle -= (control.hold_speed_mps / radius_m) * hold_elapsed
                        center_x, center_y = control.hold_center_xy
                        pos_xy = (
                            center_x + radius_km * math.cos(angle),
                            center_y + radius_km * math.sin(angle),
                        )
                        alt_m = control.hold_alt_m
                        speed_mps = control.hold_speed_mps
                        mode = MODE_HOLD
                        phase = MODE_HOLD
                        vel_dx = math.sin(angle)
                        vel_dy = -math.cos(angle)
                        heading_deg = math.degrees(math.atan2(vel_dx, vel_dy))
                        if heading_deg < 0:
                            heading_deg += 360.0
                    else:
                        control.hold_active = False
                if not control.hold_active:
                    base_speed = control.speed_override_mps or flight.speed_mps
                    target_speed = float(base_speed)
                    if control.emergency_active and flight.total_dist_m > 0:
                        progress = min(1.0, max(0.0, dist_m / flight.total_dist_m))
                        ratio = 1.0 - (1.0 - EMERGENCY_SPEED_MIN_RATIO) * progress
                        target_speed = float(base_speed) * ratio
                    if phase in (MODE_CRUISE, MODE_LANDING) and autopilot_scale < 1.0:
                        target_speed *= autopilot_scale
                    if not math.isfinite(target_speed) or target_speed < 0.0:
                        target_speed = 0.0
                    if phase == MODE_CRUISE:
                        target_speed = _apply_min_safe_speed(
                            target_speed, float(self.rules.min_safe_speed_mps)
                        )
                    target_speed_mps = float(target_speed)
                    prev_speed = prev_state.get("speed_base_mps") if prev_state else None
                    if not isinstance(prev_speed, (int, float)) or not math.isfinite(prev_speed):
                        prev_speed = prev_state.get("speed_mps") if prev_state else None
                    if not isinstance(prev_speed, (int, float)) or not math.isfinite(prev_speed):
                        prev_speed = target_speed
                    if phase == MODE_CRUISE:
                        prev_speed = _apply_min_safe_speed(
                            prev_speed, float(self.rules.min_safe_speed_mps)
                        )
                    speed = target_speed
                    if delta_s > 0.0:
                        accel_mps2 = float(self.rules.accel_mps2)
                        if not math.isfinite(accel_mps2) or accel_mps2 <= 0.0:
                            accel_mps2 = 0.0
                        if accel_mps2 > 0.0:
                            speed = _approach_value(
                                float(prev_speed),
                                target_speed,
                                accel_mps2 * delta_s,
                            )
                    if phase == MODE_CRUISE:
                        speed = _apply_min_safe_speed(speed, float(self.rules.min_safe_speed_mps))
                    if delta_s > 0 and dist_m < flight.total_dist_m:
                        avg_speed = 0.5 * (float(prev_speed) + speed)
                        dist_m = min(flight.total_dist_m, dist_m + avg_speed * delta_s)
                        control.manual_dist_m = dist_m
                    pos_xy = _position_at_distance(flight.points_xy, flight.cum_dist_m, dist_m)
                    alt_m = _value_at_distance(flight.points_alt_m, flight.cum_dist_m, dist_m)
                    speed_mps = speed
                    heading_deg = _heading_at_distance(flight.points_xy, flight.cum_dist_m, dist_m)
                    if dist_m >= flight.total_dist_m:
                        if control.manual_arrival_s is None:
                            control.manual_arrival_s = self.sim_elapsed_s
                            control.manual_landing_alt_m = alt_m
                        landing_t = self.sim_elapsed_s - control.manual_arrival_s
                        if landing_t < landing_s:
                            mode = MODE_LANDING
                            phase = MODE_LANDING
                            ratio = min(1.0, landing_t / landing_s) if landing_s > 0 else 1.0
                            start_alt_m = control.manual_landing_alt_m
                            if not isinstance(start_alt_m, (int, float)) or not math.isfinite(
                                start_alt_m,
                            ):
                                start_alt_m = alt_m if math.isfinite(alt_m) else FLIGHT_ALT_M
                            alt_drop = max(0.0, float(start_alt_m) - VERTIPORT_ALT_M)
                            alt_m = float(start_alt_m) - alt_drop * ratio
                            pos_xy = flight.points_xy[-1]
                            speed_mps = 0.0
                        else:
                            mode = MODE_ENDED
                    else:
                        mode = MODE_CRUISE
                        phase = MODE_CRUISE
            else:
                dist_m = _distance_at_time_profile(profile, t_since_start)
                if flight.total_dist_m > 0:
                    dist_m = min(dist_m, flight.total_dist_m)
                pos_xy = _position_at_distance(flight.points_xy, flight.cum_dist_m, dist_m)
                alt_m = _altitude_at_time_profile(profile, t_since_start)
                speed_mps = _speed_at_time_profile(profile, t_since_start)
                heading_deg = _heading_at_distance(flight.points_xy, flight.cum_dist_m, dist_m)
                if phase == MODE_ENDED:
                    ops_metrics, _metrics_updated = self._update_flight_ops_metrics(
                        flight=flight,
                        mode=mode,
                        phase=phase,
                        elapsed_s=float(elapsed),
                        wait_s=float(wait_s),
                        dist_m=float(dist_m),
                        speed_mps=float(speed_mps),
                        control=control,
                        force_update=ops_metrics_due,
                        finalize_arrival=True,
                    )
                    statuses.append(
                        {
                            "id": flight.flight_id,
                            "name": flight.name,
                            "mode": mode,
                            "speed_mps": 0.0,
                            "altitude_m": VERTIPORT_ALT_M,
                            "from": flight.origin,
                            "to": flight.destination,
                            **self._build_ops_metrics_payload(
                                ops_metrics,
                                True,
                            ),
                        }
                    )
                    self.flight_controls.pop(flight.flight_id, None)
                    self.flight_state.pop(flight.flight_id, None)
                    continue
            if mode == MODE_ENDED:
                ops_metrics, _metrics_updated = self._update_flight_ops_metrics(
                    flight=flight,
                    mode=mode,
                    phase=phase,
                    elapsed_s=float(elapsed),
                    wait_s=float(wait_s),
                    dist_m=float(dist_m),
                    speed_mps=float(speed_mps),
                    control=control,
                    force_update=ops_metrics_due,
                    finalize_arrival=True,
                )
                statuses.append(
                    {
                        "id": flight.flight_id,
                        "name": flight.name,
                        "mode": mode,
                        "speed_mps": 0.0,
                        "altitude_m": VERTIPORT_ALT_M,
                        "from": flight.origin,
                        "to": flight.destination,
                        **self._build_ops_metrics_payload(
                            ops_metrics,
                            True,
                        ),
                    }
                )
                self.flight_controls.pop(flight.flight_id, None)
                self.flight_state.pop(flight.flight_id, None)
                continue
            track_heading_deg = heading_deg
            wind_state: dict[str, float] = {}
            base_speed_mps = float(speed_mps)
            if target_speed_mps is None:
                target_speed_mps = float(flight.speed_mps)
                if control and isinstance(control.speed_override_mps, (int, float)):
                    if math.isfinite(control.speed_override_mps):
                        target_speed_mps = float(control.speed_override_mps)
            if (
                isinstance(dist_m, (int, float))
                and isinstance(heading_deg, (int, float))
                and math.isfinite(dist_m)
                and math.isfinite(heading_deg)
            ):
                pos_xy, speed_mps, heading_deg, track_heading_deg, wind_state = (
                    self._apply_wind_influence(
                        flight.flight_id,
                        mode,
                        pos_xy,
                        float(dist_m),
                        float(speed_mps),
                        float(heading_deg),
                        float(delta_s),
                        flight.points_xy,
                        flight.cum_dist_m,
                        float(flight.total_dist_m),
                    )
                )
            if mode == MODE_CRUISE:
                speed_mps = _apply_min_safe_speed(
                    speed_mps, float(self.rules.min_safe_speed_mps)
                )
                base_speed_mps = _apply_min_safe_speed(
                    base_speed_mps, float(self.rules.min_safe_speed_mps)
                )
                if isinstance(target_speed_mps, (int, float)) and math.isfinite(target_speed_mps):
                    target_speed_mps = _apply_min_safe_speed(
                        float(target_speed_mps),
                        float(self.rules.min_safe_speed_mps),
                    )
            lateral_dev_m = 0.0
            if wind_state:
                cross_value = wind_state.get("wind_cross_m")
                if isinstance(cross_value, (int, float)) and math.isfinite(cross_value):
                    lateral_dev_m = float(cross_value)
            planned_alt_m = None
            if (
                isinstance(dist_m, (int, float))
                and flight.points_alt_m
                and flight.cum_dist_m
                and math.isfinite(dist_m)
            ):
                planned_alt_m = _value_at_distance(
                    flight.points_alt_m,
                    flight.cum_dist_m,
                    float(dist_m),
                )
            vertical_dev_m = 0.0
            if isinstance(planned_alt_m, (int, float)) and math.isfinite(planned_alt_m):
                if isinstance(alt_m, (int, float)) and math.isfinite(alt_m):
                    vertical_dev_m = float(alt_m) - float(planned_alt_m)
            lateral_rate_mps = 0.0
            vertical_rate_mps = 0.0
            if delta_s > 0.0 and prev_state:
                prev_lat = prev_state.get("lateral_dev_m")
                if isinstance(prev_lat, (int, float)) and math.isfinite(prev_lat):
                    lateral_rate_mps = (lateral_dev_m - float(prev_lat)) / float(delta_s)
                prev_ver = prev_state.get("vertical_dev_m")
                if isinstance(prev_ver, (int, float)) and math.isfinite(prev_ver):
                    vertical_rate_mps = (vertical_dev_m - float(prev_ver)) / float(delta_s)
            lon, lat = self.planner.projection.to_lonlat(pos_xy[0], pos_xy[1])
            route_from = None
            route_to = None
            segment = self._route_segment_for_distance(
                flight.path_nodes,
                flight.cum_dist_m,
                float(dist_m),
                flight.path_segment_idx,
            )
            if segment:
                route_from, route_to = segment
            battery_pct = 100.0
            battery_capacity_s = float(
                getattr(self.rules, "battery_capacity_s", BATTERY_CAPACITY_S)
            )
            if not math.isfinite(battery_capacity_s) or battery_capacity_s <= 0.0:
                battery_capacity_s = 0.0
            if battery_capacity_s > 0.0:
                airborne_elapsed = max(0.0, elapsed - wait_s)
                battery_pct = 100.0 * (1.0 - airborne_elapsed / battery_capacity_s)
                battery_pct = max(0.0, min(100.0, battery_pct))
            if battery_pct <= 0.0:
                fail_reason = "Battery 0"
                ops_metrics, _metrics_updated = self._update_flight_ops_metrics(
                    flight=flight,
                    mode=MODE_FAILED,
                    phase=phase,
                    elapsed_s=float(elapsed),
                    wait_s=float(wait_s),
                    dist_m=float(dist_m),
                    speed_mps=float(speed_mps),
                    control=control,
                    force_update=True,
                    finalize_arrival=False,
                )
                if self.add_failure_event:
                    self.add_failure_event(
                        {
                            "time_s": float(self.sim_elapsed_s),
                            "flight_id": flight.flight_id,
                            "flight_name": flight.name,
                            "origin": flight.origin,
                            "destination": flight.destination,
                            "lon": lon,
                            "lat": lat,
                            "altitude_m": alt_m,
                            "battery_pct": battery_pct,
                            "reason": fail_reason,
                        }
                    )
                statuses.append(
                    {
                        "id": flight.flight_id,
                        "name": flight.name,
                        "mode": MODE_FAILED,
                        "speed_mps": 0.0,
                        "altitude_m": alt_m,
                        "battery_pct": battery_pct,
                        "reason": fail_reason,
                        "from": flight.origin,
                        "to": flight.destination,
                        **self._build_ops_metrics_payload(
                            ops_metrics,
                            True,
                        ),
                    }
                )
                self.flight_controls.pop(flight.flight_id, None)
                self.flight_state.pop(flight.flight_id, None)
                continue
            ops_metrics, metrics_updated = self._update_flight_ops_metrics(
                flight=flight,
                mode=mode,
                phase=phase,
                elapsed_s=float(elapsed),
                wait_s=float(wait_s),
                dist_m=float(dist_m),
                speed_mps=float(speed_mps),
                control=control,
                force_update=ops_metrics_due,
                finalize_arrival=False,
            )
            ops_payload = self._build_ops_metrics_payload(ops_metrics, metrics_updated)
            positions.append(
                {
                    "id": flight.flight_id,
                    "lon": lon,
                    "lat": lat,
                    "altitude_m": alt_m,
                    "name": flight.name,
                    "from": flight.origin,
                    "to": flight.destination,
                    "route_from": route_from,
                    "route_to": route_to,
                    "risk": str(prev_risk),
                    "risk_level": prev_risk,
                    "risk_reason": prev_reason,
                    "speed_mps": speed_mps,
                    "speed_target_mps": target_speed_mps,
                    "lateral_dev_m": lateral_dev_m,
                    "vertical_dev_m": vertical_dev_m,
                    "lateral_rate_mps": lateral_rate_mps,
                    "vertical_rate_mps": vertical_rate_mps,
                    "battery_pct": battery_pct,
                    "icon": flight.icon_id,
                    "mode": mode,
                    "heading_deg": heading_deg,
                    "track_heading_deg": track_heading_deg,
                    **ops_payload,
                }
            )
            statuses.append(
                {
                    "id": flight.flight_id,
                    "name": flight.name,
                    "mode": mode,
                    "speed_mps": speed_mps,
                    "altitude_m": alt_m,
                    "from": flight.origin,
                    "to": flight.destination,
                    **ops_payload,
                }
            )
            self.flight_state[flight.flight_id] = {
                "phase": phase,
                "dist_m": dist_m,
                "pos_xy": pos_xy,
                "heading_deg": heading_deg,
                "track_heading_deg": track_heading_deg,
                "alt_m": alt_m,
                "speed_mps": speed_mps,
                "speed_base_mps": base_speed_mps,
                "speed_target_mps": target_speed_mps,
                "lateral_dev_m": lateral_dev_m,
                "vertical_dev_m": vertical_dev_m,
                "lateral_rate_mps": lateral_rate_mps,
                "vertical_rate_mps": vertical_rate_mps,
                "battery_pct": battery_pct,
                "risk_level": prev_risk,
                "risk_reason": prev_reason,
                **ops_payload,
            }
            if wind_state:
                self.flight_state[flight.flight_id].update(wind_state)
            active_flights.append(flight)
        self.flights = active_flights
        positions_by_id = {item["id"]: item for item in positions if "id" in item}
        interval_s = self.rules.risk_update_interval_s
        if not isinstance(interval_s, (int, float)) or not math.isfinite(interval_s):
            interval_s = RISK_UPDATE_INTERVAL_S
        interval_s = max(0.0, float(interval_s))
        update_risk = (
            self.last_risk_update_s is None
            or self.sim_elapsed_s - self.last_risk_update_s >= interval_s
        )
        if update_risk:
            risk_levels = self._compute_risk_levels(active_flights)
            self.last_risk_update_s = self.sim_elapsed_s
            for flight in active_flights:
                info = risk_levels.get(flight.flight_id, {"level": 0, "reason": ""})
                level = int(info.get("level", 0))
                reason = str(info.get("reason", ""))
                flight.risk = str(level)
                entry = positions_by_id.get(flight.flight_id)
                if entry is not None:
                    entry["risk_level"] = level
                    entry["risk"] = str(level)
                    entry["risk_reason"] = reason
                state = self.flight_state.get(flight.flight_id)
                if state is not None:
                    state["risk_level"] = level
                    state["risk_reason"] = reason
        else:
            for flight in active_flights:
                state = self.flight_state.get(flight.flight_id)
                level = int(state.get("risk_level", 0)) if state else 0
                reason = str(state.get("risk_reason", "")) if state else ""
                entry = positions_by_id.get(flight.flight_id)
                if entry is not None:
                    entry["risk_level"] = level
                    entry["risk"] = str(level)
                    entry["risk_reason"] = reason
        self.update_map(positions)
        self.update_dashboard_status(statuses)

    # --- Schedule / state reset ---
    def _reset_state(self) -> None:
        self.update_map([])
        self.flight_state.clear()
        self.flight_controls.clear()
        self.flight_ops_metrics.clear()
        self.last_positions_time_s = None
        self.last_risk_update_s = None
        self.last_ops_metrics_update_s = None

    def _spawn_ready_flights(self) -> None:
        while self.schedule_index < len(self.schedule):
            schedule = self.schedule[self.schedule_index]
            if schedule.start_offset_s > self.sim_elapsed_s:
                break
            self.pending_schedule.append(schedule)
            self.schedule_index += 1

        if not self.pending_schedule:
            return

        active_aircraft_ids = {
            str(flight.aircraft_id).strip()
            for flight in self.flights
            if str(flight.aircraft_id).strip()
        }
        next_pending: list[FlightSchedule] = []
        for schedule in self.pending_schedule:
            spawn_time_s = float(self.sim_elapsed_s)
            aircraft_id = str(schedule.aircraft_id or "").strip()
            if aircraft_id:
                if aircraft_id in active_aircraft_ids:
                    next_pending.append(schedule)
                    continue
                available_time = self.next_available_by_aircraft.get(aircraft_id, -1.0)
                if spawn_time_s < available_time:
                    next_pending.append(schedule)
                    continue
            takeoff_spacing = max(1, int(self.rules.takeoff_s))
            origin = schedule.origin
            origin_kind = ""
            port = self.planner.ports.get(origin)
            if port:
                origin_kind = str(getattr(port, "kind", "") or "").lower()
            if origin_kind == "hub":
                takeoff_spacing = max(1, int(takeoff_spacing / 2))
            flight = self._create_flight_from_schedule(schedule)
            if not flight:
                next_pending.append(schedule)
                continue
            planned_wait_s = max(0.0, float(getattr(schedule, "preflight_wait_s", PREFLIGHT_WAIT_S)))
            if isinstance(schedule.planned_takeoff_offset_s, int):
                planned_wait_s = max(
                    planned_wait_s,
                    float(schedule.planned_takeoff_offset_s - schedule.start_offset_s),
                )
            planned_takeoff_s = spawn_time_s + planned_wait_s
            ready_time = self.next_takeoff_by_origin.get(origin, -1.0)
            actual_takeoff_s = max(planned_takeoff_s, ready_time)
            actual_wait_s = max(0.0, actual_takeoff_s - spawn_time_s)
            flight.start_offset_s = int(spawn_time_s)
            flight.preflight_wait_s = actual_wait_s
            flight.scheduled_takeoff_s = int(planned_takeoff_s)
            flight.actual_takeoff_s = int(actual_takeoff_s)
            flight.std_s = float(spawn_time_s)
            flight.sta_s = float(spawn_time_s + actual_wait_s + float(flight.total_time_s))
            flight.ata_s = None
            initial_remaining_s = max(0.0, float(flight.sta_s) - float(self.sim_elapsed_s))
            self.flight_ops_metrics[flight.flight_id] = {
                "std_s": float(flight.std_s),
                "sta_s": float(flight.sta_s),
                "eta_s": float(flight.sta_s),
                "ata_s": None,
                "delay_s": 0.0,
                "tti": 1.0,
                "remaining_dist_m": float(flight.total_dist_m),
                "remaining_time_s": initial_remaining_s,
                "updated_s": float(self.sim_elapsed_s),
            }
            route_label = "-"
            segment = self._route_segment_for_distance(
                flight.path_nodes,
                flight.cum_dist_m,
                0.0,
                flight.path_segment_idx,
            )
            if segment:
                route_label = f"{segment[0]} -> {segment[1]}"
            self.flights.append(flight)
            self.add_dashboard_row(
                [
                    flight.name,
                    flight.risk,
                    "0.0 m/s",
                    "100%",
                    "-",
                    "-",
                    MODE_WAITING,
                    f"{VERTIPORT_ALT_M:.0f} m",
                    flight.origin,
                    flight.destination,
                    route_label,
                ]
            )
            self.next_takeoff_by_origin[origin] = actual_takeoff_s + takeoff_spacing
            if aircraft_id:
                active_aircraft_ids.add(aircraft_id)
                turnaround_s = max(0.0, float(getattr(schedule, "turnaround_s", DEFAULT_TURNAROUND_S)))
                self.next_available_by_aircraft[aircraft_id] = (
                    actual_takeoff_s + float(flight.total_time_s) + turnaround_s
                )
        self.pending_schedule = next_pending

    def _create_flight_from_schedule(self, schedule: FlightSchedule) -> Flight | None:
        if len(self.port_names) < 2:
            return None
        planned_schedule = bool(schedule.aircraft_id or schedule.local_id or schedule.source_file)

        def pick_destination(start: str) -> str | None:
            for _ in range(10):
                candidate = random.choice(self.port_names)
                if candidate != start:
                    return candidate
            for candidate in self.port_names:
                if candidate != start:
                    return candidate
            return None

        def pick_new_pair() -> tuple[str, str] | None:
            start = random.choice(self.port_names)
            dest = pick_destination(start)
            if dest is None:
                return None
            return start, dest

        origin = schedule.origin
        destination = schedule.destination
        for _ in range(6):
            if origin not in self.port_names:
                if planned_schedule:
                    return None
                pair = pick_new_pair()
                if not pair:
                    return None
                origin, destination = pair
            if destination not in self.port_names or destination == origin:
                if planned_schedule and destination == schedule.destination:
                    return None
                destination = pick_destination(origin)
                if destination is None:
                    return None
            try:
                result = self.planner.find_route(origin, destination)
            except Exception:
                if planned_schedule:
                    return None
                pair = pick_new_pair()
                if not pair:
                    return None
                origin, destination = pair
                continue
            geometry = result.points
            if len(geometry) < 2:
                if planned_schedule:
                    return None
                pair = pick_new_pair()
                if not pair:
                    return None
                origin, destination = pair
                continue
            speed_mps = self.rules.speed_mps
            points_xy, points_alt_m, cum_dist_m, segment_map = self._build_flight_path(
                list(geometry),
                list(result.path),
            )
            if len(points_xy) < 2 or not cum_dist_m:
                if planned_schedule:
                    return None
                pair = pick_new_pair()
                if not pair:
                    return None
                origin, destination = pair
                continue
            total_dist_m = float(cum_dist_m[-1])
            if total_dist_m <= 0:
                if planned_schedule:
                    return None
                pair = pick_new_pair()
                if not pair:
                    return None
                origin, destination = pair
                continue
            profile = _build_flight_profile(total_dist_m, speed_mps, self.rules)
            flight_id = schedule.schedule_id
            aircraft_id = str(schedule.aircraft_id or "").strip()
            name = aircraft_id or f"F{flight_id:05d}"
            icon_id = self.aircraft_icons.get(aircraft_id, "")
            if not icon_id:
                icon_id = random.choice(PLANE_ICON_IDS)
                if aircraft_id:
                    self.aircraft_icons[aircraft_id] = icon_id
            preflight_wait_s = max(0.0, float(getattr(schedule, "preflight_wait_s", PREFLIGHT_WAIT_S)))
            planned_takeoff_s = int(schedule.start_offset_s + preflight_wait_s)
            if isinstance(schedule.planned_takeoff_offset_s, int):
                planned_takeoff_s = int(schedule.planned_takeoff_offset_s)
            return Flight(
                flight_id=flight_id,
                name=name,
                origin=origin,
                destination=destination,
                risk=schedule.risk,
                icon_id=icon_id,
                start_offset_s=schedule.start_offset_s,
                speed_mps=speed_mps,
                points_xy=points_xy,
                points_alt_m=points_alt_m,
                cum_dist_m=cum_dist_m,
                total_dist_m=total_dist_m,
                accel_time_s=profile.accel_time_s,
                cruise_time_s=profile.cruise_time_s,
                total_time_s=profile.total_time_s,
                peak_speed_mps=profile.peak_speed_mps,
                path_nodes=list(result.path),
                path_segment_idx=segment_map,
                profile=profile,
                preflight_wait_s=preflight_wait_s,
                aircraft_id=aircraft_id,
                local_id=str(schedule.local_id or ""),
                dep_fato_no=str(schedule.dep_fato_no or ""),
                dep_gate_no=str(schedule.dep_gate_no or ""),
                arr_fato_no=str(schedule.arr_fato_no or ""),
                arr_gate_no=str(schedule.arr_gate_no or ""),
                source_file=str(schedule.source_file or ""),
                scheduled_takeoff_s=planned_takeoff_s,
            )
        return None

    def _generate_schedule(self) -> list[FlightSchedule]:
        if self.has_flightplan_schedule():
            return [replace(item) for item in self.flightplan_schedule]
        selection = self.get_traffic_selection()
        if not selection:
            return []
        count = TRAFFIC_LEVELS.get(selection)
        if not count:
            return []
        if len(self.port_names) < 2:
            return []

        window_s = int(self.sim_duration_s)
        if window_s <= 0:
            return []

        return build_random_schedule(
            port_names=self.port_names,
            count=int(count),
            window_s=window_s,
            make_schedule=lambda schedule_id, start_offset_s, origin, destination: FlightSchedule(
                schedule_id=int(schedule_id),
                risk="0",
                start_offset_s=int(start_offset_s),
                origin=str(origin),
                destination=str(destination),
            ),
        )

    # --- Public helpers ---
    def build_prediction_path(self, name: str, horizon_s: float = 20.0) -> list[list[float]] | None:
        flight = self.get_flight_by_name(name)
        if not flight:
            return None
        state = self.flight_state.get(flight.flight_id)
        if not state:
            return None
        phase = state.get("phase")
        if phase == MODE_ENDED:
            return None
        control = self.flight_controls.get(flight.flight_id)
        if control and control.hold_active:
            return None
        dist_m = state.get("dist_m")
        if not isinstance(dist_m, (int, float)):
            return None
        speed_value = None
        speed_candidates = (
            state.get("speed_base_mps"),
            state.get("speed_target_mps"),
            state.get("speed_mps"),
            flight.speed_mps,
        )
        for candidate in speed_candidates:
            if isinstance(candidate, (int, float)) and math.isfinite(candidate) and candidate > 0:
                speed_value = float(candidate)
                break
        if speed_value is None:
            return None
        projection = self.planner.projection
        path_xy = self._build_prediction_path_xy_wind(
            flight,
            float(dist_m),
            speed_value,
            float(horizon_s),
        )
        if len(path_xy) < 2:
            return None
        points: list[list[float]] = []
        for pos_xy in path_xy:
            lon, lat = projection.to_lonlat(pos_xy[0], pos_xy[1])
            points.append([lon, lat])
        return points

    def build_hold_path(self, name: str) -> list[list[float]] | None:
        flight = self.get_flight_by_name(name)
        if not flight:
            return None
        control = self.flight_controls.get(flight.flight_id)
        if not control or not control.hold_active or not control.hold_center_xy:
            return None
        radius_m = float(control.hold_radius_m)
        if radius_m <= 0:
            return None
        center_x, center_y = control.hold_center_xy
        radius_km = radius_m / 1000.0
        steps = 36
        projection = self.planner.projection
        points: list[list[float]] = []
        for idx in range(steps + 1):
            angle = (2.0 * math.pi * idx) / steps
            x = center_x + radius_km * math.cos(angle)
            y = center_y + radius_km * math.sin(angle)
            lon, lat = projection.to_lonlat(x, y)
            points.append([lon, lat])
        return points
