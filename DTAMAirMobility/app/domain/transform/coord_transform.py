"""WGS84 → Local NED 변환 유틸리티.

DTAM 4001 ``position`` 은 local NED (m). 각 비행체마다 원점(보통 출발 버티포트)을
고정하고, 매 tick 마다 위도/경도/고도를 NED 로 환산해 송출한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


# WGS84
WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)


def _deg2rad(deg: float) -> float:
    return deg * math.pi / 180.0


def geodetic_to_ecef(lat_deg: float, lon_deg: float, h_m: float = 0.0) -> Tuple[float, float, float]:
    lat = _deg2rad(lat_deg)
    lon = _deg2rad(lon_deg)
    s = math.sin(lat)
    c = math.cos(lat)
    n = WGS84_A / math.sqrt(1.0 - WGS84_E2 * s * s)
    x = (n + h_m) * c * math.cos(lon)
    y = (n + h_m) * c * math.sin(lon)
    z = ((1.0 - WGS84_E2) * n + h_m) * s
    return x, y, z


def ecef_to_enu(
    x: float, y: float, z: float,
    lat0_deg: float, lon0_deg: float, h0_m: float = 0.0,
) -> Tuple[float, float, float]:
    x0, y0, z0 = geodetic_to_ecef(lat0_deg, lon0_deg, h0_m)
    dx, dy, dz = x - x0, y - y0, z - z0
    lat0 = _deg2rad(lat0_deg)
    lon0 = _deg2rad(lon0_deg)
    slat, clat = math.sin(lat0), math.cos(lat0)
    slon, clon = math.sin(lon0), math.cos(lon0)
    e = -slon * dx + clon * dy
    n = -slat * clon * dx - slat * slon * dy + clat * dz
    u = clat * clon * dx + clat * slon * dy + slat * dz
    return e, n, u


def geodetic_to_enu(
    lat_deg: float, lon_deg: float, h_m: float,
    lat0_deg: float, lon0_deg: float, h0_m: float = 0.0,
) -> Tuple[float, float, float]:
    x, y, z = geodetic_to_ecef(lat_deg, lon_deg, h_m)
    return ecef_to_enu(x, y, z, lat0_deg, lon0_deg, h0_m)


def wgs84_to_local_ned(
    lat_deg: float, lon_deg: float, h_m: float,
    lat0_deg: float, lon0_deg: float, h0_m: float = 0.0,
) -> Tuple[float, float, float]:
    """WGS84 → local NED (north, east, down) [m]."""
    e, n, u = geodetic_to_enu(lat_deg, lon_deg, h_m, lat0_deg, lon0_deg, h0_m)
    return float(n), float(e), float(-u)


def heading_to_ned_velocity(speed_mps: float, heading_deg: float) -> Tuple[float, float, float]:
    """Ground-track heading(북=0, 시계방향) → NED 속도 (vn, ve, vd)."""
    rad = math.radians(float(heading_deg))
    vn = float(speed_mps) * math.cos(rad)
    ve = float(speed_mps) * math.sin(rad)
    vd = 0.0
    return vn, ve, vd


@dataclass
class LocalNEDFrame:
    """특정 원점을 기준으로 하는 NED 프레임."""
    origin_lat: float
    origin_lon: float
    origin_alt_m: float = 0.0

    def to_ned(self, lat: float, lon: float, alt_m: float) -> Tuple[float, float, float]:
        return wgs84_to_local_ned(
            float(lat), float(lon), float(alt_m),
            float(self.origin_lat), float(self.origin_lon), float(self.origin_alt_m),
        )

    def as_dict(self) -> dict:
        return {
            "origin_lat": float(self.origin_lat),
            "origin_lon": float(self.origin_lon),
            "origin_alt_m": float(self.origin_alt_m),
        }
