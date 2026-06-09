"""DTAM Mission Planner FastAPI 서버.

odt_mp/app/server.py 의 미션 계획 관련 엔드포인트를 그대로 보존하되,
AirSim / mission_runner / telemetry / simulator_service 관련 기능은 모두
제거하였다. 대신 DTAM 3001 (Scheduled Flight) 송신 엔드포인트를 추가한다.
"""
from __future__ import annotations

import asyncio
import csv
import json
import math
import re
import subprocess
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import (
    DATA_DIR,
    DEM_DIR,
    DEM_MAX_ZOOM,
    DEM_TILE_SIZE,
    DEFAULT_CENTER_LAT,
    DEFAULT_CENTER_LON,
    DEFAULT_START_ZOOM,
    MBTILES_PATH,
    STATIC_DIR,
)
from .domain.converter_tool import (
    DEFAULT_CUSTOM_X_AXIS_HEADING_DEG,
    DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG,
    build_vertiport_spawn_layout,
    convert_target_to_unreal,
    get_vertiport_spawn_point,
    load_airsim_settings_summary,
)
from .domain.unreal_spawn_mapping import lookup_unreal_spawn_point
from .services.mission_service import MissionService
from .services.mbtiles import MBTiles
from .services.route_planner import RoutePlanner
from .state import state


MISSION_ICD_RESOURCE_CSV = DATA_DIR / "resources_vp.csv"
VERTIPORT_SURFACE_CLEARANCE_M = 10.0
ROUTE_RESOURCE_ALIASES = {
    "여의도": "영등포",
}
# 런타임 상태 (mbtiles, route_planner, dem_provider, mission_service, settings) 는
# app.state 모듈의 ``state`` 컨테이너 (싱글턴) 에 보관. helpers 와 routes 모두
# 이 컨테이너를 단일 소스로 읽는다 — ``global`` 키워드 사용 없음.
settings = state.settings  # 후방 호환 (기존 helpers 가 ``settings[...]`` 으로 읽는 코드)


# ── 공통 유틸 (odt_mp 서버에서 그대로 가져옴) ──────────────────────────────
def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_m * math.atan2(math.sqrt(a), math.sqrt(max(1 - a, 0)))


