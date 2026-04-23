"""UAM Flight Simulator — Coordinate projection utilities."""

from __future__ import annotations

import math
from typing import Tuple

from .types import LLA, XY


class LocalProjection:
    """Equirectangular projection centred on (lon0, lat0).

    Converts between geographic (lon, lat) and local Cartesian (x_km, y_km)
    using a flat-Earth approximation accurate within tens of km.
    """

    def __init__(self, lon0: float, lat0: float) -> None:
        self.lon0 = lon0
        self.lat0 = lat0
        self._km_per_deg_lat = 111.32
        self._km_per_deg_lon = 111.32 * math.cos(math.radians(lat0))

    def to_xy(self, lon: float, lat: float) -> XY:
        dx = (lon - self.lon0) * self._km_per_deg_lon
        dy = (lat - self.lat0) * self._km_per_deg_lat
        return XY(dx, dy)

    def to_lonlat(self, x_km: float, y_km: float) -> Tuple[float, float]:
        lon = self.lon0 + (x_km / self._km_per_deg_lon)
        lat = self.lat0 + (y_km / self._km_per_deg_lat)
        return lon, lat

    def lla_to_xy(self, lla: LLA) -> XY:
        return self.to_xy(lla.lon, lla.lat)

    def xy_to_lla(self, xy: XY, alt: float) -> LLA:
        lon, lat = self.to_lonlat(xy.x, xy.y)
        return LLA(lat=lat, lon=lon, alt=alt)


def heading_between(p1: XY, p2: XY) -> float:
    """Heading in degrees (0=N, 90=E) from p1 to p2."""
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return 0.0
    h = math.degrees(math.atan2(dx, dy))
    return h % 360.0


def distance_xy(p1: XY, p2: XY) -> float:
    """Distance in metres between two XY points (km coords)."""
    dx = (p2.x - p1.x) * 1000.0
    dy = (p2.y - p1.y) * 1000.0
    return math.hypot(dx, dy)


def interpolate_xy(p1: XY, p2: XY, t: float) -> XY:
    """Linear interpolation between two XY points."""
    return XY(p1.x + (p2.x - p1.x) * t, p1.y + (p2.y - p1.y) * t)


def wrap_heading(deg: float) -> float:
    """Normalise heading to [0, 360)."""
    return deg % 360.0
