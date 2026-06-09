"""UAM Flight Simulator — Flight dynamics engine.

Samples position, altitude, speed, and heading at each simulation tick,
applying kinematic profiles and wind perturbation.  This is the core
physics loop extracted from UATM sim_core.py.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

from .types import (
    LLA,
    FlightMode,
    FlightTrajectoryPoint,
    Phase,
    SegmentProfile,
    SimulationConfig,
)
from .geo import LocalProjection, XY, distance_xy, heading_between, wrap_heading
from .wind_model import WindModel, WindVector
from .flight_profile import (
    SegmentKinematics,
    find_segment_at_time,
    total_flight_time,
)

_LOCKED_XY_PHASES = {Phase.B.value, Phase.J.value}


@dataclass
class _VehicleState:
    x_m: float
    y_m: float
    alt_m: float
    speed_mps: float
    heading_deg: float
    track_heading_deg: float
    vertical_speed_mps: float = 0.0


def _exp_smooth_alpha(dt: float, tau: float) -> float:
    if tau <= 0.0:
        return 1.0
    return 1.0 - math.exp(-dt / tau)


def _phase_to_flight_mode(phase: Phase) -> FlightMode:
    return {
        Phase.A: FlightMode.GATE_TAXI,
        Phase.B: FlightMode.VERTICAL_CLIMB,
        Phase.C: FlightMode.TRANSITION,
        Phase.D: FlightMode.TRANSITION,
        Phase.E: FlightMode.CLIMB,
        Phase.F: FlightMode.CRUISE,
        Phase.G: FlightMode.DESCENT,
        Phase.H: FlightMode.APPROACH,
        Phase.I: FlightMode.APPROACH,
        Phase.J: FlightMode.VERTICAL_DESCENT,
        Phase.K: FlightMode.GATE_IN,
    }.get(phase, FlightMode.CRUISE)


def _interpolate_on_segment(
    seg_profile: SegmentProfile,
    seg_kin: SegmentKinematics,
    t_in_seg: float,
) -> Tuple[LLA, float, float]:
    """Interpolate position along a segment at local time offset.

    Returns (lla, distance_within_segment, speed_mps).
    """
    t = max(0.0, min(seg_kin.duration_s, t_in_seg))
    frac = t / seg_kin.duration_s if seg_kin.duration_s > 0 else 1.0

    if seg_kin.is_vertical:
        # Vertical climb/descent: stay at same lat/lon, interpolate alt
        alt = seg_profile.start_lla.alt + (
            seg_profile.end_lla.alt - seg_profile.start_lla.alt
        ) * frac
        lla = LLA(
            lat=seg_profile.start_lla.lat,
            lon=seg_profile.start_lla.lon,
            alt=alt,
        )
        speed = abs(seg_kin.climb_rate_mps)
        dist = seg_kin.distance_m * frac
        return lla, dist, speed

    # Horizontal segment: compute distance travelled using kinematics
    if abs(seg_kin.accel_mps2) > 0.01:
        # s = v0*t + 0.5*a*t^2, but capped at segment distance
        accel_time = abs(seg_kin.target_speed_mps - seg_kin.entry_speed_mps) / abs(seg_kin.accel_mps2) if abs(seg_kin.accel_mps2) > 0 else 0.0
        if t <= accel_time:
            dist = seg_kin.entry_speed_mps * t + 0.5 * seg_kin.accel_mps2 * t * t
            speed = seg_kin.entry_speed_mps + seg_kin.accel_mps2 * t
        else:
            # Accel phase distance
            dist_accel = seg_kin.entry_speed_mps * accel_time + 0.5 * seg_kin.accel_mps2 * accel_time * accel_time
            # Cruise phase
            t_cruise = t - accel_time
            dist = dist_accel + seg_kin.target_speed_mps * t_cruise
            speed = seg_kin.target_speed_mps
    else:
        speed = seg_kin.entry_speed_mps if seg_kin.entry_speed_mps > 0 else seg_kin.target_speed_mps
        dist = speed * t

    dist = max(0.0, min(seg_kin.distance_m, dist))
    speed = max(0.0, speed)

    # Look up position along the densified polyline
    lla = _position_on_polyline(seg_profile.points_lla, seg_profile.cum_dist_m, dist)
    return lla, dist, speed


def _position_on_polyline(
    points: List[LLA],
    cum_dist: List[float],
    dist_m: float,
) -> LLA:
    """Interpolate LLA position along a polyline at a given distance."""
    if not points:
        return LLA(0, 0, 0)
    if dist_m <= 0 or len(points) == 1:
        return points[0]
    if dist_m >= cum_dist[-1]:
        return points[-1]

    # Binary search for segment
    lo, hi = 0, len(cum_dist) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if cum_dist[mid] < dist_m:
            lo = mid + 1
        else:
            hi = mid
    idx = max(1, lo)
    idx = min(idx, len(points) - 1)

    seg_start = cum_dist[idx - 1]
    seg_len = cum_dist[idx] - seg_start
    if seg_len <= 0:
        return points[idx]
    ratio = (dist_m - seg_start) / seg_len

    p1 = points[idx - 1]
    p2 = points[idx]
    return LLA(
        lat=p1.lat + (p2.lat - p1.lat) * ratio,
        lon=p1.lon + (p2.lon - p1.lon) * ratio,
        alt=p1.alt + (p2.alt - p1.alt) * ratio,
    )


def _heading_on_polyline(
    points: List[LLA],
    cum_dist: List[float],
    dist_m: float,
    proj: LocalProjection,
) -> float:
    """Compute heading at a point along a polyline."""
    if len(points) < 2:
        return 0.0

    # Look ahead a small distance for smoother heading
    lookahead = 30.0  # metres
    d0 = max(0.0, dist_m - lookahead)
    d1 = min(cum_dist[-1], dist_m + lookahead)
    if d1 - d0 < 1.0:
        d0 = max(0.0, dist_m)
        d1 = min(cum_dist[-1], dist_m + 1.0)

    p0 = _position_on_polyline(points, cum_dist, d0)
    p1 = _position_on_polyline(points, cum_dist, d1)

    xy0 = proj.lla_to_xy(p0)
    xy1 = proj.lla_to_xy(p1)
    return heading_between(xy0, xy1)


def _signed_heading_delta_deg(value_deg: float, reference_deg: float) -> float:
    return ((float(value_deg) - float(reference_deg) + 180.0) % 360.0) - 180.0


def _move_towards(value: float, target: float, max_step: float) -> float:
    step = abs(float(max_step))
    delta = float(target) - float(value)
    if abs(delta) <= step:
        return float(target)
    return float(value) + math.copysign(step, delta)


def _clamp_float(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


def _config_float(config: SimulationConfig, name: str, default: float) -> float:
    try:
        value = float(getattr(config, name, default))
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(value):
        return float(default)
    return value


def _slew_heading(value_deg: float, target_deg: float, max_delta_deg: float) -> float:
    delta = _signed_heading_delta_deg(target_deg, value_deg)
    limit = abs(float(max_delta_deg))
    if abs(delta) <= limit:
        return wrap_heading(target_deg)
    return wrap_heading(value_deg + math.copysign(limit, delta))


def _xy_to_m(xy: XY) -> Tuple[float, float]:
    return float(xy.x) * 1000.0, float(xy.y) * 1000.0


def _lla_xy_m(proj: LocalProjection, lla: LLA) -> Tuple[float, float]:
    return _xy_to_m(proj.lla_to_xy(lla))


def _xy_m_to_lla(proj: LocalProjection, x_m: float, y_m: float, alt_m: float) -> LLA:
    return proj.xy_to_lla(XY(float(x_m) / 1000.0, float(y_m) / 1000.0), float(alt_m))


def _distance_xy_m(ax_m: float, ay_m: float, bx_m: float, by_m: float) -> float:
    return math.hypot(float(bx_m) - float(ax_m), float(by_m) - float(ay_m))


def _heading_between_xy_m(ax_m: float, ay_m: float, bx_m: float, by_m: float) -> float:
    return heading_between(
        XY(float(ax_m) / 1000.0, float(ay_m) / 1000.0),
        XY(float(bx_m) / 1000.0, float(by_m) / 1000.0),
    )


def _is_vertical_segment(seg_profile: SegmentProfile, proj: LocalProjection) -> bool:
    if seg_profile.phase in (Phase.B, Phase.J):
        return True
    start_x, start_y = _lla_xy_m(proj, seg_profile.start_lla)
    end_x, end_y = _lla_xy_m(proj, seg_profile.end_lla)
    return _distance_xy_m(start_x, start_y, end_x, end_y) < 0.5


def _rate_limit_heading_series(
    values: List[float],
    points: List[FlightTrajectoryPoint],
    max_rate_deg_s: float,
) -> List[float]:
    if len(values) < 2 or max_rate_deg_s <= 0.0:
        return [wrap_heading(value) for value in values]

    reset_phases = {Phase.A.value, Phase.B.value, Phase.J.value, Phase.K.value}
    limited: List[float] = [wrap_heading(values[0])]

    for idx in range(1, len(values)):
        target = wrap_heading(values[idx])
        point = points[idx]
        if point.phase in reset_phases:
            limited.append(target)
            continue

        prev = limited[-1]
        dt = max(0.0, float(point.time_s) - float(points[idx - 1].time_s))
        max_delta = max_rate_deg_s * dt
        delta = _signed_heading_delta_deg(target, prev)
        if max_delta > 0.0:
            delta = max(-max_delta, min(max_delta, delta))
        limited.append(wrap_heading(prev + delta))

    return limited


def _ema_pass(values: List[float], alpha: float, locked: List[bool]) -> List[float]:
    if not values:
        return []
    out = list(values)
    prev = float(values[0])
    out[0] = prev
    for i in range(1, len(values)):
        current = float(values[i])
        if locked[i]:
            prev = current
            out[i] = current
            continue
        prev = prev + alpha * (current - prev)
        out[i] = prev
    return out


def _smooth_series_bidirectional(
    values: List[float],
    alpha: float,
    passes: int,
    locked: List[bool],
) -> List[float]:
    if len(values) < 3:
        return list(values)
    out = list(values)
    loop_count = max(1, int(passes))
    for _ in range(loop_count):
        forward = _ema_pass(out, alpha, locked)
        backward = list(reversed(_ema_pass(list(reversed(forward)), alpha, list(reversed(locked)))))
        out = backward
        for i, is_locked in enumerate(locked):
            if is_locked:
                out[i] = values[i]
    return out


def _smooth_series_by_distance(
    values: List[float],
    cum_dist_m: List[float],
    radius_m: float,
    passes: int,
    locked: List[bool],
) -> List[float]:
    if len(values) < 3 or radius_m <= 0.0:
        return list(values)

    out = list(values)
    original = list(values)
    loop_count = max(1, int(passes))

    for _ in range(loop_count):
        prefix_sum = [0.0]
        for value in out:
            prefix_sum.append(prefix_sum[-1] + float(value))

        next_out = list(out)
        for i, center in enumerate(cum_dist_m):
            if locked[i]:
                next_out[i] = original[i]
                continue
            lo = bisect_left(cum_dist_m, center - radius_m)
            hi = bisect_right(cum_dist_m, center + radius_m) - 1
            if hi <= lo:
                next_out[i] = out[i]
                continue
            total = prefix_sum[hi + 1] - prefix_sum[lo]
            count = hi - lo + 1
            next_out[i] = total / max(1, count)

        out = next_out
        for i, is_locked in enumerate(locked):
            if is_locked:
                out[i] = original[i]

    return out


def _smoothed_track_heading_series(
    xs_km: List[float],
    ys_km: List[float],
    original: List[FlightTrajectoryPoint],
    lookahead_m: float,
) -> List[float]:
    count = len(original)
    if count < 2:
        return [p.track_heading_deg for p in original]
    lookahead_idx = max(1, int(round(max(1.0, lookahead_m) / 20.0)))
    result: List[float] = []
    xy_points = [XY(xs_km[i], ys_km[i]) for i in range(count)]
    for i, point in enumerate(original):
        if point.phase in _LOCKED_XY_PHASES:
            result.append(point.track_heading_deg)
            continue
        lo = max(0, i - lookahead_idx)
        hi = min(count - 1, i + lookahead_idx)
        if lo == hi:
            result.append(point.track_heading_deg)
            continue
        result.append(heading_between(xy_points[lo], xy_points[hi]))
    return result


def _segment_nominal_heading(
    seg_profile: SegmentProfile,
    proj: LocalProjection,
    *,
    prefer_end: bool,
) -> Optional[float]:
    total_dist = float(seg_profile.cum_dist_m[-1]) if seg_profile.cum_dist_m else 0.0
    if total_dist > 1e-3 and len(seg_profile.points_lla) >= 2:
        sample_dist = total_dist if prefer_end else 0.0
        return _heading_on_polyline(seg_profile.points_lla, seg_profile.cum_dist_m, sample_dist, proj)

    start_xy = proj.lla_to_xy(seg_profile.start_lla)
    end_xy = proj.lla_to_xy(seg_profile.end_lla)
    if distance_xy(start_xy, end_xy) > 1e-6:
        return heading_between(start_xy, end_xy)
    return None


def _resolve_vertical_segment_heading(
    segments: List[SegmentProfile],
    seg_idx: int,
    proj: LocalProjection,
) -> float:
    seg = segments[seg_idx]
    if seg.target_heading_deg is not None:
        return float(seg.target_heading_deg)

    search_specs: List[tuple[range, bool]]
    if seg.phase == Phase.B:
        search_specs = [
            (range(seg_idx + 1, len(segments)), False),
            (range(seg_idx - 1, -1, -1), True),
        ]
    else:
        search_specs = [
            (range(seg_idx - 1, -1, -1), True),
            (range(seg_idx + 1, len(segments)), False),
        ]

    for indices, prefer_end in search_specs:
        for idx in indices:
            heading = _segment_nominal_heading(segments[idx], proj, prefer_end=prefer_end)
            if heading is not None:
                return float(heading)
    return 0.0


def _build_vertical_heading_overrides(
    segments: List[SegmentProfile],
    proj: LocalProjection,
) -> Dict[int, float]:
    overrides: Dict[int, float] = {}
    for idx, seg in enumerate(segments):
        if seg.phase not in (Phase.B, Phase.J):
            continue
        overrides[idx] = _resolve_vertical_segment_heading(segments, idx, proj)
    return overrides


def _smooth_trajectory_points(
    points: List[FlightTrajectoryPoint],
    proj: LocalProjection,
    config: SimulationConfig,
) -> List[FlightTrajectoryPoint]:
    if not config.trajectory_smoothing_enabled or len(points) < 3:
        return points

    dt = max(1e-3, float(config.tick_s))
    alpha = _exp_smooth_alpha(dt, float(config.trajectory_smoothing_tau_s))
    passes = max(1, int(config.trajectory_smoothing_passes))

    xs_km: List[float] = []
    ys_km: List[float] = []
    alts_m: List[float] = []
    crab_deg: List[float] = []
    locked_xy: List[bool] = []
    locked_alt: List[bool] = []
    cum_dist_m: List[float] = [0.0]
    for idx, point in enumerate(points):
        xy = proj.to_xy(point.lon, point.lat)
        xs_km.append(xy.x)
        ys_km.append(xy.y)
        alts_m.append(float(point.alt_m))
        crab_deg.append(_signed_heading_delta_deg(point.heading_deg, point.track_heading_deg))
        endpoint = idx == 0 or idx == len(points) - 1
        near_stationary = float(point.speed_mps) <= 0.2
        locked_xy.append(endpoint or near_stationary or point.phase in _LOCKED_XY_PHASES)
        locked_alt.append(endpoint or near_stationary or point.phase in _LOCKED_XY_PHASES)
        if idx > 0:
            prev_xy = XY(xs_km[idx - 1], ys_km[idx - 1])
            curr_xy = XY(xs_km[idx], ys_km[idx])
            cum_dist_m.append(cum_dist_m[-1] + distance_xy(prev_xy, curr_xy))

    turn_radius_m = float(getattr(config, "trajectory_turn_smoothing_radius_m", 0.0) or 0.0)
    smooth_x = _smooth_series_by_distance(xs_km, cum_dist_m, turn_radius_m, passes, locked_xy)
    smooth_y = _smooth_series_by_distance(ys_km, cum_dist_m, turn_radius_m, passes, locked_xy)
    smooth_alt = _smooth_series_bidirectional(alts_m, alpha, passes, locked_alt)
    smooth_crab = _smooth_series_bidirectional(crab_deg, alpha, passes, locked_alt)
    smooth_track = _smoothed_track_heading_series(
        smooth_x,
        smooth_y,
        points,
        float(config.trajectory_heading_lookahead_m),
    )
    preserve_vehicle_heading = bool(getattr(config, "vehicle_dynamics_enabled", False))

    raw_track_values: List[float] = []
    raw_heading_values: List[float] = []
    for idx, point in enumerate(points):
        if preserve_vehicle_heading or locked_xy[idx]:
            raw_track_values.append(float(point.track_heading_deg))
            raw_heading_values.append(float(point.heading_deg))
            continue
        track_heading = smooth_track[idx]
        heading = wrap_heading(track_heading + smooth_crab[idx])
        raw_track_values.append(wrap_heading(track_heading))
        raw_heading_values.append(wrap_heading(heading))

    max_heading_rate = float(getattr(config, "turn_rate_deg_s", 0.0) or 0.0)
    limited_track = _rate_limit_heading_series(raw_track_values, points, max_heading_rate)
    limited_heading = _rate_limit_heading_series(raw_heading_values, points, max_heading_rate)

    smoothed: List[FlightTrajectoryPoint] = []
    for idx, point in enumerate(points):
        if locked_xy[idx] and locked_alt[idx]:
            smoothed.append(point)
            continue
        lon, lat = proj.to_lonlat(smooth_x[idx], smooth_y[idx])
        if preserve_vehicle_heading or locked_xy[idx]:
            track_heading = float(point.track_heading_deg)
            heading = float(point.heading_deg)
        else:
            track_heading = limited_track[idx]
            heading = limited_heading[idx]
        smoothed.append(replace(
            point,
            lat=lat,
            lon=lon,
            alt_m=round(smooth_alt[idx], 2),
            heading_deg=round(heading, 2),
            track_heading_deg=round(wrap_heading(track_heading), 2),
        ))
    return smoothed


class DynamicsEngine:
    """Core flight dynamics engine.

    Supports two usage modes:

    1. **Batch** — ``generate_trajectory()`` runs the full simulation and
       returns a complete list of ``FlightTrajectoryPoint``.
    2. **Tick-by-tick** — call ``tick()`` repeatedly to advance one time
       step at a time and receive a single point (or ``None`` when done).
    """

    def __init__(
        self,
        segments: List[SegmentProfile],
        kinematics: List[SegmentKinematics],
        proj: LocalProjection,
        config: SimulationConfig,
        wind_model: Optional[WindModel] = None,
        start_clock: str = "09:00:00",
        month: int = 4,
    ) -> None:
        self.segments = segments
        self.kinematics = kinematics
        self.proj = proj
        self.config = config
        self.wind = wind_model
        self.start_clock = start_clock
        self.month = month

        # Parse start time to seconds
        parts = start_clock.split(":")
        self.start_time_s = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        self.total_time_s = total_flight_time(kinematics)

        # Wind accumulation state
        self._wind_cross_m = 0.0
        self._wind_along_m = 0.0
        self._prev_wind_e = 0.0
        self._prev_wind_n = 0.0
        self._prev_track_deg = 0.0
        self._vertical_heading_overrides = _build_vertical_heading_overrides(self.segments, self.proj)

        # Stepper state
        self._t = 0.0
        self._airborne_time = 0.0
        self._battery_pct = 100.0
        self._battery_consumed_kwh = 0.0
        self._battery_power_kw = 0.0
        self._energy_last_alt_m: Optional[float] = None
        self._finished = False
        self._vehicle_enabled = bool(getattr(config, "vehicle_dynamics_enabled", False))
        self._vehicle_segment_index = 0
        self._vehicle_waypoint_index = 1
        self._vehicle_state: Optional[_VehicleState] = None
        self._vehicle_end_emitted = False
        self._vehicle_max_time_s = (
            max(1.0, self.total_time_s)
            * max(1.0, float(getattr(config, "vehicle_max_sim_time_factor", 4.0) or 4.0))
            + max(0.0, float(getattr(config, "vehicle_max_extra_time_s", 300.0) or 300.0))
        )
        self._reset_energy_state()
        self._reset_vehicle_state()

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_finished(self) -> bool:
        return self._finished

    @property
    def current_time(self) -> float:
        return self._t

    @property
    def progress(self) -> float:
        """Return progress fraction 0.0 → 1.0."""
        if self.total_time_s <= 0:
            return 1.0
        return min(1.0, self._t / self.total_time_s)

    # ── Helpers ─────────────────────────────────────────────────

    def reset(self) -> None:
        """Reset engine state so the simulation can be re-run."""
        self._t = 0.0
        self._airborne_time = 0.0
        self._reset_energy_state()
        self._finished = False
        self._wind_cross_m = 0.0
        self._wind_along_m = 0.0
        self._prev_wind_e = 0.0
        self._prev_wind_n = 0.0
        self._prev_track_deg = 0.0
        self._vertical_heading_overrides = _build_vertical_heading_overrides(self.segments, self.proj)
        self._vehicle_segment_index = 0
        self._vehicle_waypoint_index = 1
        self._vehicle_end_emitted = False
        self._reset_vehicle_state()

    def _seconds_to_clock(self, total_s: float) -> str:
        s = int(total_s) % 86400
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"

    def _apply_wind(
        self,
        lla: LLA,
        speed_mps: float,
        heading_deg: float,
        sim_time_s: float,
        delta_s: float,
    ) -> Tuple[LLA, float, float, float, float, float]:
        """Apply wind perturbation.

        Returns (perturbed_lla, speed, heading, track_heading, wind_e, wind_n).
        """
        if not self.wind or not self.config.wind_enabled:
            return lla, speed_mps, heading_deg, heading_deg, 0.0, 0.0

        wv = self.wind.wind_at(lla.lon, lla.lat, sim_time_s, self.month)
        w_e = wv.u
        w_n = wv.v

        # Smooth wind
        if delta_s > 0:
            alpha = _exp_smooth_alpha(delta_s, 2.0)
            w_e = self._prev_wind_e + (w_e - self._prev_wind_e) * alpha
            w_n = self._prev_wind_n + (w_n - self._prev_wind_n) * alpha

        # Decompose into along-track and cross-track
        h_rad = math.radians(heading_deg)
        h_vec = (math.sin(h_rad), math.cos(h_rad))
        r_vec = (math.cos(h_rad), -math.sin(h_rad))

        w_along = w_e * h_vec[0] + w_n * h_vec[1]
        w_cross = w_e * r_vec[0] + w_n * r_vec[1]

        cross_gain = self.config.wind_cross_gain
        cross_return = self.config.wind_cross_return_s
        cross_max = self.config.wind_cross_max_m
        along_gain = self.config.wind_along_gain
        along_max = self.config.wind_along_max_mps

        if delta_s > 0:
            if cross_return > 0:
                self._wind_cross_m += (w_cross * cross_gain - self._wind_cross_m / cross_return) * delta_s
                self._wind_along_m += (w_along * along_gain - self._wind_along_m / cross_return) * delta_s
            else:
                self._wind_cross_m += w_cross * cross_gain * delta_s
                self._wind_along_m += w_along * along_gain * delta_s

        self._wind_cross_m = max(-cross_max, min(cross_max, self._wind_cross_m))

        # Perturb position by cross-track offset
        offset_km = self._wind_cross_m / 1000.0
        xy = self.proj.lla_to_xy(lla)
        xy_perturbed = XY(
            xy.x + r_vec[0] * offset_km,
            xy.y + r_vec[1] * offset_km,
        )
        perturbed = self.proj.xy_to_lla(xy_perturbed, lla.alt)

        # Speed perturbation from along-track wind
        speed_delta = max(-along_max, min(along_max, w_along * along_gain))
        speed_out = max(0.0, speed_mps + speed_delta)

        # Crab angle
        track_heading = heading_deg
        crab_max = self.config.wind_crab_max_deg
        if crab_max > 0 and speed_out > 0.1:
            crab = math.degrees(math.atan2(w_cross, max(speed_out, 1e-3)))
            crab = max(-crab_max, min(crab_max, crab))
            heading_out = wrap_heading(heading_deg + crab)
        else:
            heading_out = heading_deg

        self._prev_wind_e = w_e
        self._prev_wind_n = w_n
        self._prev_track_deg = track_heading

        return perturbed, speed_out, heading_out, track_heading, w_e, w_n

    # Vehicle follower -------------------------------------------------

    def _reset_vehicle_state(self) -> None:
        if not self.segments:
            self._vehicle_state = None
            return
        first = self.segments[0]
        x_m, y_m = _lla_xy_m(self.proj, first.start_lla)
        heading = self._initial_vehicle_heading()
        self._vehicle_state = _VehicleState(
            x_m=x_m,
            y_m=y_m,
            alt_m=float(first.start_lla.alt),
            speed_mps=0.0,
            heading_deg=wrap_heading(heading),
            track_heading_deg=wrap_heading(heading),
            vertical_speed_mps=0.0,
        )

    def _initial_vehicle_heading(self) -> float:
        for seg in self.segments:
            if seg.phase == Phase.B and seg.target_heading_deg is not None:
                return float(seg.target_heading_deg)
        for seg in self.segments:
            if seg.phase in (Phase.A, Phase.B, Phase.J, Phase.K):
                continue
            heading = _segment_nominal_heading(seg, self.proj, prefer_end=False)
            if heading is not None:
                return float(heading)
        for seg in self.segments:
            heading = _segment_nominal_heading(seg, self.proj, prefer_end=False)
            if heading is not None:
                return float(heading)
        return 0.0

    def _segment_target_speed(self, seg: SegmentProfile) -> float:
        target = max(0.0, float(seg.target_speed_mps))
        if seg.phase in (Phase.A, Phase.K):
            taxi_speed = max(0.0, float(self.config.taxi_speed_mps))
            return min(target, taxi_speed) if target > 0.0 else taxi_speed
        return target

    def _segment_exit_speed(self, seg_idx: int) -> float:
        if seg_idx >= len(self.segments) - 1:
            return 0.0
        next_seg = self.segments[seg_idx + 1]
        if _is_vertical_segment(next_seg, self.proj):
            return 0.0
        return self._segment_target_speed(next_seg)

    def _vertical_target_heading(self, seg_idx: int, seg: SegmentProfile) -> Optional[float]:
        if seg.target_heading_deg is not None:
            return float(seg.target_heading_deg)

        if seg.phase == Phase.B:
            return None
        elif seg.phase == Phase.J:
            search = range(seg_idx - 1, -1, -1)
            prefer_end = True
        else:
            return None

        for idx in search:
            candidate = self.segments[idx]
            if _is_vertical_segment(candidate, self.proj):
                continue
            heading = _segment_nominal_heading(candidate, self.proj, prefer_end=prefer_end)
            if heading is not None:
                return float(heading)
        return None

    def _segment_point_xy_m(self, seg: SegmentProfile, point_index: int) -> Tuple[float, float, float]:
        if seg.points_lla and 0 <= point_index < len(seg.points_lla):
            lla = seg.points_lla[point_index]
        else:
            lla = seg.end_lla
        x_m, y_m = _lla_xy_m(self.proj, lla)
        return x_m, y_m, float(lla.alt)

    def _current_target_xy_m(self, seg: SegmentProfile) -> Tuple[float, float, float, bool]:
        if not seg.points_lla or len(seg.points_lla) < 2:
            x_m, y_m = _lla_xy_m(self.proj, seg.end_lla)
            return x_m, y_m, float(seg.end_lla.alt), True
        idx = min(max(1, self._vehicle_waypoint_index), len(seg.points_lla) - 1)
        x_m, y_m, alt_m = self._segment_point_xy_m(seg, idx)
        return x_m, y_m, alt_m, idx >= len(seg.points_lla) - 1

    def _remaining_distance_in_segment_m(self, seg: SegmentProfile, state: _VehicleState) -> float:
        target_x, target_y, _target_alt, at_last = self._current_target_xy_m(seg)
        remaining = _distance_xy_m(state.x_m, state.y_m, target_x, target_y)
        if at_last or not seg.points_lla or not seg.cum_dist_m:
            return remaining
        idx = min(max(1, self._vehicle_waypoint_index), len(seg.cum_dist_m) - 1)
        return remaining + max(0.0, float(seg.cum_dist_m[-1]) - float(seg.cum_dist_m[idx]))

    def _advance_vehicle_segment(self) -> None:
        self._vehicle_segment_index += 1
        self._vehicle_waypoint_index = 1
        if self._vehicle_state is not None:
            self._vehicle_state.vertical_speed_mps = 0.0
            if self._vehicle_segment_index >= len(self.segments):
                self._vehicle_state.speed_mps = 0.0

    def _reset_energy_state(self) -> None:
        capacity_kwh = max(0.0, _config_float(self.config, "battery_capacity_kwh", 120.0))
        initial_pct = _clamp_float(_config_float(self.config, "battery_initial_pct", 100.0), 0.0, 100.0)
        self._battery_pct = initial_pct
        self._battery_consumed_kwh = capacity_kwh * (100.0 - initial_pct) / 100.0 if capacity_kwh > 0.0 else 0.0
        self._battery_power_kw = 0.0
        self._energy_last_alt_m = None

    def _estimate_battery_power_kw(
        self,
        phase: Phase,
        *,
        speed_mps: float,
        climb_rate_mps: float,
        accel_mps2: float = 0.0,
    ) -> float:
        speed = max(0.0, float(speed_mps))
        climb = float(climb_rate_mps)
        accel = max(0.0, float(accel_mps2))

        aux_kw = max(0.0, _config_float(self.config, "battery_aux_power_kw", 6.0))
        taxi_kw = max(0.0, _config_float(self.config, "battery_taxi_power_kw", 18.0))
        hover_kw = max(0.0, _config_float(self.config, "battery_hover_power_kw", 120.0))
        cruise_kw = max(0.0, _config_float(self.config, "battery_cruise_power_kw", 75.0))
        speed_drag_kw = max(0.0, _config_float(self.config, "battery_speed_power_kw_per_mps2", 0.020)) * speed * speed

        if phase in (Phase.A, Phase.K):
            base_kw = taxi_kw + speed_drag_kw * 0.25
        elif phase in (Phase.B, Phase.J) or speed < 2.0:
            base_kw = hover_kw
        else:
            transition_speed = max(1.0, _config_float(self.config, "transition_speed_mps", 35.97))
            cruise_blend = _clamp_float(speed / transition_speed, 0.0, 1.0)
            cruise_component = cruise_kw + speed_drag_kw
            base_kw = hover_kw * (1.0 - cruise_blend) + cruise_component * cruise_blend

        vertical_kw = 0.0
        if climb > 0.0:
            vertical_kw += max(0.0, _config_float(self.config, "battery_climb_power_kw_per_mps", 10.0)) * climb
        else:
            # Descent still consumes power for control/propulsion.  Regeneration
            # is intentionally not modelled, so SOC never comes back up.
            vertical_kw += max(0.0, _config_float(self.config, "battery_descent_power_kw_per_mps", 1.5)) * abs(climb)
        accel_kw = max(0.0, _config_float(self.config, "battery_accel_power_kw_per_mps2", 2.0)) * accel
        return max(0.0, aux_kw + base_kw + vertical_kw + accel_kw)

    def _consume_battery(
        self,
        phase: Phase,
        *,
        speed_mps: float,
        climb_rate_mps: float,
        dt_s: float,
        accel_mps2: float = 0.0,
    ) -> float:
        dt = max(0.0, float(dt_s))
        if dt <= 0.0:
            return self._battery_pct

        capacity_kwh = max(0.0, _config_float(self.config, "battery_capacity_kwh", 120.0))
        if capacity_kwh > 1e-6:
            power_kw = self._estimate_battery_power_kw(
                phase,
                speed_mps=speed_mps,
                climb_rate_mps=climb_rate_mps,
                accel_mps2=accel_mps2,
            )
            consumed_kwh = power_kw * dt / 3600.0
            consumed_pct = consumed_kwh / capacity_kwh * 100.0
            self._battery_consumed_kwh += max(0.0, consumed_kwh)
            self._battery_power_kw = power_kw
        else:
            # Backward-compatible fallback if a caller disables kWh modelling.
            battery_cap_s = max(0.0, _config_float(self.config, "battery_capacity_s", 1800.0))
            consumed_pct = (100.0 * dt / battery_cap_s) if battery_cap_s > 1e-6 else 0.0
            self._battery_power_kw = 0.0

        self._battery_pct = max(0.0, min(self._battery_pct, self._battery_pct - max(0.0, consumed_pct)))
        return self._battery_pct

    def _vehicle_battery_pct(self) -> float:
        return _clamp_float(float(getattr(self, "_battery_pct", 100.0)), 0.0, 100.0)

    def _build_vehicle_point(self, seg: SegmentProfile) -> FlightTrajectoryPoint:
        state = self._vehicle_state
        if state is None:
            raise RuntimeError("Vehicle state is not initialized.")

        lla = _xy_m_to_lla(self.proj, state.x_m, state.y_m, state.alt_m)
        speed = max(0.0, float(state.speed_mps))
        heading = wrap_heading(state.heading_deg)
        track_heading = wrap_heading(state.track_heading_deg)

        if _is_vertical_segment(seg, self.proj):
            speed = abs(float(state.vertical_speed_mps))

        wind_e, wind_n = 0.0, 0.0
        lateral_dev = 0.0
        if seg.phase in (Phase.C, Phase.D, Phase.E, Phase.F, Phase.G, Phase.H, Phase.I):
            lla, speed, heading, _wind_track, wind_e, wind_n = self._apply_wind(
                lla,
                speed,
                heading,
                self._t,
                float(self.config.tick_s),
            )
            lateral_dev = self._wind_cross_m
        else:
            self._wind_cross_m = 0.0
            self._wind_along_m = 0.0

        return FlightTrajectoryPoint(
            time_s=round(self._t, 3),
            clock=self._seconds_to_clock(self.start_time_s + self._t),
            phase=seg.phase.value,
            mode=_phase_to_flight_mode(seg.phase).value,
            lat=lla.lat,
            lon=lla.lon,
            alt_m=round(lla.alt, 2),
            speed_mps=round(speed, 2),
            heading_deg=round(wrap_heading(heading), 2),
            track_heading_deg=round(wrap_heading(track_heading), 2),
            wind_e_mps=round(wind_e, 3),
            wind_n_mps=round(wind_n, 3),
            lateral_dev_m=round(lateral_dev, 3),
            battery_pct=round(self._vehicle_battery_pct(), 2),
        )

    def _build_vehicle_end_point(self) -> FlightTrajectoryPoint:
        state = self._vehicle_state
        last_seg = self.segments[-1]
        if state is None:
            x_m, y_m = _lla_xy_m(self.proj, last_seg.end_lla)
            state = _VehicleState(
                x_m=x_m,
                y_m=y_m,
                alt_m=float(last_seg.end_lla.alt),
                speed_mps=0.0,
                heading_deg=0.0,
                track_heading_deg=0.0,
            )
        lla = _xy_m_to_lla(self.proj, state.x_m, state.y_m, state.alt_m)
        return FlightTrajectoryPoint(
            time_s=round(self._t, 3),
            clock=self._seconds_to_clock(self.start_time_s + self._t),
            phase=last_seg.phase.value,
            mode=FlightMode.ENDED.value,
            lat=lla.lat,
            lon=lla.lon,
            alt_m=round(lla.alt, 2),
            speed_mps=0.0,
            heading_deg=round(wrap_heading(state.heading_deg), 2),
            track_heading_deg=round(wrap_heading(state.track_heading_deg), 2),
            battery_pct=round(self._vehicle_battery_pct(), 2),
        )

    def _step_vehicle_vertical(self, seg: SegmentProfile, dt: float) -> None:
        state = self._vehicle_state
        if state is None:
            return

        start_x, start_y = _lla_xy_m(self.proj, seg.start_lla)
        target_x, target_y = _lla_xy_m(self.proj, seg.end_lla)
        if _distance_xy_m(state.x_m, state.y_m, start_x, start_y) < 0.5:
            state.x_m = start_x
            state.y_m = start_y
        else:
            state.x_m = target_x
            state.y_m = target_y

        state.speed_mps = 0.0
        target_heading = self._vertical_target_heading(self._vehicle_segment_index, seg)
        if target_heading is not None:
            state.track_heading_deg = wrap_heading(target_heading)
            state.heading_deg = _slew_heading(
                state.heading_deg,
                target_heading,
                float(self.config.turn_rate_deg_s) * dt,
            )
        else:
            state.track_heading_deg = state.heading_deg

        target_alt = float(seg.end_lla.alt)
        if (
            seg.phase == Phase.J
            and target_heading is not None
            and abs(_signed_heading_delta_deg(target_heading, state.heading_deg)) > 0.5
            and abs(state.alt_m - target_alt) > 0.01
        ):
            state.vertical_speed_mps = 0.0
            return

        climb_rate = float(self.config.vertical_climb_rate_mps)
        descent_rate = float(self.config.vertical_descent_rate_mps)
        rate = climb_rate if target_alt >= state.alt_m else descent_rate
        max_step = max(0.0, abs(rate) * dt)
        prev_alt = state.alt_m
        state.alt_m = _move_towards(state.alt_m, target_alt, max_step)
        state.vertical_speed_mps = (state.alt_m - prev_alt) / dt if dt > 0 else 0.0

        if abs(state.alt_m - target_alt) <= 0.01:
            state.alt_m = target_alt
            state.vertical_speed_mps = 0.0
            self._advance_vehicle_segment()

    def _step_vehicle_horizontal(self, seg: SegmentProfile, dt: float) -> None:
        state = self._vehicle_state
        if state is None:
            return

        target_x, target_y, target_alt, at_last = self._current_target_xy_m(seg)
        dist = _distance_xy_m(state.x_m, state.y_m, target_x, target_y)
        acceptance_m = max(
            0.5,
            float(getattr(self.config, "vehicle_waypoint_acceptance_m", 6.0) or 6.0),
        )
        final_snap_m = max(acceptance_m, state.speed_mps * dt + 0.2)
        if at_last and dist <= final_snap_m and abs(state.alt_m - float(seg.end_lla.alt)) <= 0.5:
            state.x_m = target_x
            state.y_m = target_y
            state.alt_m = float(seg.end_lla.alt)
            state.speed_mps = 0.0 if self._vehicle_segment_index >= len(self.segments) - 1 else state.speed_mps
            self._advance_vehicle_segment()
            return
        if dist <= acceptance_m and not at_last:
            rate = (
                float(self.config.vertical_climb_rate_mps)
                if target_alt >= state.alt_m
                else float(self.config.vertical_descent_rate_mps)
            )
            prev_alt = state.alt_m
            state.alt_m = _move_towards(state.alt_m, target_alt, max(0.0, abs(rate) * dt))
            state.vertical_speed_mps = (state.alt_m - prev_alt) / dt if dt > 0 else 0.0
            if at_last and abs(state.alt_m - float(seg.end_lla.alt)) <= 0.5:
                state.alt_m = float(seg.end_lla.alt)
                self._advance_vehicle_segment()
            else:
                self._vehicle_waypoint_index += 1
            return
        if dist <= 1e-6:
            return

        desired_track = _heading_between_xy_m(state.x_m, state.y_m, target_x, target_y)
        state.track_heading_deg = wrap_heading(desired_track)
        state.heading_deg = _slew_heading(
            state.heading_deg,
            desired_track,
            float(self.config.turn_rate_deg_s) * dt,
        )
        if (
            state.speed_mps <= 0.2
            and abs(_signed_heading_delta_deg(desired_track, state.heading_deg)) > 0.5
        ):
            state.speed_mps = 0.0
            state.vertical_speed_mps = 0.0
            return

        target_speed = self._segment_target_speed(seg)
        exit_speed = self._segment_exit_speed(self._vehicle_segment_index) if at_last else target_speed
        remaining = self._remaining_distance_in_segment_m(seg, state)
        accel = max(1e-6, float(self.config.accel_mps2))
        braking_dist = 0.0
        if state.speed_mps > exit_speed:
            braking_dist = ((state.speed_mps ** 2) - (exit_speed ** 2)) / (2.0 * accel)
        desired_speed = exit_speed if remaining <= braking_dist + max(1.0, state.speed_mps * dt) else target_speed
        desired_speed = max(0.0, desired_speed)
        vertical_rate = (
            float(self.config.vertical_climb_rate_mps)
            if target_alt >= state.alt_m
            else float(self.config.vertical_descent_rate_mps)
        )
        alt_remaining_m = abs(float(target_alt) - float(state.alt_m))
        if alt_remaining_m > 0.5 and abs(vertical_rate) > 1e-6:
            vertical_time_needed_s = alt_remaining_m / abs(vertical_rate)
            if vertical_time_needed_s > dt:
                desired_speed = min(
                    desired_speed,
                    max(0.5, remaining / vertical_time_needed_s),
                )
        state.speed_mps = _move_towards(state.speed_mps, desired_speed, accel * dt)

        step_m = max(0.0, state.speed_mps * dt)
        move_m = min(dist, step_m)
        if move_m > 0.0:
            ratio = move_m / dist
            state.x_m += (target_x - state.x_m) * ratio
            state.y_m += (target_y - state.y_m) * ratio

        prev_alt = state.alt_m
        state.alt_m = _move_towards(state.alt_m, target_alt, max(0.0, abs(vertical_rate) * dt))
        state.vertical_speed_mps = (state.alt_m - prev_alt) / dt if dt > 0 else 0.0

        reached = move_m >= dist - 1e-6
        if reached:
            state.x_m = target_x
            state.y_m = target_y
            if at_last:
                final_alt = float(seg.end_lla.alt)
                if abs(state.alt_m - final_alt) <= 0.5:
                    state.alt_m = final_alt
                    self._advance_vehicle_segment()
            else:
                self._vehicle_waypoint_index += 1

    def _step_vehicle(self, dt: float) -> None:
        if self._vehicle_segment_index >= len(self.segments):
            return
        seg = self.segments[self._vehicle_segment_index]
        if _is_vertical_segment(seg, self.proj):
            self._step_vehicle_vertical(seg, dt)
            return
        self._step_vehicle_horizontal(seg, dt)

    def _tick_vehicle(self) -> Optional[FlightTrajectoryPoint]:
        if self._finished or not self.segments:
            return None

        if self._vehicle_segment_index >= len(self.segments):
            if self._vehicle_end_emitted:
                self._finished = True
                return None
            self._vehicle_end_emitted = True
            self._finished = True
            return self._build_vehicle_end_point()

        seg = self.segments[self._vehicle_segment_index]
        tick = max(1e-3, float(self.config.tick_s))
        if seg.phase not in (Phase.A, Phase.K):
            self._airborne_time += tick
        state = self._vehicle_state
        self._consume_battery(
            seg.phase,
            speed_mps=max(0.0, float(state.speed_mps)) if state is not None else 0.0,
            climb_rate_mps=float(state.vertical_speed_mps) if state is not None else 0.0,
            dt_s=tick,
        )
        point = self._build_vehicle_point(seg)

        self._step_vehicle(tick)
        self._t += tick
        if self._t > self._vehicle_max_time_s:
            self._vehicle_segment_index = len(self.segments)
        return point

    # ── Tick-by-tick interface ──────────────────────────────────

    def tick(self) -> Optional[FlightTrajectoryPoint]:
        """Advance one simulation step and return the trajectory point.

        Returns ``None`` once the flight has ended and there are no more
        points to emit.  After returning ``None``, ``is_finished`` is
        ``True``.
        """
        if self._vehicle_enabled:
            return self._tick_vehicle()

        if self._finished or not self.kinematics:
            return None

        t = self._t
        tick = self.config.tick_s

        sim_time_s = self.start_time_s + t
        clock = self._seconds_to_clock(sim_time_s)

        # ── End-of-flight point ────────────────────────────────
        if t > self.total_time_s:
            last_seg = self.segments[-1]
            point = FlightTrajectoryPoint(
                time_s=t, clock=clock,
                phase=last_seg.phase.value,
                mode=FlightMode.ENDED.value,
                lat=last_seg.end_lla.lat, lon=last_seg.end_lla.lon,
                alt_m=last_seg.end_lla.alt,
                speed_mps=0.0, heading_deg=0.0, track_heading_deg=0.0,
                battery_pct=round(self._vehicle_battery_pct(), 2),
            )
            self._finished = True
            return point

        # ── Normal tick ────────────────────────────────────────
        seg_idx, seg_kin = find_segment_at_time(self.kinematics, t)
        seg = self.segments[seg_idx]
        t_in_seg = t - seg_kin.start_time_s

        lla, dist_in_seg, speed = _interpolate_on_segment(seg, seg_kin, t_in_seg)
        if seg_kin.is_vertical:
            heading = float(self._vertical_heading_overrides.get(seg_idx, self._prev_track_deg or 0.0))
        else:
            heading = _heading_on_polyline(
                seg.points_lla, seg.cum_dist_m, dist_in_seg, self.proj
            )
        mode = _phase_to_flight_mode(seg.phase)

        if seg.phase not in (Phase.A, Phase.K):
            self._airborne_time += tick

        wind_e, wind_n = 0.0, 0.0
        lateral_dev = 0.0
        if seg.phase in (Phase.C, Phase.D, Phase.E, Phase.F, Phase.G, Phase.H, Phase.I):
            lla, speed, heading, track_heading, wind_e, wind_n = self._apply_wind(
                lla, speed, heading, t, tick
            )
            lateral_dev = self._wind_cross_m
        else:
            track_heading = heading
            self._wind_cross_m = 0.0
            self._wind_along_m = 0.0

        if seg_kin.is_vertical:
            direction = 1.0 if float(seg.end_lla.alt) >= float(seg.start_lla.alt) else -1.0
            climb_rate = direction * abs(float(getattr(seg_kin, "climb_rate_mps", 0.0) or 0.0))
        else:
            prev_alt = self._energy_last_alt_m
            climb_rate = (
                (float(lla.alt) - float(prev_alt)) / max(1e-6, float(tick))
                if prev_alt is not None
                else 0.0
            )
        self._energy_last_alt_m = float(lla.alt)
        self._consume_battery(
            seg.phase,
            speed_mps=float(speed),
            climb_rate_mps=float(climb_rate),
            dt_s=float(tick),
        )
        battery_pct = self._vehicle_battery_pct()

        point = FlightTrajectoryPoint(
            time_s=round(t, 3),
            clock=clock,
            phase=seg.phase.value,
            mode=mode.value,
            lat=lla.lat,
            lon=lla.lon,
            alt_m=round(lla.alt, 2),
            speed_mps=round(speed, 2),
            heading_deg=round(wrap_heading(heading), 2),
            track_heading_deg=round(wrap_heading(track_heading), 2),
            wind_e_mps=round(wind_e, 3),
            wind_n_mps=round(wind_n, 3),
            lateral_dev_m=round(lateral_dev, 3),
            battery_pct=round(battery_pct, 2),
        )

        self._t += tick
        return point

    # ── Batch interface (backward-compatible) ──────────────────

    def generate_trajectory(self) -> List[FlightTrajectoryPoint]:
        """Run the full simulation and return trajectory points.

        This is a convenience wrapper around ``tick()`` for backward
        compatibility with the batch workflow.
        """
        self.reset()
        points: List[FlightTrajectoryPoint] = []
        while True:
            pt = self.tick()
            if pt is None:
                break
            points.append(pt)
        return _smooth_trajectory_points(points, self.proj, self.config)
