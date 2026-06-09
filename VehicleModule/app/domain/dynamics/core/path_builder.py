"""UAM Flight Simulator — Path builder.

Converts ICD enRoute segments into a densified polyline of LLA waypoints
that the dynamics engine can follow.  Handles:
  - Straight segments (A, B, C, E, F, G, I, J, K)
  - Circular-arc turn segments (D, H) using centerLLA
"""

from __future__ import annotations

import math
from typing import List, Tuple

from .types import (
    LLA,
    EnRouteSegment,
    FlightPlan,
    Phase,
    SegmentProfile,
    SimulationConfig,
    TURN_PHASES,
)
from .geo import LocalProjection, XY, distance_xy


def _arc_points(
    center: XY,
    start: XY,
    end: XY,
    clockwise: bool,
    step_deg: float,
    proj: LocalProjection,
    start_alt: float,
    end_alt: float,
) -> Tuple[List[LLA], List[float]]:
    """Generate densified LLA points along a circular arc.

    Returns (points, cumulative_distances_m).
    """
    r_start = math.hypot((start.x - center.x), (start.y - center.y))
    r_end = math.hypot((end.x - center.x), (end.y - center.y))
    radius_km = (r_start + r_end) / 2.0
    if radius_km < 1e-6:
        lla_s = proj.xy_to_lla(start, start_alt)
        lla_e = proj.xy_to_lla(end, end_alt)
        d = distance_xy(start, end)
        return [lla_s, lla_e], [0.0, d]

    a_start = math.atan2(start.y - center.y, start.x - center.x)
    a_end = math.atan2(end.y - center.y, end.x - center.x)

    if clockwise:
        sweep = a_start - a_end
        if sweep <= 0:
            sweep += 2 * math.pi
    else:
        sweep = a_end - a_start
        if sweep <= 0:
            sweep += 2 * math.pi

    n_steps = max(2, int(math.degrees(sweep) / step_deg) + 1)
    points: List[LLA] = []
    cum_dist: List[float] = [0.0]
    total = 0.0
    prev_xy = start

    for i in range(n_steps + 1):
        t = i / n_steps
        if clockwise:
            angle = a_start - sweep * t
        else:
            angle = a_start + sweep * t

        xy = XY(center.x + radius_km * math.cos(angle),
                center.y + radius_km * math.sin(angle))
        alt = start_alt + (end_alt - start_alt) * t
        lla = proj.xy_to_lla(xy, alt)
        points.append(lla)

        if i > 0:
            d = distance_xy(prev_xy, xy)
            total += d
            cum_dist.append(total)
        prev_xy = xy

    return points, cum_dist


def _straight_points(
    start: XY,
    end: XY,
    proj: LocalProjection,
    start_alt: float,
    end_alt: float,
    step_m: float,
) -> Tuple[List[LLA], List[float]]:
    """Generate densified LLA points along a straight line segment."""
    total_d = distance_xy(start, end)
    if total_d < 1e-3:
        lla = proj.xy_to_lla(start, start_alt)
        return [lla], [0.0]

    n_steps = max(1, int(total_d / step_m))
    points: List[LLA] = []
    cum_dist: List[float] = [0.0]
    total = 0.0
    prev_xy = start

    for i in range(n_steps + 1):
        t = i / n_steps
        xy = XY(start.x + (end.x - start.x) * t,
                start.y + (end.y - start.y) * t)
        alt = start_alt + (end_alt - start_alt) * t
        lla = proj.xy_to_lla(xy, alt)
        points.append(lla)

        if i > 0:
            d = distance_xy(prev_xy, xy)
            total += d
            cum_dist.append(total)
        prev_xy = xy

    return points, cum_dist


def build_segment_profiles(
    plan: FlightPlan,
    config: SimulationConfig,
) -> Tuple[List[SegmentProfile], LocalProjection]:
    """Build densified segment profiles from an ICD flight plan.

    Returns a list of SegmentProfile objects and the projection used.
    """
    if not plan.en_route:
        return [], LocalProjection(127.0, 37.5)

    # Centre projection on the first segment's start
    ref = plan.en_route[0].start_lla
    proj = LocalProjection(ref.lon, ref.lat)

    profiles: List[SegmentProfile] = []

    for seg in plan.en_route:
        start_xy = proj.lla_to_xy(seg.start_lla)
        end_xy = proj.lla_to_xy(seg.end_lla)

        if seg.phase in TURN_PHASES and seg.center_lla is not None:
            center_xy = proj.lla_to_xy(seg.center_lla)
            clockwise = seg.turn_direction == "CW"
            points, cum_dist = _arc_points(
                center_xy, start_xy, end_xy,
                clockwise, config.arc_step_deg,
                proj, seg.start_lla.alt, seg.end_lla.alt,
            )
        else:
            points, cum_dist = _straight_points(
                start_xy, end_xy, proj,
                seg.start_lla.alt, seg.end_lla.alt,
                config.densify_step_m,
            )

        total_dist = cum_dist[-1] if cum_dist else 0.0

        # Estimate segment duration from distance and target speed
        if seg.target_speed > 0 and total_dist > 0:
            duration = total_dist / seg.target_speed
        else:
            # Vertical segments with zero horizontal distance
            alt_diff = abs(seg.end_lla.alt - seg.start_lla.alt)
            if seg.phase == Phase.B:
                duration = alt_diff / config.vertical_climb_rate_mps if config.vertical_climb_rate_mps > 0 else 0.0
            elif seg.phase == Phase.J:
                duration = alt_diff / config.vertical_descent_rate_mps if config.vertical_descent_rate_mps > 0 else 0.0
            else:
                duration = alt_diff / max(seg.target_speed, 1.0) if alt_diff > 0 else 0.0

        profiles.append(SegmentProfile(
            phase=seg.phase,
            start_lla=seg.start_lla,
            end_lla=seg.end_lla,
            target_speed_mps=seg.target_speed,
            distance_m=total_dist,
            duration_s=duration,
            target_heading_deg=seg.target_heading_deg,
            points_lla=points,
            cum_dist_m=cum_dist,
        ))

    return profiles, proj
