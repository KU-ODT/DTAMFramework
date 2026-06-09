"""
VFDS Dynamics Dispatch System — Arc Interpolator & Validator

회전 세그먼트(Phase D, H)의 startLLA, endLLA, centerLLA, turnDirection으로부터
원호 기하학 검증, 보정, 그리고 시각화용 보간을 수행한다.

Phase 2 리팩토링: arc를 waypoint로 쪼개는 것이 아니라,
arc 파라미터(center, radius, sweep)를 직접 계산하여 LegBlock으로 전달하고,
오토파일럿의 orbit 명령으로 실행한다.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Literal, Optional

from ..validator.models import LLA

logger = logging.getLogger(__name__)

# ──────────────────────── 기하 상수 ────────────────────────────
M_PER_DEG_LAT = 111320.0


def _m_per_deg_lon(lat_deg: float) -> float:
    return M_PER_DEG_LAT * math.cos(math.radians(lat_deg))


def _dist_m(center: LLA, point: LLA) -> float:
    """center→point 거리 (m, 평면근사)."""
    dy = (point.lat - center.lat) * M_PER_DEG_LAT
    dx = (point.lon - center.lon) * _m_per_deg_lon(center.lat)
    return math.sqrt(dx**2 + dy**2)


def _angle_rad(center: LLA, point: LLA) -> float:
    """center→point 방위각 (수학 좌표계: 동=0, 반시계 양방향)."""
    dx = (point.lon - center.lon) * _m_per_deg_lon(center.lat)
    dy = (point.lat - center.lat) * M_PER_DEG_LAT
    return math.atan2(dy, dx)


# ──────────────────────── Arc Validation ────────────────────────

ARC_RADIUS_TOLERANCE = 0.05  # 5%: R_start vs R_end 허용 편차


@dataclass
class ArcValidationResult:
    """Arc 기하학 검증 결과."""
    valid: bool
    radius_start_m: float
    radius_end_m: float
    delta_ratio: float          # |R_start - R_end| / R_start
    sweep_rad: float            # 호 각도 (양수)
    theta_start: float          # 시작각 (rad)
    theta_end: float            # 종료각 (rad)
    warning: Optional[str] = None
    # 보정된 값 (valid=False일 때 사용)
    corrected_center: Optional[LLA] = None
    corrected_radius_m: float = 0.0


def validate_arc(
    center: LLA,
    start: LLA,
    end: LLA,
    direction: Literal["CW", "CCW"],
) -> ArcValidationResult:
    """
    Arc 기하학을 검증하고, 필요 시 보정된 파라미터를 제공한다.

    검증 항목:
    1. R_start vs R_end 일관성 (ΔR < 5%)
    2. sweep angle 계산
    3. 반경이 너무 작지 않은지 (< 10m)
    """
    r_start = _dist_m(center, start)
    r_end = _dist_m(center, end)

    if r_start < 0.1:
        return ArcValidationResult(
            valid=False,
            radius_start_m=r_start,
            radius_end_m=r_end,
            delta_ratio=1.0,
            sweep_rad=0.0,
            theta_start=0.0,
            theta_end=0.0,
            warning="Arc radius is near zero — degenerate arc",
        )

    delta_ratio = abs(r_start - r_end) / r_start

    theta_start = _angle_rad(center, start)
    theta_end = _angle_rad(center, end)

    # sweep 계산
    if direction == "CW":
        sweep = theta_start - theta_end
        if sweep <= 0:
            sweep += 2 * math.pi
    else:  # CCW
        sweep = theta_end - theta_start
        if sweep <= 0:
            sweep += 2 * math.pi

    warning = None
    corrected_center = None
    corrected_radius = 0.0

    if delta_ratio > ARC_RADIUS_TOLERANCE:
        warning = (
            f"Arc radius inconsistency: R_start={r_start:.1f}m, R_end={r_end:.1f}m "
            f"(ΔR={delta_ratio*100:.1f}%). Reconstructing center..."
        )
        logger.warning(warning)

        # 보정: start-end 중점 기준 수직이등분선 위에 center 재계산
        corrected_center, corrected_radius = reconstruct_arc_center(
            start, end, direction, r_start
        )

    return ArcValidationResult(
        valid=(delta_ratio <= ARC_RADIUS_TOLERANCE),
        radius_start_m=r_start,
        radius_end_m=r_end,
        delta_ratio=delta_ratio,
        sweep_rad=sweep,
        theta_start=theta_start,
        theta_end=theta_end,
        warning=warning,
        corrected_center=corrected_center,
        corrected_radius_m=corrected_radius,
    )


def reconstruct_arc_center(
    start: LLA,
    end: LLA,
    direction: Literal["CW", "CCW"],
    hint_radius: float = 0.0,
) -> tuple[LLA, float]:
    """
    start-end 사이의 수직이등분선 위에서 constant-radius arc center를 재계산한다.

    hint_radius가 주어지면 그 반경을 사용하고,
    아니면 start-end 직선거리의 0.8배를 기본 반경으로 사용한다.
    """
    mid_lat = (start.lat + end.lat) / 2
    mid_lon = (start.lon + end.lon) / 2
    mid_alt = (start.alt + end.alt) / 2

    # start→end 벡터 (미터)
    dx = (end.lon - start.lon) * _m_per_deg_lon(mid_lat)
    dy = (end.lat - start.lat) * M_PER_DEG_LAT

    chord = math.sqrt(dx**2 + dy**2)
    if chord < 1.0:
        return LLA(lat=mid_lat, lon=mid_lon, alt=mid_alt), 1.0

    # 반경 결정
    if hint_radius > chord / 2:
        r = hint_radius
    else:
        r = chord * 0.8  # 최소한 원이 성립하도록

    # 중점에서 center까지의 수선 거리
    half_chord = chord / 2
    if r < half_chord:
        r = half_chord * 1.01  # 원이 chord를 포함하도록
    perp_dist = math.sqrt(r**2 - half_chord**2)

    # 수직이등분선 방향 (chord 벡터에 수직)
    # CW: center를 chord 오른편에, CCW: 왼편에
    nx, ny = -dy / chord, dx / chord  # 시계 방향 법선
    if direction == "CCW":
        nx, ny = -nx, -ny

    center_lat = mid_lat + (ny * perp_dist) / M_PER_DEG_LAT
    center_lon = mid_lon + (nx * perp_dist) / _m_per_deg_lon(mid_lat)

    logger.info(
        "Arc center reconstructed: (%.6f, %.6f) R=%.1fm",
        center_lat, center_lon, r,
    )

    return LLA(lat=center_lat, lon=center_lon, alt=mid_alt), r


# ──────────────────────── Arc 파라미터 계산 ────────────────────

def compute_arc_params(
    center: LLA,
    start: LLA,
    end: LLA,
    direction: Literal["CW", "CCW"],
) -> dict:
    """
    Arc의 핵심 파라미터를 계산한다.

    Returns:
        dict with keys: radius_m, sweep_rad, theta_start, theta_end,
        center (보정 후), valid, warning
    """
    result = validate_arc(center, start, end, direction)

    if result.valid:
        use_center = center
        use_radius = result.radius_start_m
    else:
        if result.corrected_center is not None:
            use_center = result.corrected_center
            use_radius = result.corrected_radius_m
        else:
            use_center = center
            use_radius = result.radius_start_m

    # 보정된 center 기준으로 sweep 재계산
    theta_s = _angle_rad(use_center, start)
    theta_e = _angle_rad(use_center, end)

    if direction == "CW":
        sweep = theta_s - theta_e
        if sweep <= 0:
            sweep += 2 * math.pi
    else:
        sweep = theta_e - theta_s
        if sweep <= 0:
            sweep += 2 * math.pi

    return {
        "center": use_center,
        "radius_m": use_radius,
        "sweep_rad": sweep,
        "theta_start": theta_s,
        "theta_end": theta_e,
        "valid": result.valid,
        "warning": result.warning,
    }


# ──────────────────────── 보간 (시각화용) ────────────────────────

@dataclass
class ArcWaypoint:
    """보간된 원호 웨이포인트 (대시보드 시각화용)."""
    lat: float
    lon: float
    alt: float
    index: int
    heading_deg: float


def interpolate_arc(
    center: LLA,
    start: LLA,
    end: LLA,
    direction: Literal["CW", "CCW"],
    num_points: int = 12,
) -> list[ArcWaypoint]:
    """
    원호 보간: center 기준으로 start→end를 direction 방향으로 등분하여
    num_points개의 웨이포인트를 생성한다.

    이 함수는 대시보드 궤적 미리보기용이며,
    실제 비행 실행에는 do_orbit_arc()가 사용된다.
    """
    if num_points < 2:
        num_points = 2

    lat_rad = math.radians(center.lat)
    m_per_deg_lon = M_PER_DEG_LAT * math.cos(lat_rad)

    dx_start = (start.lon - center.lon) * m_per_deg_lon
    dy_start = (start.lat - center.lat) * M_PER_DEG_LAT

    radius = math.sqrt(dx_start**2 + dy_start**2)
    if radius < 0.1:
        return [
            ArcWaypoint(lat=start.lat, lon=start.lon, alt=start.alt, index=0, heading_deg=0),
            ArcWaypoint(lat=end.lat, lon=end.lon, alt=end.alt, index=1, heading_deg=0),
        ]

    theta_start = math.atan2(dy_start, dx_start)
    dx_end = (end.lon - center.lon) * m_per_deg_lon
    dy_end = (end.lat - center.lat) * M_PER_DEG_LAT
    theta_end = math.atan2(dy_end, dx_end)

    if direction == "CW":
        sweep = theta_start - theta_end
        if sweep <= 0:
            sweep += 2 * math.pi
        sweep = -sweep
    else:
        sweep = theta_end - theta_start
        if sweep <= 0:
            sweep += 2 * math.pi

    waypoints: list[ArcWaypoint] = []

    for i in range(num_points):
        t = i / (num_points - 1)
        theta = theta_start + sweep * t

        x_m = radius * math.cos(theta)
        y_m = radius * math.sin(theta)

        wp_lon = center.lon + x_m / m_per_deg_lon
        wp_lat = center.lat + y_m / M_PER_DEG_LAT
        wp_alt = start.alt + (end.alt - start.alt) * t

        tangent_theta = theta + (math.pi / 2 if direction == "CCW" else -math.pi / 2)
        heading_deg = 90.0 - math.degrees(tangent_theta)
        heading_deg = heading_deg % 360.0

        waypoints.append(
            ArcWaypoint(
                lat=round(wp_lat, 6),
                lon=round(wp_lon, 6),
                alt=round(wp_alt, 1),
                index=i,
                heading_deg=round(heading_deg, 1),
            )
        )

    return waypoints


def arc_length_meters(
    center: LLA,
    start: LLA,
    end: LLA,
    direction: Literal["CW", "CCW"],
) -> float:
    """호의 길이를 미터로 계산한다."""
    lat_rad = math.radians(center.lat)
    m_per_deg_lon = M_PER_DEG_LAT * math.cos(lat_rad)

    dx = (start.lon - center.lon) * m_per_deg_lon
    dy = (start.lat - center.lat) * M_PER_DEG_LAT
    radius = math.sqrt(dx**2 + dy**2)

    theta_start = math.atan2(dy, dx)
    dx_end = (end.lon - center.lon) * m_per_deg_lon
    dy_end = (end.lat - center.lat) * M_PER_DEG_LAT
    theta_end = math.atan2(dy_end, dx_end)

    if direction == "CW":
        sweep = theta_start - theta_end
        if sweep <= 0:
            sweep += 2 * math.pi
    else:
        sweep = theta_end - theta_start
        if sweep <= 0:
            sweep += 2 * math.pi

    return radius * abs(sweep)
