from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple
import csv
import math

import numpy as np

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)

JSON_XY_DIV = 100.0
JSON_Z_DIV = 100.0
AIRSIM_D_BIAS = 3.0

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RESOURCES_VP = ROOT_DIR / "data" / "resources_vp.csv"

GCP_LIST = [
    ("SEOUL_CITY_HALL", 37.566831, 126.978445, (217063.379391, -1013419.868553, -220649.796452)),
    ("GIMPO_VERTIPORT", 37.563535, 126.791805, (-1431694.121809, -979217.553043, -221157.611723)),
    ("YEOUIDO", 37.525491, 126.921490, (-285967.804749, -555936.730254, -221891.377864)),
    ("CHEONHO_4WAY", 37.538658, 127.123442, (1498921.351312, -703218.244679, -223002.980913)),
    ("SUSEO_IC", 37.483396, 127.025980, (638658.814081, -89106.174219, -221891.377864)),
    ("IMUN_YARD", 37.603812, 127.068543, (1013805.274583, -1424832.145135, -223125.441155)),
    ("YEONSINNAE", 37.618936, 126.921349, (-287516.699663, -1593208.781614, -222297.078953)),
]

CITY_HALL_NAME = "SEOUL_CITY_HALL"


def _deg2rad(deg: float) -> float:
    return deg * math.pi / 180.0


def _geodetic_to_ecef(lat_deg: float, lon_deg: float, h_m: float = 0.0) -> np.ndarray:
    lat = _deg2rad(lat_deg)
    lon = _deg2rad(lon_deg)
    s = math.sin(lat)
    c = math.cos(lat)
    n = WGS84_A / math.sqrt(1.0 - WGS84_E2 * s * s)
    x = (n + h_m) * c * math.cos(lon)
    y = (n + h_m) * c * math.sin(lon)
    z = ((1.0 - WGS84_E2) * n + h_m) * s
    return np.array([x, y, z], dtype=float)


def _ecef_to_enu(xyz: np.ndarray, lat0_deg: float, lon0_deg: float, h0_m: float = 0.0) -> np.ndarray:
    x0, y0, z0 = _geodetic_to_ecef(lat0_deg, lon0_deg, h0_m)
    dx, dy, dz = xyz[0] - x0, xyz[1] - y0, xyz[2] - z0
    lat0 = _deg2rad(lat0_deg)
    lon0 = _deg2rad(lon0_deg)
    slat, clat = math.sin(lat0), math.cos(lat0)
    slon, clon = math.sin(lon0), math.cos(lon0)
    e = -slon * dx + clon * dy
    n = -slat * clon * dx - slat * slon * dy + clat * dz
    u = clat * clon * dx + clat * slon * dy + slat * dz
    return np.array([e, n, u], dtype=float)


def _geodetic_to_enu(
    lat_deg: float, lon_deg: float, lat0_deg: float, lon0_deg: float, h_m: float = 0.0, h0_m: float = 0.0
) -> np.ndarray:
    return _ecef_to_enu(_geodetic_to_ecef(lat_deg, lon_deg, h_m), lat0_deg, lon0_deg, h0_m)


class AffineGeoToUEMapper:
    def __init__(self, gcps: Sequence[Tuple[str, float, float, Sequence[float]]]) -> None:
        city = [g for g in gcps if g[0] == CITY_HALL_NAME][0]
        self.lat0, self.lon0 = city[1], city[2]
        self._fit(gcps)

    def _fit(self, gcps: Sequence[Tuple[str, float, float, Sequence[float]]]) -> None:
        rows = []
        xs, ys, zs = [], [], []
        for _, lat, lon, ue in gcps:
            e, n, u = _geodetic_to_enu(lat, lon, self.lat0, self.lon0)
            rows.append([e, n, u, 1.0])
            xs.append(ue[0])
            ys.append(ue[1])
            zs.append(ue[2])

        a = np.asarray(rows, dtype=float)
        x = np.asarray(xs, dtype=float)
        y = np.asarray(ys, dtype=float)
        z = np.asarray(zs, dtype=float)
        cx, *_ = np.linalg.lstsq(a, x, rcond=None)
        cy, *_ = np.linalg.lstsq(a, y, rcond=None)
        cz, *_ = np.linalg.lstsq(a, z, rcond=None)
        self.M = np.vstack([cx, cy, cz])

    def geodetic_to_ue(self, lat_deg: float, lon_deg: float, h_m: float = 0.0) -> np.ndarray:
        e, n, u = _geodetic_to_enu(lat_deg, lon_deg, self.lat0, self.lon0, h_m, 0.0)
        v = np.array([e, n, u, 1.0], dtype=float)
        return self.M @ v


