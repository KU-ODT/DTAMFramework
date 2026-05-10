"""UAM Flight Simulator — Flight kinematic profile.

Pre-computes speed and acceleration schedules within each segment
so the dynamics engine can sample position at arbitrary time offsets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from .types import LLA, Phase, SegmentProfile, SimulationConfig


@dataclass
class SegmentKinematics:
    """Pre-computed kinematic schedule for one segment."""
    seg_index: int
    phase: Phase
    start_time_s: float    # absolute sim-time when segment begins
    end_time_s: float      # absolute sim-time when segment ends
    duration_s: float
    distance_m: float
    entry_speed_mps: float
    exit_speed_mps: float
    target_speed_mps: float
    accel_mps2: float      # signed acceleration
    # For vertical-only segments
    is_vertical: bool
    climb_rate_mps: float  # signed: positive=up, negative=down


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def build_kinematics(
    segments: List[SegmentProfile],
    config: SimulationConfig,
) -> List[SegmentKinematics]:
    """Build a kinematic schedule across all segments.

    Computes entry/exit speeds, acceleration rates, and absolute
    timing for each segment to create smooth speed transitions.
    """
    if not segments:
        return []

    result: List[SegmentKinematics] = []
    current_time = 0.0
    current_speed = 0.0  # start stationary

    for i, seg in enumerate(segments):
        target = seg.target_speed_mps
        dist = seg.distance_m
        is_vertical = seg.phase in (Phase.B, Phase.J)

        if is_vertical:
            # Vertical segments: use climb/descent rate, not horizontal speed
            alt_diff = seg.end_lla.alt - seg.start_lla.alt
            if seg.phase == Phase.B:
                rate = config.vertical_climb_rate_mps
            else:
                rate = -config.vertical_descent_rate_mps
            duration = abs(alt_diff) / abs(rate) if abs(rate) > 0 else 0.0
            entry_speed = 0.0
            exit_speed = 0.0
            accel = 0.0
        elif seg.phase in (Phase.A, Phase.K):
            # Taxi: constant low speed
            taxi_speed = min(target, config.taxi_speed_mps)
            duration = dist / taxi_speed if taxi_speed > 0 else 0.0
            entry_speed = taxi_speed
            exit_speed = taxi_speed
            accel = 0.0
            current_speed = taxi_speed
        else:
            # Airborne segments: accelerate/decelerate to target speed
            entry_speed = current_speed

            # Compute how much distance needed to reach target speed
            if abs(target - entry_speed) > 0.01 and config.accel_mps2 > 0:
                accel_dist = abs(target ** 2 - entry_speed ** 2) / (2.0 * config.accel_mps2)
                if accel_dist >= dist:
                    # Can't reach target speed in this segment
                    # Compute achievable speed
                    if target > entry_speed:
                        achievable = math.sqrt(entry_speed ** 2 + 2 * config.accel_mps2 * dist)
                        exit_speed = min(achievable, target)
                    else:
                        achievable = math.sqrt(max(0, entry_speed ** 2 - 2 * config.accel_mps2 * dist))
                        exit_speed = max(achievable, target)
                    avg_speed = (entry_speed + exit_speed) / 2.0
                    duration = dist / avg_speed if avg_speed > 0 else 0.0
                    accel = (exit_speed - entry_speed) / duration if duration > 0 else 0.0
                else:
                    # Accelerate/decelerate then cruise
                    accel_time = abs(target - entry_speed) / config.accel_mps2
                    remaining_dist = dist - accel_dist
                    cruise_time = remaining_dist / target if target > 0 else 0.0
                    duration = accel_time + cruise_time
                    exit_speed = target
                    accel = (target - entry_speed) / accel_time if accel_time > 0 else 0.0
            else:
                # Already at target speed
                exit_speed = target
                duration = dist / target if target > 0 else 0.0
                accel = 0.0

            current_speed = exit_speed

        # Ensure minimum duration
        if duration < 0.001:
            duration = 0.001

        result.append(SegmentKinematics(
            seg_index=i,
            phase=seg.phase,
            start_time_s=current_time,
            end_time_s=current_time + duration,
            duration_s=duration,
            distance_m=dist,
            entry_speed_mps=entry_speed,
            exit_speed_mps=exit_speed,
            target_speed_mps=target,
            accel_mps2=accel,
            is_vertical=is_vertical,
            climb_rate_mps=(seg.end_lla.alt - seg.start_lla.alt) / duration if duration > 0 else 0.0,
        ))
        current_time += duration

    return result


def total_flight_time(kinematics: List[SegmentKinematics]) -> float:
    """Total flight time across all segments."""
    if not kinematics:
        return 0.0
    return kinematics[-1].end_time_s


def find_segment_at_time(
    kinematics: List[SegmentKinematics],
    t_s: float,
) -> Tuple[int, SegmentKinematics]:
    """Find which segment index is active at time t_s.

    Returns (segment_index, kinematics).
    """
    for k in kinematics:
        if t_s <= k.end_time_s:
            return k.seg_index, k
    # Past the end: return last segment
    last = kinematics[-1]
    return last.seg_index, last
