from __future__ import annotations

import csv
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from .coord_transform import wgs84_to_local_ned

DEFAULT_AIRSIM_SETTINGS_PATH = Path.home() / "Documents" / "AirSim" / "settings.json"
ROOT_DIR = Path(__file__).resolve().parents[2]
try:
    from ..config import DATA_DIR as _DATA_DIR  # type: ignore
except Exception:  # pragma: no cover — config 미가용 환경용 폴백
    _DATA_DIR = ROOT_DIR / "data"
DEFAULT_VERTIPORT_UE_PATH = _DATA_DIR / "vertiport_UE.csv"
DEFAULT_VERTIPORT_LAYOUT_PATH = _DATA_DIR / "groundmaps" / "Vertiport_round_KU_layout.csv"
DEFAULT_VERTIPORT_MAP_PATH = _DATA_DIR / "vertiportMap_KU.csv"
DEFAULT_CUSTOM_X_AXIS_HEADING_DEG = 90.0
DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG = 180.0
BASE_LAYOUT_X_HEADING_DEG = DEFAULT_CUSTOM_X_AXIS_HEADING_DEG
BASE_LAYOUT_Y_HEADING_DEG = DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG


def get_default_settings_path() -> Path:
    return DEFAULT_AIRSIM_SETTINGS_PATH


def load_airsim_settings_summary(path: Optional[str] = None) -> Dict[str, Any]:
    settings_path = Path(path).expanduser() if path else DEFAULT_AIRSIM_SETTINGS_PATH
    summary: Dict[str, Any] = {
        "path": str(settings_path.resolve()),
        "exists": settings_path.exists(),
        "origin_geopoint": None,
        "vehicles": [],
        "raw": None,
    }
    if not settings_path.exists():
        return summary

    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    summary["raw"] = payload

    origin = payload.get("OriginGeopoint") or {}
    if isinstance(origin, dict):
        summary["origin_geopoint"] = {
            "lat": _to_float(origin.get("Latitude")),
            "lon": _to_float(origin.get("Longitude")),
            "alt_m": _to_float(origin.get("Altitude")),
        }

    vehicles = payload.get("Vehicles") or {}
    if isinstance(vehicles, dict):
        for name in sorted(vehicles.keys()):
            item = vehicles.get(name) or {}
            if not isinstance(item, dict):
                continue
            summary["vehicles"].append({
                "name": str(name),
                "vehicle_type": item.get("VehicleType"),
                "x_m": _to_float(item.get("X")),
                "y_m": _to_float(item.get("Y")),
                "z_m": _to_float(item.get("Z")),
                "yaw_deg": _to_float(item.get("Yaw")),
            })

    return summary


def convert_target_to_unreal(
    *,
    player_start_lat: float,
    player_start_lon: float,
    player_start_alt_m: float,
    target_lat: float,
    target_lon: float,
    target_alt_m: float,
    x_axis_heading_deg: float,
    y_axis_heading_deg: float,
) -> Dict[str, Any]:
    north_m, east_m, down_m = wgs84_to_local_ned(
        target_lat,
        target_lon,
        target_alt_m,
        player_start_lat,
        player_start_lon,
        player_start_alt_m,
    )
    x_axis = _heading_to_ne_unit(x_axis_heading_deg)
    y_axis = _heading_to_ne_unit(y_axis_heading_deg)
    x_m = (north_m * x_axis[0]) + (east_m * x_axis[1])
    y_m = (north_m * y_axis[0]) + (east_m * y_axis[1])
    axis_delta_deg = _normalize_angle_deg(y_axis_heading_deg - x_axis_heading_deg)
    orthogonality_error_deg = min(
        abs(axis_delta_deg - 90.0),
        abs(axis_delta_deg + 90.0),
        abs(abs(axis_delta_deg) - 270.0),
    )
    horizontal_distance_m = math.hypot(north_m, east_m)
    bearing_deg = _normalize_heading_deg(math.degrees(math.atan2(east_m, north_m)))

    return {
        "local_ned_m": {
            "north": north_m,
            "east": east_m,
            "down": down_m,
        },
        "custom_unreal_m": {
            "x": x_m,
            "y": y_m,
            "z": down_m,
        },
        "distance_m": horizontal_distance_m,
        "bearing_deg": bearing_deg,
        "axis_delta_deg": axis_delta_deg,
        "orthogonality_error_deg": orthogonality_error_deg,
    }


