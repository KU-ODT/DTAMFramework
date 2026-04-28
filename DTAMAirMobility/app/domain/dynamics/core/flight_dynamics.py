"""UAM Flight Simulator — Flight dynamics engine.

Samples position, altitude, speed, and heading at each simulation tick,
applying kinematic profiles and wind perturbation.  This is the core
physics loop extracted from UATM sim_core.py.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from dataclasses import replace
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
        locked_xy.append(endpoint or point.phase in _LOCKED_XY_PHASES)
        locked_alt.append(endpoint)
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

    smoothed: List[FlightTrajectoryPoint] = []
    for idx, point in enumerate(points):
        if locked_xy[idx] and locked_alt[idx]:
            smoothed.append(point)
            continue
        lon, lat = proj.to_lonlat(smooth_x[idx], smooth_y[idx])
        if point.phase in _LOCKED_XY_PHASES:
            track_heading = float(point.track_heading_deg)
            heading = float(point.heading_deg)
        else:
            track_heading = smooth_track[idx]
            heading = wrap_heading(track_heading + smooth_crab[idx])
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
        self._finished = False

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
        self._finished = False
        self._wind_cross_m = 0.0
        self._wind_along_m = 0.0
        self._prev_wind_e = 0.0
        self._prev_wind_n = 0.0
        self._prev_track_deg = 0.0
        self._vertical_heading_overrides = _build_vertical_heading_overrides(self.segments, self.proj)

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

    # ── Tick-by-tick interface ──────────────────────────────────

    def tick(self) -> Optional[FlightTrajectoryPoint]:
        """Advance one simulation step and return the trajectory point.

        Returns ``None`` once the flight has ended and there are no more
        points to emit.  After returning ``None``, ``is_finished`` is
        ``True``.
        """
        if self._finished or not self.kinematics:
            return None

        t = self._t
        tick = self.config.tick_s
        battery_cap = self.config.battery_capacity_s

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
                battery_pct=max(0, 100.0 * (1 - self._airborne_time / battery_cap)) if battery_cap > 0 else 100.0,
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

        battery_pct = 100.0
        if battery_cap > 0:
            battery_pct = max(0.0, 100.0 * (1.0 - self._airborne_time / battery_cap))

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
