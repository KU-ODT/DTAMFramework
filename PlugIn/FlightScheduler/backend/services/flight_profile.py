"""Mission flight profile — 9-phase staircase model for urban UAM.

Phase scheme (D/H 제거, C·E·G·I 모두 사선):
    A  Gate → FATO taxi             ground
    B  Vertical takeoff             0   → 15 m
    C  Transition + climb           15  → 100 m   (TRANSITION_SPEED)
    E  Accel + climb                100 → 305 m   (TRANSITION_SPEED → cruise)
    F  Cruise                       305 m         (cruise speed)
    G  Decel + descend              305 → 100 m   (cruise → TRANSITION_SPEED)
    I  Transition + descend         100 → 15 m    (DESCENT_SPEED)
    J  Vertical landing             15  → 0 m
    K  FATO → Gate taxi             ground

`build_mission_profile(air_distance_m, ...)` returns a list of phase entries
with start/end altitudes, speeds, distance, duration, and cumulative running
totals — enough for the frontend to draw an altitude/speed chart.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import List, Optional

# ---- defaults (도심 UAM, staircase profile) ----
TAXI_SPEED_MPS = 3.0           # ≈ 6 kt
VERTICAL_SPEED_MPS = 10.0      # ≈ 19 kt
TRANSITION_SPEED_MPS = 36.0    # ≈ 70 kt — sloped climb/descent target
DESCENT_SPEED_MPS = 30.0       # ≈ 58 kt — final approach
DEFAULT_CRUISE_SPEED_MPS = 51.4  # ≈ 100 kt
TRANSITION_ALT_M = 15.0        # vertical ↔ sloped transition (≈ 50 ft)
TERMINAL_ALT_M = 100.0         # terminal-procedure altitude (≈ 300 ft)
CORRIDOR_ALT_M = 305.0         # waypoint/cruise altitude (≈ 1000 ft)
CLIMB_RATE_MPS = 2.54          # 500 fpm
ACCEL_MPS2 = 1.5
DEFAULT_TAXI_DIST_M = 200.0    # gate ↔ fato typical


@dataclass
class PhaseEntry:
    code: str               # 'A' .. 'K'
    name: str               # Korean label
    altStartM: float
    altEndM: float
    speedStartMps: float
    speedEndMps: float
    distanceM: float        # along-trajectory distance
    durationS: float
    cumDistanceM: float     # running cumulative
    cumDurationS: float

    def to_dict(self) -> dict:
        return asdict(self)


def _slope_distance(vert_m: float, horiz_m: float) -> float:
    return math.hypot(vert_m, horiz_m)


def build_mission_profile(
    *,
    air_distance_m: float,
    cruise_speed_mps: float = DEFAULT_CRUISE_SPEED_MPS,
    tdp_alt_m: float = 120.0,
    ldp_alt_m: float = 90.0,
    taxi_dist_dep_m: float = DEFAULT_TAXI_DIST_M,
    taxi_dist_arr_m: float = DEFAULT_TAXI_DIST_M,
) -> dict:
    """Build the 9-phase staircase profile.

    `air_distance_m` is the route path length in meters (output of
    pathplanner.find_route().distance_km × 1000). It's matched against the
    *horizontal projection* of phases C/E/F/G/I — so the computed splits
    line up with the map-projected route distance.

    Altitude staircase: 0 → 15 (B) → 100 (C) → 305 (E) → 305 (F) → 100 (G)
    → 15 (I) → 0 (J). E and G combine altitude change with accel/decel.

    `tdp_alt_m` / `ldp_alt_m` are stored as annotations; the profile uses
    fixed corridor / terminal / transition altitudes regardless.
    """
    cruise_speed_mps = max(TRANSITION_SPEED_MPS + 1, float(cruise_speed_mps))
    avg_e_speed = 0.5 * (TRANSITION_SPEED_MPS + cruise_speed_mps)

    phases: List[PhaseEntry] = []
    cum_d = 0.0
    cum_t = 0.0

    def push(p: PhaseEntry) -> None:
        nonlocal cum_d, cum_t
        cum_d += p.distanceM
        cum_t += p.durationS
        p.cumDistanceM = cum_d
        p.cumDurationS = cum_t
        phases.append(p)

    # --- A: gate→fato taxi
    a_dist = float(taxi_dist_dep_m)
    push(PhaseEntry(
        code='A', name='Gate→FATO 활주',
        altStartM=0.0, altEndM=0.0,
        speedStartMps=TAXI_SPEED_MPS, speedEndMps=TAXI_SPEED_MPS,
        distanceM=a_dist,
        durationS=a_dist / TAXI_SPEED_MPS,
        cumDistanceM=0.0, cumDurationS=0.0,
    ))

    # --- B: vertical takeoff 0 → TRANSITION_ALT
    push(PhaseEntry(
        code='B', name='수직 이륙',
        altStartM=0.0, altEndM=TRANSITION_ALT_M,
        speedStartMps=VERTICAL_SPEED_MPS, speedEndMps=VERTICAL_SPEED_MPS,
        distanceM=TRANSITION_ALT_M,
        durationS=TRANSITION_ALT_M / VERTICAL_SPEED_MPS,
        cumDistanceM=0.0, cumDurationS=0.0,
    ))

    # --- C: transition + climb 15 → 100 m at TRANSITION_SPEED
    c_alt = TERMINAL_ALT_M - TRANSITION_ALT_M  # 85 m
    c_time = c_alt / CLIMB_RATE_MPS
    c_horizontal = TRANSITION_SPEED_MPS * c_time

    # --- E: accel + climb 100 → 305 m, TRANSITION_SPEED → cruise
    e_alt = CORRIDOR_ALT_M - TERMINAL_ALT_M  # 205 m
    e_time = e_alt / CLIMB_RATE_MPS  # climb sets the duration (longer than accel)
    e_horizontal = avg_e_speed * e_time

    # --- G: decel + descend 305 → 100 m (mirror of E)
    g_horizontal = e_horizontal
    g_time = e_time

    # --- I: transition + descend 100 → 15 m at DESCENT_SPEED
    i_alt = TERMINAL_ALT_M - TRANSITION_ALT_M  # 85 m
    i_time = i_alt / CLIMB_RATE_MPS
    i_horizontal = DESCENT_SPEED_MPS * i_time

    used_horizontal = c_horizontal + e_horizontal + g_horizontal + i_horizontal
    remaining_horizontal = float(air_distance_m) - used_horizontal

    # If route too short to fit C+E+G+I, shrink them proportionally so the
    # profile still terminates at the destination.
    shrink = 1.0
    if remaining_horizontal < 0 and used_horizontal > 0:
        shrink = float(air_distance_m) / used_horizontal
        c_horizontal *= shrink
        e_horizontal *= shrink
        g_horizontal *= shrink
        i_horizontal *= shrink
        c_time *= shrink
        e_time *= shrink
        g_time *= shrink
        i_time *= shrink
        remaining_horizontal = 0.0

    c_distance = _slope_distance(c_alt, c_horizontal)
    e_distance = _slope_distance(e_alt, e_horizontal)
    g_distance = _slope_distance(e_alt, g_horizontal)
    i_distance = _slope_distance(i_alt, i_horizontal)

    push(PhaseEntry(
        code='C', name='사선 climb',
        altStartM=TRANSITION_ALT_M, altEndM=TERMINAL_ALT_M,
        speedStartMps=TRANSITION_SPEED_MPS, speedEndMps=TRANSITION_SPEED_MPS,
        distanceM=c_distance,
        durationS=c_time,
        cumDistanceM=0.0, cumDurationS=0.0,
    ))
    # E speed end = peak_speed_during_E (full cruise unless shrunk away)
    e_speed_end = cruise_speed_mps if shrink == 1.0 else TRANSITION_SPEED_MPS + (cruise_speed_mps - TRANSITION_SPEED_MPS) * shrink
    push(PhaseEntry(
        code='E', name='가속 + 상승',
        altStartM=TERMINAL_ALT_M, altEndM=CORRIDOR_ALT_M,
        speedStartMps=TRANSITION_SPEED_MPS, speedEndMps=e_speed_end,
        distanceM=e_distance,
        durationS=e_time,
        cumDistanceM=0.0, cumDurationS=0.0,
    ))

    # --- F: cruise at corridor altitude, fills any remaining horizontal
    if remaining_horizontal > 0:
        f_time = remaining_horizontal / cruise_speed_mps
        peak_speed = cruise_speed_mps
        push(PhaseEntry(
            code='F', name='순항',
            altStartM=CORRIDOR_ALT_M, altEndM=CORRIDOR_ALT_M,
            speedStartMps=cruise_speed_mps, speedEndMps=cruise_speed_mps,
            distanceM=remaining_horizontal,
            durationS=f_time,
            cumDistanceM=0.0, cumDurationS=0.0,
        ))
    else:
        peak_speed = e_speed_end

    push(PhaseEntry(
        code='G', name='감속 + 하강',
        altStartM=CORRIDOR_ALT_M, altEndM=TERMINAL_ALT_M,
        speedStartMps=e_speed_end, speedEndMps=TRANSITION_SPEED_MPS,
        distanceM=g_distance,
        durationS=g_time,
        cumDistanceM=0.0, cumDurationS=0.0,
    ))
    push(PhaseEntry(
        code='I', name='사선 descent',
        altStartM=TERMINAL_ALT_M, altEndM=TRANSITION_ALT_M,
        speedStartMps=TRANSITION_SPEED_MPS, speedEndMps=DESCENT_SPEED_MPS,
        distanceM=i_distance,
        durationS=i_time,
        cumDistanceM=0.0, cumDurationS=0.0,
    ))

    # --- J: vertical landing
    push(PhaseEntry(
        code='J', name='수직 착륙',
        altStartM=TRANSITION_ALT_M, altEndM=0.0,
        speedStartMps=VERTICAL_SPEED_MPS, speedEndMps=VERTICAL_SPEED_MPS,
        distanceM=TRANSITION_ALT_M,
        durationS=TRANSITION_ALT_M / VERTICAL_SPEED_MPS,
        cumDistanceM=0.0, cumDurationS=0.0,
    ))

    # --- K: fato→gate taxi
    k_dist = float(taxi_dist_arr_m)
    push(PhaseEntry(
        code='K', name='FATO→Gate 활주',
        altStartM=0.0, altEndM=0.0,
        speedStartMps=TAXI_SPEED_MPS, speedEndMps=TAXI_SPEED_MPS,
        distanceM=k_dist,
        durationS=k_dist / TAXI_SPEED_MPS,
        cumDistanceM=0.0, cumDurationS=0.0,
    ))

    return {
        "phases": [p.to_dict() for p in phases],
        "totalDistanceM": round(cum_d, 2),
        "totalDurationS": round(cum_t, 2),
        "peakSpeedMps": round(peak_speed, 3),
        "cruiseAltM": CORRIDOR_ALT_M,
        "terminalAltM": TERMINAL_ALT_M,
        "transitionAltM": TRANSITION_ALT_M,
        "tdpAltM": float(tdp_alt_m),
        "ldpAltM": float(ldp_alt_m),
        "constants": {
            "taxiSpeedMps": TAXI_SPEED_MPS,
            "verticalSpeedMps": VERTICAL_SPEED_MPS,
            "transitionSpeedMps": TRANSITION_SPEED_MPS,
            "descentSpeedMps": DESCENT_SPEED_MPS,
            "cruiseSpeedMps": cruise_speed_mps,
            "climbRateMps": CLIMB_RATE_MPS,
            "accelMps2": ACCEL_MPS2,
        },
    }