def build_vertiport_spawn_layout(
    *,
    vertiport_name: str,
    vertiport_lat: float,
    vertiport_lon: float,
    vertiport_ground_m: Optional[float] = None,
) -> Dict[str, Any]:
    anchor = _match_vertiport_anchor(vertiport_lat, vertiport_lon)
    if anchor is None:
        raise RuntimeError(f"No spawn-layout anchor matched {vertiport_name}.")

    layout_points = _load_layout_points(DEFAULT_VERTIPORT_LAYOUT_PATH)
    pad_center_overrides = _load_pad_center_overrides(DEFAULT_VERTIPORT_MAP_PATH)
    # KU ground layout is authored with its local X/Y axes aligned to 90/180 deg.
    # Each vertiport's AngleDegrees is treated as an additive yaw offset from that base frame.
    x_axis_heading_deg = _normalize_heading_deg(anchor["angle_deg"] + BASE_LAYOUT_X_HEADING_DEG)
    y_axis_heading_deg = _normalize_heading_deg(anchor["angle_deg"] + BASE_LAYOUT_Y_HEADING_DEG)
    points: List[Dict[str, Any]] = []
    base_ground_m = vertiport_ground_m if vertiport_ground_m is not None else 0.0

    for index, point in enumerate(layout_points, start=1):
        override = pad_center_overrides.get(index)
        local_x_cm = override["local_x_cm"] if override else point["local_x_cm"]
        local_y_cm = override["local_y_cm"] if override else point["local_y_cm"]
        local_z_cm = override["local_z_cm"] if override else point["local_z_cm"]
        local_x_m = local_x_cm / 100.0
        local_y_m = local_y_cm / 100.0
        local_z_m = local_z_cm / 100.0
        north_m, east_m = _rotate_layout_to_ne_m(
            local_x_m,
            local_y_m,
            x_axis_heading_deg,
            y_axis_heading_deg,
        )
        lat, lon = _offset_latlon_m(vertiport_lat, vertiport_lon, north_m, east_m)
        points.append({
            "id": f"S{index:02d}",
            "label": point["label"],
            "kind": point["kind"],
            "lat": lat,
            "lon": lon,
            "alt_m": base_ground_m + local_z_m,
            "ground_m": base_ground_m,
            "yaw_deg": _normalize_heading_deg(anchor["angle_deg"] + point["local_yaw_deg"]),
            "local_x_m": local_x_m,
            "local_y_m": local_y_m,
            "local_z_m": local_z_m,
            "north_offset_m": north_m,
            "east_offset_m": east_m,
            "layout_world_x_cm": point["world_x_cm"],
            "layout_world_y_cm": point["world_y_cm"],
            "layout_world_z_cm": point["world_z_cm"],
            "pad_center_override": bool(override),
            "source_local_x_cm": point["local_x_cm"],
            "source_local_y_cm": point["local_y_cm"],
            "source_local_z_cm": point["local_z_cm"],
            "semantic_id": override.get("semantic_id") if override else None,
        })

    return {
        "vertiport_name": vertiport_name,
        "center": {
            "lat": vertiport_lat,
            "lon": vertiport_lon,
            "ground_m": vertiport_ground_m,
        },
        "layout_name": "Vertiport_round_KU",
        "source_anchor": anchor,
        "base_layout_heading_deg": {
            "x": BASE_LAYOUT_X_HEADING_DEG,
            "y": BASE_LAYOUT_Y_HEADING_DEG,
        },
        "frame_heading_deg": {
            "x": x_axis_heading_deg,
            "y": y_axis_heading_deg,
        },
        "points": points,
    }