def _densify_route_points(
    points: List[tuple[float, float]], step_m: float = 60.0
) -> List[tuple[float, float]]:
    if len(points) < 2:
        return points
    dense = [points[0]]
    for idx in range(1, len(points)):
        lon1, lat1 = points[idx - 1]
        lon2, lat2 = points[idx]
        distance_m = _haversine_m(lon1, lat1, lon2, lat2)
        steps = max(1, int(distance_m // step_m))
        for part in range(1, steps + 1):
            t = part / steps
            dense.append((
                lon1 + ((lon2 - lon1) * t),
                lat1 + ((lat2 - lat1) * t),
            ))
    return dense


def _sample_ground_optional_m(lon: float, lat: float) -> Optional[float]:
    dem = state.dem_provider
    if dem is None or not getattr(dem, "available", False):
        return None
    try:
        value = dem.sample_elevation(lon, lat)
    except Exception:
        value = None
    return float(value) if value is not None else None


def _sample_ground_m(lon: float, lat: float) -> float:
    value = _sample_ground_optional_m(lon, lat)
    return value if value is not None else 0.0


def _coerce_int(value: Any) -> Optional[int]:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


# ICD bundle helpers (_normalize_simulation_fleet, _build_existing_icd_export_bundle,
# _build_mission_icd_bundle, _extract_records_from_export, _looks_like_icd_record*)
# 는 모두 MissionService 의 메서드로 이동했음. routes 는
# server.mission_service.X 로 호출.


def _route_absolute_altitude_m(waypoints_with_alt: List[Dict[str, Any]]) -> float:
    waypoint_alts = [
        float(item.get("alt_m", 0) or 0)
        for item in waypoints_with_alt
        if float(item.get("alt_m", 0) or 0) > 0
    ]
    return max(state.settings["default_altitude_m"], max(waypoint_alts, default=0.0))


def _build_route_point_payload(
    raw_points: List[tuple[float, float]], absolute_alt_m: float
) -> List[Dict[str, float]]:
    dense_points = _densify_route_points(raw_points)
    payload: List[Dict[str, float]] = []
    for lon, lat in dense_points:
        payload.append({
            "lon": lon,
            "lat": lat,
            "ground_m": _sample_ground_m(lon, lat),
            "alt_m": absolute_alt_m,
        })
    return payload


def _polyline_distance_km(points: List[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    distance_m = 0.0
    for idx in range(1, len(points)):
        lon1, lat1 = points[idx - 1]
        lon2, lat2 = points[idx]
        distance_m += _haversine_m(lon1, lat1, lon2, lat2)
    return distance_m / 1000.0


def _build_route_waypoint(
    *,
    name: str,
    lat: float,
    lon: float,
    ground_m: float,
    alt_m: float,
    waypoint_type: str,
    spawn_point_id: Optional[str] = None,
    yaw_deg: Optional[float] = None,
    airsim_x_m: Optional[float] = None,
    airsim_y_m: Optional[float] = None,
    airsim_z_m: Optional[float] = None,
    airsim_spawn_z_m: Optional[float] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "name": name,
        "lat": lat,
        "lon": lon,
        "ground_m": ground_m,
        "alt_ft": None,
        "alt_m": alt_m,
        "type": waypoint_type,
    }
    if spawn_point_id:
        payload["spawn_point_id"] = spawn_point_id
    if yaw_deg is not None:
        payload["yaw_deg"] = float(yaw_deg) % 360.0
    if airsim_x_m is not None:
        payload["airsim_x_m"] = float(airsim_x_m)
    if airsim_y_m is not None:
        payload["airsim_y_m"] = float(airsim_y_m)
    if airsim_z_m is not None:
        payload["airsim_z_m"] = float(airsim_z_m)
    if airsim_spawn_z_m is not None:
        payload["airsim_spawn_z_m"] = float(airsim_spawn_z_m)
    return payload


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def _load_route_resource_catalog() -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    rows: List[Dict[str, Any]] = []
    for encoding in ("utf-8-sig", "cp949", "utf-8", "latin-1"):
        try:
            with MISSION_ICD_RESOURCE_CSV.open("r", encoding=encoding, newline="") as handle:
                rows = list(csv.DictReader(handle))
            break
        except UnicodeDecodeError:
            continue

    catalog: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for row in rows:
        vertiport = str(row.get("Vertiport") or "").strip()
        category = str(row.get("Category") or "").strip().upper()
        label = str(row.get("Label") or "").strip()
        lat = _to_float(row.get("pt_lat_deg"))
        lon = _to_float(row.get("pt_lon_deg"))
        alt_m = _to_float(row.get("pt_h_m"))
        ground_m = _to_float(row.get("Z_m"))
        x_m = _to_float(row.get("X_m"))
        y_m = _to_float(row.get("Y_m"))
        yaw_deg = _to_float(row.get("Yaw_deg"))
        if not vertiport or not category or lat is None or lon is None:
            continue
        catalog.setdefault(vertiport, {}).setdefault(category, []).append({
            "label": label,
            "lat": float(lat),
            "lon": float(lon),
            "alt_m": float(alt_m if alt_m is not None else ground_m or 0.0),
            "ground_m": float(ground_m if ground_m is not None else alt_m or 0.0),
            "airsim_x_m": float(x_m) if x_m is not None else None,
            "airsim_y_m": float(y_m) if y_m is not None else None,
            "airsim_z_m": float(ground_m) if ground_m is not None else None,
            "yaw_deg": float(yaw_deg) if yaw_deg is not None else None,
        })

    for per_vertiport in catalog.values():
        for category, points in per_vertiport.items():
            per_vertiport[category] = sorted(
                points,
                key=lambda item: _resource_label_sort_key(str(item.get("label") or "")),
            )
    return catalog


def _resource_label_sort_key(label: str) -> tuple[str, int]:
    text = str(label or "").strip()
    match = re.match(r"^(.*?)(\d+)$", text)
    if not match:
        return (text, 0)
    return (match.group(1), int(match.group(2)))


def _pick_route_resource_point(
    vertiport_name: str,
    category: str,
    *,
    preferred_label: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    catalog = _load_route_resource_catalog()
    resource_name = str(vertiport_name or "").strip()
    if resource_name not in catalog:
        alias = ROUTE_RESOURCE_ALIASES.get(resource_name)
        if alias in catalog:
            resource_name = alias
    points = catalog.get(resource_name, {}).get(str(category or "").strip().upper(), [])
    if preferred_label:
        target = str(preferred_label).strip().upper()
        for point in points:
            if str(point.get("label") or "").strip().upper() == target:
                return point
    return points[0] if points else None


def _route_waypoint_from_unreal_spawn(
    vertiport_name: str,
    spawn: Dict[str, Any],
    *,
    fallback_ground_m: float,
    waypoint_type: str,
    display_label: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    lat = _to_float(spawn.get("lat"))
    lon = _to_float(spawn.get("lon"))
    if lat is None or lon is None:
        return None
    label = str(spawn.get("spawn_label") or spawn.get("label") or display_label or "").strip()
    s_id = str(spawn.get("spawn_point_id") or "").strip()
    ground_m = _to_float(spawn.get("ground_m"))
    if ground_m is None:
        ground_m = fallback_ground_m
    alt_m = _to_float(spawn.get("alt_m"))
    if alt_m is None:
        alt_m = float(ground_m) + VERTIPORT_SURFACE_CLEARANCE_M
    name_suffix = f"{s_id} {label}".strip() or str(display_label or "").strip()
    return _build_route_waypoint(
        name=f"{vertiport_name} {name_suffix}".strip(),
        lat=float(lat),
        lon=float(lon),
        ground_m=float(ground_m),
        alt_m=float(alt_m),
        waypoint_type=waypoint_type,
        spawn_point_id=s_id or label or None,
        yaw_deg=_to_float(spawn.get("yaw_deg")),
        airsim_x_m=_to_float(spawn.get("airsim_x_m")),
        airsim_y_m=_to_float(spawn.get("airsim_y_m")),
        airsim_z_m=_to_float(spawn.get("airsim_z_m")),
        airsim_spawn_z_m=_to_float(spawn.get("airsim_spawn_z_m")),
    )


def _resolve_departure_takeoff_waypoint(
    route_planner: RoutePlanner,
    departure_name: str,
    fallback_ground_m: float,
) -> Optional[Dict[str, Any]]:
    port = route_planner.ports.get(departure_name)
    if port is None:
        return None

    unreal_spawn = lookup_unreal_spawn_point(
        departure_name,
        category="FATO",
        preferred_label="FATO 2",
        spawn_point_id="S25",
    )
    if unreal_spawn is not None:
        waypoint = _route_waypoint_from_unreal_spawn(
            departure_name,
            unreal_spawn,
            fallback_ground_m=fallback_ground_m,
            waypoint_type="departure_takeoff",
            display_label="F2",
        )
        if waypoint is not None:
            return waypoint

    resource = _pick_route_resource_point(departure_name, "FATO", preferred_label="FATO 2")
    if resource is None:
        resource = _pick_route_resource_point(departure_name, "FATO")
    if resource is not None:
        label = str(resource.get("label") or "FATO")
        return _build_route_waypoint(
            name=f"{departure_name} {label}",
            lat=float(resource["lat"]),
            lon=float(resource["lon"]),
            ground_m=float(resource.get("ground_m") or fallback_ground_m),
            alt_m=float(resource.get("ground_m") or fallback_ground_m) + VERTIPORT_SURFACE_CLEARANCE_M,
            waypoint_type="departure_takeoff",
            spawn_point_id=label,
            yaw_deg=_to_float(resource.get("yaw_deg")),
            airsim_x_m=_to_float(resource.get("airsim_x_m")),
            airsim_y_m=_to_float(resource.get("airsim_y_m")),
            airsim_z_m=_to_float(resource.get("airsim_z_m")),
        )
    spawn = _get_route_spawn_waypoint(
        route_planner,
        departure_name,
        "S25",
        fallback_ground_m,
        waypoint_type="departure_takeoff",
        display_label="F2",
    )
    if spawn is not None:
        return spawn

    return _build_route_waypoint(
        name=departure_name,
        lat=float(port.lat),
        lon=float(port.lon),
        ground_m=fallback_ground_m,
        alt_m=fallback_ground_m + VERTIPORT_SURFACE_CLEARANCE_M,
        waypoint_type="departure_takeoff",
    )


def _resolve_arrival_landing_waypoint(
    route_planner: RoutePlanner,
    arrival_name: str,
    fallback_ground_m: float,
) -> Optional[Dict[str, Any]]:
    port = route_planner.ports.get(arrival_name)
    if port is None:
        return None

    unreal_spawn = lookup_unreal_spawn_point(
        arrival_name,
        category="FATO",
        preferred_label="FATO 1",
        spawn_point_id="S26",
    )
    if unreal_spawn is not None:
        waypoint = _route_waypoint_from_unreal_spawn(
            arrival_name,
            unreal_spawn,
            fallback_ground_m=fallback_ground_m,
            waypoint_type="arrival_touchdown",
            display_label="F1",
        )
        if waypoint is not None:
            return waypoint

    resource = _pick_route_resource_point(arrival_name, "FATO", preferred_label="FATO 1")
    if resource is None:
        resource = _pick_route_resource_point(arrival_name, "FATO")
    if resource is not None:
        label = str(resource.get("label") or "FATO")
        return _build_route_waypoint(
            name=f"{arrival_name} {label}",
            lat=float(resource["lat"]),
            lon=float(resource["lon"]),
            ground_m=float(resource.get("ground_m") or fallback_ground_m),
            alt_m=float(resource.get("ground_m") or fallback_ground_m) + VERTIPORT_SURFACE_CLEARANCE_M,
            waypoint_type="arrival_touchdown",
            spawn_point_id=label,
            yaw_deg=_to_float(resource.get("yaw_deg")),
            airsim_x_m=_to_float(resource.get("airsim_x_m")),
            airsim_y_m=_to_float(resource.get("airsim_y_m")),
            airsim_z_m=_to_float(resource.get("airsim_z_m")),
        )
    spawn = _get_route_spawn_waypoint(
        route_planner,
        arrival_name,
        "S26",
        fallback_ground_m,
        waypoint_type="arrival_touchdown",
        display_label="F1",
    )
    if spawn is not None:
        return spawn

    return _build_route_waypoint(
        name=arrival_name,
        lat=float(port.lat),
        lon=float(port.lon),
        ground_m=fallback_ground_m,
        alt_m=fallback_ground_m + VERTIPORT_SURFACE_CLEARANCE_M,
        waypoint_type="arrival_touchdown",
    )


def _get_route_spawn_waypoint(
    route_planner: RoutePlanner,
    vertiport_name: str,
    spawn_point_id: str,
    fallback_ground_m: float,
    *,
    waypoint_type: str,
    display_label: str,
) -> Optional[Dict[str, Any]]:
    port = route_planner.ports.get(vertiport_name)
    if port is None:
        return None
    unreal_spawn = lookup_unreal_spawn_point(
        vertiport_name,
        spawn_point_id=spawn_point_id,
    )
    if unreal_spawn is not None:
        waypoint = _route_waypoint_from_unreal_spawn(
            vertiport_name,
            unreal_spawn,
            fallback_ground_m=fallback_ground_m,
            waypoint_type=waypoint_type,
            display_label=display_label,
        )
        if waypoint is not None:
            return waypoint

    ground_m = _sample_ground_optional_m(port.lon, port.lat)
    if ground_m is None:
        ground_m = fallback_ground_m
    try:
        spawn = get_vertiport_spawn_point(
            vertiport_name=vertiport_name,
            vertiport_lat=float(port.lat),
            vertiport_lon=float(port.lon),
            vertiport_ground_m=float(ground_m),
            spawn_point_id=spawn_point_id,
        )
    except Exception:
        spawn = None
    if spawn is None:
        return None
    spawn_ground_m = float(spawn.get("ground_m") or ground_m or 0.0)
    spawn_alt_m = spawn_ground_m + VERTIPORT_SURFACE_CLEARANCE_M
    return _build_route_waypoint(
        name=f"{vertiport_name} {spawn_point_id} {display_label}",
        lat=float(spawn["lat"]),
        lon=float(spawn["lon"]),
        ground_m=spawn_ground_m,
        alt_m=spawn_alt_m,
        waypoint_type=waypoint_type,
        spawn_point_id=spawn_point_id,
        yaw_deg=_to_float(spawn.get("yaw_deg")),
    )


def _build_route_mission_waypoints(
    route_waypoints: List[Dict[str, Any]],
    route_alt_m: float,
) -> List[Dict[str, Any]]:
    if not route_waypoints:
        return []

    mission_waypoints: List[Dict[str, Any]] = []
    start = dict(route_waypoints[0])
    start["alt_m"] = route_alt_m
    mission_waypoints.append(start)

    for waypoint in route_waypoints[1:-1]:
        if str(waypoint.get("type") or "").strip().lower() == "vertiport":
            continue
        mission_waypoints.append(dict(waypoint))

    if len(route_waypoints) > 1:
        mission_waypoints.append(dict(route_waypoints[-1]))
    return mission_waypoints


def _build_quadratic_connector_points(
    start: tuple[float, float],
    control: tuple[float, float],
    end: tuple[float, float],
    *,
    step_m: float = 80.0,
    include_start: bool = True,
    include_end: bool = True,
) -> List[tuple[float, float]]:
    approx_length_m = (
        _haversine_m(start[0], start[1], control[0], control[1])
        + _haversine_m(control[0], control[1], end[0], end[1])
    )
    steps = max(4, int(approx_length_m // max(step_m, 20.0)))
    points: List[tuple[float, float]] = []
    for index in range(steps + 1):
        if index == 0 and not include_start:
            continue
        if index == steps and not include_end:
            continue
        t = index / steps
        omt = 1.0 - t
        lon = (omt * omt * start[0]) + (2.0 * omt * t * control[0]) + (t * t * end[0])
        lat = (omt * omt * start[1]) + (2.0 * omt * t * control[1]) + (t * t * end[1])
        points.append((lon, lat))
    return points


def _replace_final_route_point_with_touchdown(
    base_points: List[tuple[float, float]],
    touchdown_point: tuple[float, float],
    *,
    include_turn_arcs: bool,
) -> List[tuple[float, float]]:
    updated_points = list(base_points)
    if not updated_points:
        return [touchdown_point]

    if include_turn_arcs:
        if len(updated_points) >= 2:
            return updated_points[:-2] + _build_quadratic_connector_points(
                updated_points[-2],
                updated_points[-1],
                touchdown_point,
            )
        updated_points[-1] = touchdown_point
        return updated_points

    updated_points[-1] = touchdown_point
    return updated_points


def _append_arrival_touchdown(
    *,
    route_planner: RoutePlanner,
    departure_name: str,
    arrival_name: str,
    waypoints_with_alt: List[Dict[str, Any]],
    route_points: List[tuple[float, float]],
    route_alt_m: float,
    base_distance_km: float,
    include_turn_arcs: bool,
) -> Dict[str, Any]:
    departure_ground_m = float(waypoints_with_alt[0].get("ground_m") or 0.0) if waypoints_with_alt else 0.0
    departure_takeoff = _resolve_departure_takeoff_waypoint(
        route_planner,
        departure_name,
        departure_ground_m,
    )
    base_waypoints = list(waypoints_with_alt)
    base_points = list(route_points)
    if departure_takeoff is not None and base_waypoints:
        base_waypoints[0] = departure_takeoff
    if departure_takeoff is not None and len(base_points) >= 2:
        if include_turn_arcs:
            base_points = _build_quadratic_connector_points(
                (float(departure_takeoff["lon"]), float(departure_takeoff["lat"])),
                base_points[0],
                base_points[1],
            ) + base_points[2:]
        else:
            base_points[0] = (float(departure_takeoff["lon"]), float(departure_takeoff["lat"]))
    elif departure_takeoff is not None and base_points:
        base_points[0] = (float(departure_takeoff["lon"]), float(departure_takeoff["lat"]))

    arrival_ground_m = float(waypoints_with_alt[-1].get("ground_m") or 0.0) if waypoints_with_alt else 0.0
    landing = _resolve_arrival_landing_waypoint(
        route_planner,
        arrival_name,
        arrival_ground_m,
    )
    if landing is None:
        return {
            "waypoints": base_waypoints,
            "mission_waypoints": _build_route_mission_waypoints(base_waypoints, route_alt_m),
            "points": _build_route_point_payload(base_points, route_alt_m),
            "distance_km": base_distance_km,
            "departure_takeoff": departure_takeoff,
            "arrival_touchdown": None,
        }

    updated_waypoints = list(base_waypoints)
    updated_waypoints.append(landing)

    touchdown_point = (float(landing["lon"]), float(landing["lat"]))
    updated_points = _replace_final_route_point_with_touchdown(
        base_points,
        touchdown_point,
        include_turn_arcs=include_turn_arcs,
    )

    arrival_touchdown = {
        "name": arrival_name,
        "spawn_point_id": str(landing.get("spawn_point_id") or "FATO 1"),
        "label": str(landing.get("name") or f"{arrival_name} FATO 1"),
        "lat": float(landing["lat"]),
        "lon": float(landing["lon"]),
        "ground_m": float(landing.get("ground_m") or 0.0),
        "alt_m": float(landing.get("alt_m") or landing.get("ground_m") or 0.0),
        "landing_calibration_applied": bool(landing.get("landing_calibration_applied", False)),
    }
    landing_yaw = _to_float(landing.get("yaw_deg"))
    if landing_yaw is not None:
        arrival_touchdown["yaw_deg"] = float(landing_yaw) % 360.0

    return {
        "waypoints": updated_waypoints,
        "mission_waypoints": _build_route_mission_waypoints(updated_waypoints, route_alt_m),
        "points": _build_route_point_payload(updated_points, route_alt_m),
        "distance_km": _polyline_distance_km(updated_points) or base_distance_km,
        "departure_takeoff": departure_takeoff,
        "arrival_touchdown": arrival_touchdown,
        "include_turn_arcs": include_turn_arcs,
    }


# _extract_records_from_export → MissionService.extract_records_from_export


# ── HTTP utilities (CoreServer DB 조회) ──────────────────────────────────
def _server_http_base() -> str:
    s = state.settings
    host = str(s.get("server_http_host") or s.get("dtam_target_ip") or "127.0.0.1")
    port = int(s.get("server_http_port") or 8095)
    return f"http://{host}:{port}"


def _server_get_json(path: str, query: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    url = f"{_server_http_base()}{path}"
    if query:
        url += "?" + urlencode({key: value for key, value in query.items() if value})
    request = UrlRequest(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=4.0) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DTAM server request failed: HTTP {exc.code} {body}") from exc
    except (OSError, URLError) as exc:
        raise RuntimeError(f"DTAM server unavailable at {url}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"DTAM server returned non-object JSON from {url}")
    return data


# Auto-3001 pipeline (_find_scenario_setup_payload,
# _build_auto_mission_payload_from_scenario, _scenario_vertiport_names,
# _auto_plan_count) 는 모두 MissionService 안으로 흡수됨. MissionService 가
# 생성자 deps (route_planner, settings, route_response_fn, server_http_get_fn)
# 를 통해 동일 helpers 를 자체 사용한다.


@asynccontextmanager
async def _lifespan(_: FastAPI):
    # ── startup ────────────────────────────────────────────────
    # 모든 런타임 상태는 ``state`` 컨테이너의 attribute 를 mutate — global 키워드 불필요.
    if MBTILES_PATH.exists():
        state.mbtiles = MBTiles(MBTILES_PATH)
        print(f"[DTAM MP] MBTiles loaded: {state.mbtiles.info.name} "
              f"(z{state.mbtiles.info.min_zoom}-{state.mbtiles.info.max_zoom})")
    else:
        print(f"[DTAM MP] Warning: MBTiles not found at {MBTILES_PATH}")

    vp_csv = DATA_DIR / "vertiport_default.csv"
    wp_csv = DATA_DIR / "waypoint_default.csv"
    if vp_csv.exists() and wp_csv.exists():
        try:
            state.route_planner = RoutePlanner.from_csv(vp_csv, wp_csv)
            print(f"[DTAM MP] RoutePlanner loaded: "
                  f"{len(state.route_planner.ports)} ports, "
                  f"{len(state.route_planner.waypoints)} waypoints")
        except Exception as exc:
            print(f"[DTAM MP] RoutePlanner error: {exc}")

    try:
        from .services.dem import load_dem_provider
        state.dem_provider = load_dem_provider(DEM_DIR, DEM_TILE_SIZE, DEM_MAX_ZOOM)
        if state.dem_provider.available:
            print("[DTAM MP] DEM provider loaded")
    except Exception as exc:
        print(f"[DTAM MP] DEM provider unavailable: {exc}")

    try:
        state.mission_service = MissionService(
            target_ip=str(state.settings["dtam_target_ip"]),
            ws_port=int(state.settings.get("dtam_ws_port", 8096)),
            route_planner=state.route_planner,
            settings=state.settings,
            resource_csv=MISSION_ICD_RESOURCE_CSV,
            route_response_fn=_route_payload_response,
            server_http_get_fn=_server_get_json,
        )
        desc = state.mission_service.describe()
        print(f"[DTAM MP] DTAM sender ready → {desc['server_url']}")
    except Exception as exc:
        print(f"[DTAM MP] DTAM sender unavailable: {exc}")

    try:
        yield
    finally:
        # ── shutdown ──────────────────────────────────────────
        if state.mbtiles:
            state.mbtiles.close()
        if state.mission_service is not None:
            state.mission_service.close()


def create_app() -> FastAPI:
    app = FastAPI(title="DTAM Mission Planner", lifespan=_lifespan)

    # ── 라우터 등록 (도메인별로 routes/*.py 에 분리) ─────────────
    from .routes import (
        index as index_routes,
        tiles as tiles_routes,
        info as info_routes,
        icd as icd_routes,
        route as route_routes,
        dtam as dtam_routes,
        settings_api as settings_routes,
        converter as converter_routes,
    )
    for r in (
        index_routes.router,
        tiles_routes.router,
        info_routes.router,
        icd_routes.router,
        route_routes.router,
        dtam_routes.router,
        settings_routes.router,
        converter_routes.router,
    ):
        app.include_router(r)

    # ── 정적 파일 마운트 ──────────────────────────────────────
    app.mount("/css", StaticFiles(directory=str(STATIC_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(STATIC_DIR / "js")), name="js")
    app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")
    app.mount("/resources", StaticFiles(directory=str(Path(MBTILES_PATH).parent)), name="resources")


    return app


def _route_payload_response(
    start: Any,
    end: Any,
    result: Any,
    *,
    include_turn_arcs: bool = False,
) -> Dict[str, Any]:
    rp = state.route_planner
    waypoints_with_alt: List[Dict[str, Any]] = []
    for name in result.path:
        if rp is None:
            break
        if name in rp.ports:
            p = rp.ports[name]
            waypoints_with_alt.append(_build_route_waypoint(
                name=name,
                lat=p.lat,
                lon=p.lon,
                ground_m=_sample_ground_m(p.lon, p.lat),
                alt_m=0.0,
                waypoint_type="vertiport",
            ))
        elif name in rp.waypoints:
            w = rp.waypoints[name]
            payload = _build_route_waypoint(
                name=name,
                lat=w.lat,
                lon=w.lon,
                ground_m=_sample_ground_m(w.lon, w.lat),
                alt_m=w.alt_ft * 0.3048 if w.alt_ft else 300,
                waypoint_type="waypoint",
            )
            payload["alt_ft"] = w.alt_ft
            waypoints_with_alt.append(payload)
    route_alt_m = _route_absolute_altitude_m(waypoints_with_alt)
    route_payload = _append_arrival_touchdown(
        route_planner=rp,  # type: ignore[arg-type]
        departure_name=str(start),
        arrival_name=str(end),
        waypoints_with_alt=waypoints_with_alt,
        route_points=result.points,
        route_alt_m=route_alt_m,
        base_distance_km=result.distance_km,
        include_turn_arcs=include_turn_arcs,
    )
    return {
        "path": result.path,
        "distance_km": route_payload["distance_km"],
        "points": route_payload["points"],
        "waypoints": route_payload["waypoints"],
        "missionWaypoints": route_payload["mission_waypoints"],
        "departureTakeoff": route_payload["departure_takeoff"],
        "arrivalTouchdown": route_payload["arrival_touchdown"],
        "includeTurnArcs": include_turn_arcs,
    }


# _dtam_status_payload → routes 가 직접 server.mission_service.describe() 사용