_MAPPER: Optional[AffineGeoToUEMapper] = None


def get_mapper() -> AffineGeoToUEMapper:
    global _MAPPER
    if _MAPPER is None:
        _MAPPER = AffineGeoToUEMapper(GCP_LIST)
    return _MAPPER


def _get_city_hall_ue() -> Tuple[float, float, float]:
    for name, _, _, ue in GCP_LIST:
        if name == CITY_HALL_NAME:
            return ue
    raise RuntimeError("CITY_HALL_NAME missing from GCP_LIST.")


CITY_HALL_UE = _get_city_hall_ue()


def wgs84_to_ue_ch_cm(lat: float, lon: float, h_m: float = 0.0) -> Tuple[float, float, float]:
    mapper = get_mapper()
    ax_abs, ay_abs, az_abs = mapper.geodetic_to_ue(lat, lon, h_m)
    chx, chy, chz = CITY_HALL_UE
    return float(ax_abs - chx), float(ay_abs - chy), float(az_abs - chz)


def wgs84_to_airsim_ned(lat: float, lon: float, alt_m: float = 0.0) -> Tuple[float, float, float]:
    x_cm, y_cm, z_cm = wgs84_to_ue_ch_cm(lat, lon, alt_m)
    n_m = x_cm / JSON_XY_DIV
    e_m = y_cm / JSON_XY_DIV
    d_m = (-z_cm / JSON_Z_DIV) + AIRSIM_D_BIAS
    return n_m, e_m, d_m


def wgs84_to_local_ned(
    lat: float,
    lon: float,
    alt_m: float,
    lat0: float,
    lon0: float,
    alt0_m: float = 0.0,
) -> Tuple[float, float, float]:
    e, n, u = _geodetic_to_enu(lat, lon, lat0, lon0, alt_m, alt0_m)
    return float(n), float(e), float(-u)


_RES_VP_CACHE: Optional[Dict[Tuple[str, str], Dict[str, float]]] = None


def load_resources_vp(csv_path: Optional[str] = None) -> Dict[Tuple[str, str], Dict[str, float]]:
    global _RES_VP_CACHE
    path = Path(csv_path) if csv_path else DEFAULT_RESOURCES_VP
    mapping: Dict[Tuple[str, str], Dict[str, float]] = {}
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                vp = str(row.get("Vertiport", "")).strip()
                label = str(row.get("Label", "")).strip().upper()
                if not vp or not label:
                    continue

                def _num(*names: str) -> Optional[float]:
                    for name in names:
                        value = row.get(name)
                        if value is None:
                            continue
                        text = str(value).strip()
                        if not text:
                            continue
                        try:
                            return float(text)
                        except ValueError:
                            continue
                    return None

                mapping[(vp, label)] = {
                    "Z_m": _num("Z_m", "Z_M"),
                    "Z_cm": _num("Z_cm", "Z_CM"),
                    "Yaw_deg": _num("Yaw_deg", "Angle_deg", "Yaw", "Angle"),
                    "X_m": _num("X_m"),
                    "Y_m": _num("Y_m"),
                }
    _RES_VP_CACHE = mapping
    return mapping


def lookup_vp_label_alt_m(vertiport: str, label: str) -> Optional[float]:
    global _RES_VP_CACHE
    if _RES_VP_CACHE is None:
        load_resources_vp(None)
    if _RES_VP_CACHE is None:
        return None
    key = (str(vertiport).strip(), str(label).strip().upper())
    record = _RES_VP_CACHE.get(key)
    if not record:
        return None
    value = record.get("Z_m")
    return float(value) if value is not None else None