def get_vertiport_spawn_point(
    *,
    vertiport_name: str,
    vertiport_lat: float,
    vertiport_lon: float,
    spawn_point_id: str,
    vertiport_ground_m: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    layout = build_vertiport_spawn_layout(
        vertiport_name=vertiport_name,
        vertiport_lat=vertiport_lat,
        vertiport_lon=vertiport_lon,
        vertiport_ground_m=vertiport_ground_m,
    )
    target_id = str(spawn_point_id or "").strip().upper()
    for point in layout.get("points", []):
        if str(point.get("id") or "").strip().upper() == target_id:
            return {
                **point,
                "vertiport_name": layout.get("vertiport_name"),
                "frame_heading_deg": layout.get("frame_heading_deg"),
                "source_anchor": layout.get("source_anchor"),
            }
    return None


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _heading_to_ne_unit(heading_deg: float) -> tuple[float, float]:
    rad = math.radians(float(heading_deg))
    return math.cos(rad), math.sin(rad)


def _normalize_heading_deg(angle_deg: float) -> float:
    value = float(angle_deg) % 360.0
    return value if value >= 0 else value + 360.0


def _normalize_angle_deg(angle_deg: float) -> float:
    value = (float(angle_deg) + 180.0) % 360.0
    if value < 0:
        value += 360.0
    return value - 180.0


@lru_cache(maxsize=1)
def _load_vertiport_anchors(path: Path) -> List[Dict[str, Any]]:
    anchors: List[Dict[str, Any]] = []
    for row in _read_csv_rows(path):
        lat = _to_float(row.get("Latitude"))
        lon = _to_float(row.get("Longitude"))
        angle_deg = _to_float(row.get("AngleDegrees"))
        if lat is None or lon is None or angle_deg is None:
            continue
        anchors.append({
            "name": str(row.get("Name") or "").strip(),
            "class_name": str(row.get("Class") or "").strip(),
            "lat": lat,
            "lon": lon,
            "angle_deg": angle_deg,
        })
    return anchors


def _match_vertiport_anchor(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    anchors = _load_vertiport_anchors(DEFAULT_VERTIPORT_UE_PATH)
    if not anchors:
        return None
    best = min(anchors, key=lambda item: _haversine_m(lat, lon, item["lat"], item["lon"]))
    distance_m = _haversine_m(lat, lon, best["lat"], best["lon"])
    if distance_m > 250.0:
        return None
    return {
        **best,
        "match_distance_m": distance_m,
    }


@lru_cache(maxsize=1)
def _load_layout_points(path: Path) -> List[Dict[str, Any]]:
    rows = _read_csv_rows(path)
    points: List[Dict[str, Any]] = []
    for row in rows:
        kind = str(row.get("kind") or "").strip().lower()
        local_x_cm = _to_float(row.get("local_x_cm"))
        local_y_cm = _to_float(row.get("local_y_cm"))
        local_z_cm = _to_float(row.get("local_z_cm"))
        if kind != "marker" or local_x_cm is None or local_y_cm is None or local_z_cm is None:
            continue
        points.append({
            "label": str(row.get("actor_label") or row.get("actor_name") or "Marker").strip(),
            "kind": kind,
            "local_x_cm": local_x_cm,
            "local_y_cm": local_y_cm,
            "local_z_cm": local_z_cm,
            "local_yaw_deg": _to_float(row.get("local_yaw_deg")) or 0.0,
            "world_x_cm": _to_float(row.get("world_x_cm")),
            "world_y_cm": _to_float(row.get("world_y_cm")),
            "world_z_cm": _to_float(row.get("world_z_cm")),
        })
    return sorted(points, key=lambda item: _label_sort_key(item["label"]))


@lru_cache(maxsize=1)
def _load_pad_center_overrides(path: Path) -> Dict[int, Dict[str, Any]]:
    overrides: Dict[int, Dict[str, Any]] = {}
    for row in _read_csv_rows(path):
        node_type = str(row.get("node_type") or "").strip().lower()
        semantic_id = str(row.get("semantic_id") or "").strip().upper()
        if node_type != "pad" or semantic_id not in {"F1", "F2"}:
            continue
        try:
            node_id = int(str(row.get("node_id") or "").strip())
        except ValueError:
            continue
        local_x_cm = _to_float(row.get("local_x_cm"))
        local_y_cm = _to_float(row.get("local_y_cm"))
        local_z_cm = _to_float(row.get("local_z_cm"))
        if local_x_cm is None or local_y_cm is None or local_z_cm is None:
            continue
        overrides[node_id] = {
            "semantic_id": semantic_id,
            "local_x_cm": local_x_cm,
            "local_y_cm": local_y_cm,
            "local_z_cm": local_z_cm,
            "source_layout_marker": str(row.get("source_layout_marker") or "").strip(),
        }
    return overrides


def _read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    for encoding in ("utf-8-sig", "cp949", "utf-8", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Could not decode CSV file: {path}")


def _label_sort_key(label: str) -> tuple[str, int]:
    text = str(label or "").strip()
    match = re.match(r"^(.*?)(\d+)$", text)
    if not match:
        return (text, 0)
    return (match.group(1), int(match.group(2)))


def _rotate_layout_to_ne_m(
    local_x_m: float,
    local_y_m: float,
    x_axis_heading_deg: float,
    y_axis_heading_deg: float,
) -> tuple[float, float]:
    x_axis = _heading_to_ne_unit(x_axis_heading_deg)
    y_axis = _heading_to_ne_unit(y_axis_heading_deg)
    north_m = (local_x_m * x_axis[0]) + (local_y_m * y_axis[0])
    east_m = (local_x_m * x_axis[1]) + (local_y_m * y_axis[1])
    return north_m, east_m


def _offset_latlon_m(lat_deg: float, lon_deg: float, north_m: float, east_m: float) -> tuple[float, float]:
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = max(1.0, math.cos(math.radians(lat_deg)) * meters_per_deg_lat)
    return (
        lat_deg + (north_m / meters_per_deg_lat),
        lon_deg + (east_m / meters_per_deg_lon),
    )


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6371000.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(d_lon / 2.0) ** 2
    )
    return radius_m * 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
