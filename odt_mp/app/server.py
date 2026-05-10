from __future__ import annotations

import asyncio
import csv
import datetime
import json
import math
import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import (
    AIRSIM_HOST,
    AIRSIM_PORT,
    DATA_DIR,
    DEM_DIR,
    DEM_MAX_ZOOM,
    DEM_TILE_SIZE,
    DEFAULT_CENTER_LAT,
    DEFAULT_CENTER_LON,
    DEFAULT_START_ZOOM,
    MBTILES_PATH,
    WEB_DIR,
)
from app.converter_tool import (
    DEFAULT_CUSTOM_X_AXIS_HEADING_DEG,
    DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG,
    build_vertiport_spawn_layout,
    convert_target_to_unreal,
    get_vertiport_spawn_point,
    load_airsim_settings_summary,
)
from app.mission_icd_export import (
    build_mission_icd_export,
    validate_mission_icd_record,
)
from app.mbtiles import MBTiles
from app.route_planner import RoutePlanner
from app.simulator_service import SimpleDynamicsSimulatorService

mbtiles: Optional[MBTiles] = None
route_planner: Optional[RoutePlanner] = None
dem_provider: Any = None
mission_runner: Any = None
telemetry_handler: Any = None
simulator_service: Optional[SimpleDynamicsSimulatorService] = None
telemetry_loop: Optional[asyncio.AbstractEventLoop] = None
MISSION_ICD_RESOURCE_CSV = DATA_DIR / "resources_vp.csv"
MISSION_ICD_EXPORT_DIR = DATA_DIR / "mission_exports"

settings: Dict[str, Any] = {
    "airsim_host": AIRSIM_HOST,
    "airsim_port": AIRSIM_PORT,
    "default_speed_mps": 30.0,
    "default_altitude_m": 300.0,
}

telemetry_clients: List[WebSocket] = []


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
    if dem_provider is None or not getattr(dem_provider, "available", False):
        return None
    try:
        value = dem_provider.sample_elevation(lon, lat)
    except Exception:
        value = None
    return float(value) if value is not None else None


def _sample_ground_m(lon: float, lat: float) -> float:
    value = _sample_ground_optional_m(lon, lat)
    return value if value is not None else 0.0


def _looks_like_icd_record(payload: Dict[str, Any]) -> bool:
    required = {"flightPlanNumber", "aircraftId", "departure", "enRoute", "arrival"}
    return required.issubset(payload.keys())


def _looks_like_icd_record_list(payload: Any) -> bool:
    return isinstance(payload, list) and bool(payload) and all(
        isinstance(item, dict) and _looks_like_icd_record(item) for item in payload
    )


def _coerce_int(value: Any) -> Optional[int]:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_simulation_fleet(
    mission_payload: Dict[str, Any],
    default_vehicle_name: str = "Drone1",
) -> List[Dict[str, Any]]:
    options = mission_payload.get("options") or {}
    base_aircraft_id = str(options.get("aircraftId") or "UAM0001").strip() or "UAM0001"
    base_flight_plan = _coerce_int(options.get("flightPlanNumber"))
    if base_flight_plan is None:
        base_flight_plan = int(datetime.datetime.now().strftime("%m%d%H%M"))

    raw_fleet = mission_payload.get("fleet") or []
    normalized: List[Dict[str, Any]] = []
    if isinstance(raw_fleet, list):
        for index, item in enumerate(raw_fleet):
            if not isinstance(item, dict):
                continue
            aircraft_id = (
                str(item.get("aircraftId") or base_aircraft_id or f"UAM{index + 1:04d}").strip()
                or f"UAM{index + 1:04d}"
            )
            vehicle_name = (
                str(item.get("vehicleName") or item.get("vehicle_name") or "").strip()
                or (default_vehicle_name if index == 0 else f"Drone{index + 1}")
            )
            flight_plan_number = _coerce_int(item.get("flightPlanNumber"))
            if flight_plan_number is None:
                flight_plan_number = base_flight_plan + index
            normalized.append({
                "aircraftId": aircraft_id,
                "vehicleName": vehicle_name,
                "flightPlanNumber": flight_plan_number,
            })

    if normalized:
        return normalized

    return [{
        "aircraftId": base_aircraft_id,
        "vehicleName": str(default_vehicle_name or "Drone1").strip() or "Drone1",
        "flightPlanNumber": base_flight_plan,
    }]


def _build_existing_icd_export_bundle(
    mission_payload: Dict[str, Any] | List[Dict[str, Any]],
    fleet: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    records = mission_payload if isinstance(mission_payload, list) else [mission_payload]
    normalized_records = [item for item in records if isinstance(item, dict)]
    if not normalized_records:
        raise ValueError("No ICD records were provided.")

    normalized_fleet = list(fleet or [])
    if not normalized_fleet:
        normalized_fleet = []
        base_number = int(datetime.datetime.now().strftime("%m%d%H%M"))
        for index, record in enumerate(normalized_records):
            normalized_fleet.append({
                "aircraftId": str(record.get("aircraftId") or f"UAM{index + 1:04d}"),
                "vehicleName": f"Drone{index + 1}",
                "flightPlanNumber": _coerce_int(record.get("flightPlanNumber")) or (base_number + index),
            })

    errors: List[str] = []
    for fleet_entry, record in zip(normalized_fleet, normalized_records):
        prefix = f"{fleet_entry['aircraftId']} ({fleet_entry['vehicleName']})"
        for message in validate_mission_icd_record(record):
            errors.append(f"{prefix}: {message}")

    first_record = normalized_records[0]
    filename = (
        f"mission_icd_v1_{first_record.get('flightPlanNumber', 'fleet')}_{first_record.get('aircraftId', 'UAM0001')}.json"
        if len(normalized_records) == 1
        else f"mission_icd_v1_fleet_{normalized_fleet[0]['flightPlanNumber']}_{len(normalized_records)}ac.json"
    )
    return {
        "mode": "icd",
        "filename": filename,
        "record": normalized_records[0] if len(normalized_records) == 1 else normalized_records,
        "records": normalized_records,
        "fleet": normalized_fleet,
        "validation": {
            "valid": not errors,
            "errors": errors,
        },
        "warnings": [],
    }


def _build_mission_icd_bundle(
    payload: Dict[str, Any],
    fleet: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    normalized_fleet = list(fleet or _normalize_simulation_fleet(payload))
    raw_missions = payload.get("missions")
    missions = (
        [item for item in raw_missions if isinstance(item, dict)]
        if isinstance(raw_missions, list)
        else [payload]
    )
    if not missions:
        raise ValueError("No mission payloads were provided.")
    if len(missions) != len(normalized_fleet):
        raise ValueError(
            f"Mission count ({len(missions)}) does not match fleet count ({len(normalized_fleet)})."
        )

    base_options = dict(payload.get("options") or {})
    exports: List[Dict[str, Any]] = []

    for mission_payload, fleet_entry in zip(missions, normalized_fleet):
        item_payload = dict(mission_payload)
        item_payload.pop("fleet", None)
        item_payload.pop("missions", None)
        item_payload["options"] = {
            **base_options,
            **dict(item_payload.get("options") or {}),
            "aircraftId": fleet_entry["aircraftId"],
            "flightPlanNumber": fleet_entry["flightPlanNumber"],
        }
        exports.append(
            build_mission_icd_export(
                item_payload,
                route_planner,
                MISSION_ICD_RESOURCE_CSV,
                float(settings["default_altitude_m"]),
            )
        )

    if len(exports) == 1:
        result = dict(exports[0])
        result["records"] = [exports[0]["record"]]
        result["fleet"] = normalized_fleet
        return result

    warnings: List[str] = []
    errors: List[str] = []
    records: List[Dict[str, Any]] = []
    for fleet_entry, export in zip(normalized_fleet, exports):
        prefix = f"{fleet_entry['aircraftId']} ({fleet_entry['vehicleName']})"
        records.append(export["record"])
        for warning in export.get("warnings", []):
            warnings.append(f"{prefix}: {warning}")
        for message in export.get("validation", {}).get("errors", []):
            errors.append(f"{prefix}: {message}")

    return {
        "mode": str(payload.get("mode") or "route"),
        "filename": f"mission_icd_v1_fleet_{normalized_fleet[0]['flightPlanNumber']}_{len(records)}ac.json",
        "record": records,
        "records": records,
        "fleet": normalized_fleet,
        "validation": {
            "valid": not errors,
            "errors": errors,
        },
        "warnings": warnings,
    }


def _save_mission_icd_bundle(export_result: Dict[str, Any], export_dir: Path) -> Path:
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / str(export_result.get("filename") or "mission_icd_v1.json")
    path.write_text(
        json.dumps(export_result.get("record"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _route_absolute_altitude_m(waypoints_with_alt: List[Dict[str, Any]]) -> float:
    waypoint_alts = [
        float(item.get("alt_m", 0) or 0)
        for item in waypoints_with_alt
        if float(item.get("alt_m", 0) or 0) > 0
    ]
    return max(settings["default_altitude_m"], max(waypoint_alts, default=0.0))


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


def _build_route_waypoint(
    *,
    name: str,
    lat: float,
    lon: float,
    ground_m: float,
    alt_m: float,
    waypoint_type: str,
    spawn_point_id: Optional[str] = None,
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
        if not vertiport or not category or lat is None or lon is None:
            continue
        catalog.setdefault(vertiport, {}).setdefault(category, []).append({
            "label": label,
            "lat": float(lat),
            "lon": float(lon),
            "alt_m": float(alt_m if alt_m is not None else ground_m or 0.0),
            "ground_m": float(ground_m if ground_m is not None else alt_m or 0.0),
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
    points = catalog.get(vertiport_name, {}).get(str(category or "").strip().upper(), [])
    if preferred_label:
        target = str(preferred_label).strip().upper()
        for point in points:
            if str(point.get("label") or "").strip().upper() == target:
                return point
    return points[0] if points else None


def _resolve_departure_takeoff_waypoint(
    route_planner: RoutePlanner,
    departure_name: str,
    fallback_ground_m: float,
) -> Optional[Dict[str, Any]]:
    port = route_planner.ports.get(departure_name)
    if port is None:
        return None

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
            alt_m=float(resource.get("ground_m") or fallback_ground_m),
            waypoint_type="departure_takeoff",
        )

    return _build_route_waypoint(
        name=departure_name,
        lat=float(port.lat),
        lon=float(port.lon),
        ground_m=fallback_ground_m,
        alt_m=fallback_ground_m,
        waypoint_type="departure_takeoff",
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


def _append_arrival_touchdown(
    *,
    route_planner: RoutePlanner,
    departure_name: str,
    arrival_name: str,
    waypoints_with_alt: List[Dict[str, Any]],
    route_points: List[tuple[float, float]],
    route_alt_m: float,
    base_distance_km: float,
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
        base_points = _build_quadratic_connector_points(
            (float(departure_takeoff["lon"]), float(departure_takeoff["lat"])),
            base_points[0],
            base_points[1],
        ) + base_points[2:]
    elif departure_takeoff is not None and base_points:
        base_points[0] = (float(departure_takeoff["lon"]), float(departure_takeoff["lat"]))

    port = route_planner.ports.get(arrival_name)
    if port is None:
        return {
            "waypoints": base_waypoints,
            "mission_waypoints": _build_route_mission_waypoints(base_waypoints, route_alt_m),
            "points": _build_route_point_payload(base_points, route_alt_m),
            "distance_km": base_distance_km,
            "departure_takeoff": departure_takeoff,
            "arrival_touchdown": None,
        }

    touchdown = get_vertiport_spawn_point(
        vertiport_name=port.name,
        vertiport_lat=port.lat,
        vertiport_lon=port.lon,
        vertiport_ground_m=_sample_ground_optional_m(port.lon, port.lat),
        spawn_point_id="S26",
    )
    if touchdown is None:
        return {
            "waypoints": base_waypoints,
            "mission_waypoints": _build_route_mission_waypoints(base_waypoints, route_alt_m),
            "points": _build_route_point_payload(base_points, route_alt_m),
            "distance_km": base_distance_km,
            "departure_takeoff": departure_takeoff,
            "arrival_touchdown": None,
        }

    touchdown_ground_m = float(touchdown.get("ground_m") or 0.0)
    touchdown_alt_m = float(touchdown.get("alt_m") or touchdown_ground_m)
    waypoint = _build_route_waypoint(
        name=f"{arrival_name} S26",
        lat=float(touchdown["lat"]),
        lon=float(touchdown["lon"]),
        ground_m=touchdown_ground_m,
        alt_m=touchdown_alt_m,
        waypoint_type="arrival_touchdown",
        spawn_point_id="S26",
    )

    updated_waypoints = list(base_waypoints)
    updated_waypoints.append(waypoint)

    updated_points = list(base_points)
    touchdown_point = (float(touchdown["lon"]), float(touchdown["lat"]))
    if len(updated_points) >= 2:
        updated_points = updated_points[:-2] + _build_quadratic_connector_points(
            updated_points[-2],
            updated_points[-1],
            touchdown_point,
        )
    elif not updated_points or (
        _haversine_m(
            updated_points[-1][0],
            updated_points[-1][1],
            touchdown_point[0],
            touchdown_point[1],
        ) > 0.5
    ):
        updated_points.append(touchdown_point)

    extra_distance_km = 0.0
    if route_points:
        extra_distance_km = _haversine_m(
            route_points[-1][0],
            route_points[-1][1],
            float(touchdown["lon"]),
            float(touchdown["lat"]),
        ) / 1000.0

    return {
        "waypoints": updated_waypoints,
        "mission_waypoints": _build_route_mission_waypoints(updated_waypoints, route_alt_m),
        "points": _build_route_point_payload(updated_points, route_alt_m),
        "distance_km": base_distance_km + extra_distance_km,
        "departure_takeoff": departure_takeoff,
        "arrival_touchdown": {
            "name": arrival_name,
            "spawn_point_id": "S26",
            "label": waypoint["name"],
            "lat": float(touchdown["lat"]),
            "lon": float(touchdown["lon"]),
            "ground_m": touchdown_ground_m,
            "alt_m": touchdown_alt_m,
            "yaw_deg": float(touchdown.get("yaw_deg") or 0.0),
        },
    }


def create_app() -> FastAPI:
    app = FastAPI(title="ODT Mission Planner")

    @app.on_event("startup")
    async def startup() -> None:
        global mbtiles, route_planner, dem_provider, mission_runner, telemetry_handler
        global simulator_service, telemetry_loop
        telemetry_loop = asyncio.get_running_loop()
        if MBTILES_PATH.exists():
            mbtiles = MBTiles(MBTILES_PATH)
            print(f"[Server] MBTiles loaded: {mbtiles.info.name} "
                  f"(z{mbtiles.info.min_zoom}-{mbtiles.info.max_zoom})")
        else:
            print(f"[Server] Warning: MBTiles not found at {MBTILES_PATH}")

        vp_csv = DATA_DIR / "vertiport_default.csv"
        wp_csv = DATA_DIR / "waypoint_default.csv"
        if vp_csv.exists() and wp_csv.exists():
            try:
                route_planner = RoutePlanner.from_csv(vp_csv, wp_csv)
                print(f"[Server] RoutePlanner loaded: "
                      f"{len(route_planner.ports)} ports, "
                      f"{len(route_planner.waypoints)} waypoints")
            except Exception as exc:
                print(f"[Server] RoutePlanner error: {exc}")

        try:
            from app.dem import load_dem_provider
            dem_provider = load_dem_provider(DEM_DIR, DEM_TILE_SIZE, DEM_MAX_ZOOM)
            if dem_provider.available:
                print(f"[Server] DEM provider loaded")
        except Exception as exc:
            print(f"[Server] DEM provider unavailable: {exc}")

        try:
            from app.airsim.mission_runner import AirsimMissionRunner
            mission_runner = AirsimMissionRunner(speed_mps=settings["default_speed_mps"])
            print("[Server] AirSim mission runner ready")
        except Exception as exc:
            print(f"[Server] AirSim mission runner unavailable: {exc}")

        try:
            from app.airsim.telemetry import AirsimTelemetry
            telemetry_handler = AirsimTelemetry(emit_fn=_broadcast_telemetry)
            print("[Server] AirSim telemetry handler ready")
        except Exception as exc:
            print(f"[Server] AirSim telemetry handler unavailable: {exc}")

        try:
            simulator_service = SimpleDynamicsSimulatorService(emit_fn=_broadcast_telemetry)
            print("[Server] simpleDynamics simulator ready")
        except Exception as exc:
            print(f"[Server] simpleDynamics simulator unavailable: {exc}")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        global telemetry_loop
        if mbtiles:
            mbtiles.close()
        if telemetry_handler:
            telemetry_handler.stop()
        if simulator_service:
            simulator_service.disconnect()
        telemetry_loop = None

    # --- Static files ---
    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        index_path = WEB_DIR / "index.html"
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

    app.mount("/css", StaticFiles(directory=str(WEB_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(WEB_DIR / "js")), name="js")
    app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")
    app.mount("/resources", StaticFiles(directory=str(Path(MBTILES_PATH).parent)), name="resources")

    # --- Tile endpoints ---
    @app.get("/tiles/{z}/{x}/{y}.pbf")
    async def get_tile(z: int, x: int, y: int) -> Response:
        if mbtiles is None:
            return Response(status_code=404)
        data = mbtiles.get_tile(z, x, y)
        if data is None:
            return Response(status_code=204)
        headers = {"Content-Type": "application/vnd.mapbox-vector-tile",
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=86400"}
        if len(data) >= 2 and data[0] == 0x1f and data[1] == 0x8b:
            headers["Content-Encoding"] = "gzip"
        return Response(content=data, headers=headers)

    @app.get("/dem/{z}/{x}/{y}.png")
    async def get_dem_tile(z: int, x: int, y: int) -> Response:
        if dem_provider is None or not dem_provider.available:
            return Response(status_code=404)
        data = dem_provider.get_tile(z, x, y)
        if data is None:
            return Response(status_code=204)
        return Response(content=data,
                        media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})

    # --- API endpoints ---
    @app.get("/api/config")
    async def get_config() -> JSONResponse:
        info = mbtiles.info if mbtiles else None
        bounds = list(info.bounds) if info and info.bounds else None
        return JSONResponse({
            "center": [DEFAULT_CENTER_LON, DEFAULT_CENTER_LAT],
            "zoom": DEFAULT_START_ZOOM,
            "minZoom": info.min_zoom if info else 0,
            "maxZoom": info.max_zoom if info else 14,
            "bounds": bounds,
            "tileUrl": "/tiles/{z}/{x}/{y}.pbf",
            "demUrl": "/dem/{z}/{x}/{y}.png",
            "dem": {
                "enabled": bool(dem_provider and dem_provider.available),
                "tileUrl": "/dem/{z}/{x}/{y}.png",
                "tileSize": DEM_TILE_SIZE,
                "maxZoom": DEM_MAX_ZOOM,
                "encoding": "terrarium",
                "exaggeration": 1.15,
                "pitchThreshold": 18,
                "terrainZoomThreshold": 9,
                "hillshadeMinZoom": 8,
                "buildingPitchThreshold": 28,
                "buildingZoomThreshold": 13.5,
            },
            "airsim": {
                "host": settings["airsim_host"],
                "port": settings["airsim_port"],
            },
        })

    @app.get("/api/vertiports")
    async def get_vertiports() -> JSONResponse:
        if route_planner is None:
            return JSONResponse([])
        result = []
        for port in route_planner.ports.values():
            result.append({
                "name": port.name,
                "lat": port.lat,
                "lon": port.lon,
                "ground_m": _sample_ground_m(port.lon, port.lat),
                "inr_km": port.inr_km,
                "otr_km": port.otr_km,
                "inr_deg": port.inr_deg,
                "otr_deg": port.otr_deg,
                "turn_dir": port.turn_dir,
                "links": list(port.links),
            })
        return JSONResponse(result)

    @app.get("/api/waypoints")
    async def get_waypoints() -> JSONResponse:
        if route_planner is None:
            return JSONResponse([])
        result = []
        for wp in route_planner.waypoints.values():
            result.append({
                "name": wp.name,
                "lat": wp.lat,
                "lon": wp.lon,
                "ground_m": _sample_ground_m(wp.lon, wp.lat),
                "alt_ft": wp.alt_ft,
                "alt_m": wp.alt_ft * 0.3048 if wp.alt_ft else None,
                "links": list(wp.links),
            })
        return JSONResponse(result)

    @app.get("/api/elevation")
    async def get_elevation(lon: float, lat: float) -> JSONResponse:
        available = bool(dem_provider and getattr(dem_provider, "available", False))
        ground_m = _sample_ground_optional_m(lon, lat) if available else None
        return JSONResponse({
            "lon": lon,
            "lat": lat,
            "ground_m": ground_m,
            "available": available,
        })

    @app.post("/api/mission/icd/export")
    async def export_mission_icd(request: Request) -> JSONResponse:
        body = await request.json()
        try:
            if _looks_like_icd_record(body) or _looks_like_icd_record_list(body):
                result = _build_existing_icd_export_bundle(body)
            else:
                result = _build_mission_icd_bundle(body)
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/mission/icd/save")
    async def save_mission_icd(request: Request) -> JSONResponse:
        body = await request.json()
        try:
            if _looks_like_icd_record(body) or _looks_like_icd_record_list(body):
                result = _build_existing_icd_export_bundle(body)
            else:
                result = _build_mission_icd_bundle(body)
            if not result.get("validation", {}).get("valid", False):
                return JSONResponse(result, status_code=400)
            path = _save_mission_icd_bundle(result, MISSION_ICD_EXPORT_DIR)
            result["saved_path"] = str(path)
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/mission/icd/open-folder")
    async def open_mission_icd_folder() -> JSONResponse:
        try:
            folder = MISSION_ICD_EXPORT_DIR.resolve()
            folder.mkdir(parents=True, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(folder)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(folder)])
            return JSONResponse({
                "ok": True,
                "folder_path": str(folder),
            })
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/route")
    async def compute_route(request: Request) -> JSONResponse:
        body = await request.json()
        if route_planner is None:
            return JSONResponse({"error": "Route planner not loaded"}, status_code=500)
        start = body.get("start")
        end = body.get("end")
        include_arcs = body.get("include_arcs", True)
        if not start or not end:
            return JSONResponse({"error": "start and end required"}, status_code=400)
        try:
            result = route_planner.find_route(start, end, include_turn_arcs=include_arcs)
            waypoints_with_alt = []
            for name in result.path:
                if name in route_planner.ports:
                    p = route_planner.ports[name]
                    waypoints_with_alt.append(_build_route_waypoint(
                        name=name,
                        lat=p.lat,
                        lon=p.lon,
                        ground_m=_sample_ground_m(p.lon, p.lat),
                        alt_m=0.0,
                        waypoint_type="vertiport",
                    ))
                elif name in route_planner.waypoints:
                    w = route_planner.waypoints[name]
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
                route_planner=route_planner,
                departure_name=str(start),
                arrival_name=str(end),
                waypoints_with_alt=waypoints_with_alt,
                route_points=result.points,
                route_alt_m=route_alt_m,
                base_distance_km=result.distance_km,
            )
            return JSONResponse({
                "path": result.path,
                "distance_km": route_payload["distance_km"],
                "points": route_payload["points"],
                "waypoints": route_payload["waypoints"],
                "missionWaypoints": route_payload["mission_waypoints"],
                "departureTakeoff": route_payload["departure_takeoff"],
                "arrivalTouchdown": route_payload["arrival_touchdown"],
            })
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/route/via")
    async def compute_route_via(request: Request) -> JSONResponse:
        body = await request.json()
        if route_planner is None:
            return JSONResponse({"error": "Route planner not loaded"}, status_code=500)
        start = body.get("start")
        end = body.get("end")
        via = body.get("via", [])
        include_arcs = body.get("include_arcs", True)
        if not start or not end:
            return JSONResponse({"error": "start and end required"}, status_code=400)
        try:
            result = route_planner.find_route_via(
                start, end, via, include_turn_arcs=include_arcs
            )
            waypoints_with_alt = []
            for name in result.path:
                if name in route_planner.ports:
                    p = route_planner.ports[name]
                    waypoints_with_alt.append(_build_route_waypoint(
                        name=name,
                        lat=p.lat,
                        lon=p.lon,
                        ground_m=_sample_ground_m(p.lon, p.lat),
                        alt_m=0.0,
                        waypoint_type="vertiport",
                    ))
                elif name in route_planner.waypoints:
                    w = route_planner.waypoints[name]
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
                route_planner=route_planner,
                departure_name=str(start),
                arrival_name=str(end),
                waypoints_with_alt=waypoints_with_alt,
                route_points=result.points,
                route_alt_m=route_alt_m,
                base_distance_km=result.distance_km,
            )
            return JSONResponse({
                "path": result.path,
                "distance_km": route_payload["distance_km"],
                "points": route_payload["points"],
                "waypoints": route_payload["waypoints"],
                "missionWaypoints": route_payload["mission_waypoints"],
                "departureTakeoff": route_payload["departure_takeoff"],
                "arrivalTouchdown": route_payload["arrival_touchdown"],
            })
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/mission/start")
    async def start_mission(request: Request) -> JSONResponse:
        body = await request.json()
        if mission_runner is None:
            return JSONResponse({"error": "Mission runner not available"}, status_code=500)
        payload = {
            "host": settings["airsim_host"],
            "port": settings["airsim_port"],
            "vehicle_name": body.get("vehicle_name", ""),
            "snap_to_first_waypoint": body.get("snap_to_first_waypoint", False),
            "snap_to_last_waypoint": body.get("snap_to_last_waypoint", False),
            "route": body.get("route", []),
            "relative_to_start": body.get("relative_to_start", True),
            "body_relative": body.get("body_relative", False),
            "yaw_follow": body.get("yaw_follow", True),
        }
        mission_runner.start_mission(payload)
        return JSONResponse({"status": "started"})

    @app.post("/api/mission/stop")
    async def stop_mission() -> JSONResponse:
        if mission_runner is None:
            return JSONResponse({"error": "Mission runner not available"}, status_code=500)
        mission_runner.stop_mission()
        return JSONResponse({"status": "stopped"})

    @app.post("/api/telemetry/start")
    async def start_telemetry(request: Request) -> JSONResponse:
        body = await request.json()
        if telemetry_handler is None:
            return JSONResponse({"error": "Telemetry not available"}, status_code=500)
        host = body.get("host", settings["airsim_host"])
        port = body.get("port", settings["airsim_port"])
        vehicle = body.get("vehicle_name", "")
        telemetry_handler.start(host, port, vehicle)
        return JSONResponse({"status": "started"})

    @app.post("/api/telemetry/stop")
    async def stop_telemetry() -> JSONResponse:
        if telemetry_handler is None:
            return JSONResponse({"error": "Telemetry not available"}, status_code=500)
        telemetry_handler.stop()
        return JSONResponse({"status": "stopped"})

    @app.get("/api/simulator/status")
    async def get_simulator_status() -> JSONResponse:
        if simulator_service is None:
            return JSONResponse({"error": "Simulator not available"}, status_code=500)
        return JSONResponse(simulator_service.get_status())

    @app.post("/api/simulator/connect")
    async def connect_simulator(request: Request) -> JSONResponse:
        if simulator_service is None:
            return JSONResponse({"error": "Simulator not available"}, status_code=500)
        body = await request.json()
        host = str(body.get("host") or settings["airsim_host"])
        port = int(body.get("port") or settings["airsim_port"])
        vehicle_names = body.get("vehicle_names")
        if not vehicle_names:
            vehicle_names = [str(body.get("vehicle_name") or "Drone1")]
        try:
            status = await asyncio.to_thread(
                simulator_service.connect,
                host,
                port,
                vehicle_names,
            )
            return JSONResponse(status)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/simulator/disconnect")
    async def disconnect_simulator() -> JSONResponse:
        if simulator_service is None:
            return JSONResponse({"error": "Simulator not available"}, status_code=500)
        status = await asyncio.to_thread(simulator_service.disconnect)
        return JSONResponse(status)

    @app.post("/api/simulator/start")
    async def start_simulator(request: Request) -> JSONResponse:
        if simulator_service is None:
            return JSONResponse({"error": "Simulator not available"}, status_code=500)
        body = await request.json()
        mission_payload = body.get("mission") or {}
        sync_to_airsim = bool(body.get("sync_to_airsim", False))
        replay_step_s = float(body.get("replay_step_s") or 0.1)
        playback_speed_x = float(body.get("playback_speed_x") or 1.0)
        host = str(body.get("host") or settings["airsim_host"])
        port = int(body.get("port") or settings["airsim_port"])
        fleet: List[Dict[str, Any]] = []

        try:
            if _looks_like_icd_record(mission_payload) or _looks_like_icd_record_list(mission_payload):
                mission_export = _build_existing_icd_export_bundle(mission_payload, fleet or None)
            else:
                fleet = _normalize_simulation_fleet(
                    mission_payload if isinstance(mission_payload, dict) else {},
                    str(body.get("vehicle_name") or "Drone1"),
                )
                mission_export = _build_mission_icd_bundle(mission_payload, fleet)
            fleet = list(mission_export.get("fleet") or fleet)
            vehicle_names = [item["vehicleName"] for item in fleet]
            if not mission_export.get("validation", {}).get("valid", False):
                return JSONResponse(mission_export, status_code=400)

            if sync_to_airsim:
                await asyncio.to_thread(
                    simulator_service.connect,
                    host,
                    port,
                    vehicle_names,
                )

            status = await asyncio.to_thread(
                simulator_service.start,
                mission_export["records"],
                replay_step_s,
                playback_speed_x,
                sync_to_airsim,
                vehicle_names,
            )
            return JSONResponse({
                "status": "started",
                "sync_to_airsim": sync_to_airsim,
                "mission_export": mission_export,
                "simulator": status,
            })
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/simulator/stop")
    async def stop_simulator() -> JSONResponse:
        if simulator_service is None:
            return JSONResponse({"error": "Simulator not available"}, status_code=500)
        status = await asyncio.to_thread(simulator_service.stop)
        return JSONResponse(status)

    @app.post("/api/simulator/speed")
    async def update_simulator_speed(request: Request) -> JSONResponse:
        if simulator_service is None:
            return JSONResponse({"error": "Simulator not available"}, status_code=500)
        body = await request.json()
        playback_speed_x = float(body.get("playback_speed_x") or 1.0)
        status = await asyncio.to_thread(simulator_service.set_playback_speed, playback_speed_x)
        return JSONResponse(status)

    @app.get("/api/settings")
    async def get_settings() -> JSONResponse:
        return JSONResponse(settings)

    @app.put("/api/settings")
    async def update_settings(request: Request) -> JSONResponse:
        body = await request.json()
        for key in ("airsim_host", "airsim_port", "default_speed_mps", "default_altitude_m"):
            if key in body:
                settings[key] = body[key]
        return JSONResponse(settings)

    @app.get("/api/converter/settings")
    async def get_converter_settings() -> JSONResponse:
        try:
            return JSONResponse(load_airsim_settings_summary(None))
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/api/converter/convert")
    async def convert_coordinates(request: Request) -> JSONResponse:
        body = await request.json()
        try:
            target_lat = float(body.get("target_lat"))
            target_lon = float(body.get("target_lon"))
            player_start_lat = float(body.get("player_start_lat"))
            player_start_lon = float(body.get("player_start_lon"))
            player_start_alt_m = float(body.get("player_start_alt_m") or 0.0)
            x_axis_heading_deg = float(body.get("x_axis_heading_deg") or DEFAULT_CUSTOM_X_AXIS_HEADING_DEG)
            y_axis_heading_deg = float(body.get("y_axis_heading_deg") or DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG)
        except (TypeError, ValueError):
            return JSONResponse({"error": "Invalid converter input."}, status_code=400)

        target_ground_m = _sample_ground_optional_m(target_lon, target_lat)
        player_start_ground_m = _sample_ground_optional_m(player_start_lon, player_start_lat)

        raw_target_alt = body.get("target_alt_m")
        if raw_target_alt in (None, ""):
            target_alt_m = target_ground_m if target_ground_m is not None else 0.0
        else:
            try:
                target_alt_m = float(raw_target_alt)
            except (TypeError, ValueError):
                return JSONResponse({"error": "Invalid target altitude."}, status_code=400)

        result = convert_target_to_unreal(
            player_start_lat=player_start_lat,
            player_start_lon=player_start_lon,
            player_start_alt_m=player_start_alt_m,
            target_lat=target_lat,
            target_lon=target_lon,
            target_alt_m=target_alt_m,
            x_axis_heading_deg=x_axis_heading_deg,
            y_axis_heading_deg=y_axis_heading_deg,
        )
        return JSONResponse({
            "player_start": {
                "lat": player_start_lat,
                "lon": player_start_lon,
                "alt_m": player_start_alt_m,
                "ground_m": player_start_ground_m,
            },
            "target": {
                "lat": target_lat,
                "lon": target_lon,
                "ground_m": target_ground_m,
                "alt_m": target_alt_m,
            },
            **result,
        })

    @app.get("/api/converter/vertiport-spawns")
    async def get_converter_vertiport_spawns(name: str) -> JSONResponse:
        if route_planner is None:
            return JSONResponse({"error": "Route planner not loaded."}, status_code=500)
        port = route_planner.ports.get(name)
        if port is None:
            return JSONResponse({"error": f"Unknown vertiport: {name}"}, status_code=404)
        try:
            return JSONResponse(
                build_vertiport_spawn_layout(
                    vertiport_name=port.name,
                    vertiport_lat=port.lat,
                    vertiport_lon=port.lon,
                    vertiport_ground_m=_sample_ground_optional_m(port.lon, port.lat),
                )
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.get("/api/buildings")
    async def get_buildings() -> JSONResponse:
        return JSONResponse({
            "type": "FeatureCollection",
            "features": [],
            "_note": "Building extraction from OSM PBF is a placeholder for future implementation"
        })

    # --- WebSocket ---
    @app.websocket("/ws/telemetry")
    async def ws_telemetry(websocket: WebSocket) -> None:
        await websocket.accept()
        telemetry_clients.append(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in telemetry_clients:
                telemetry_clients.remove(websocket)

    return app


def _broadcast_telemetry(payload: dict) -> None:
    if telemetry_loop is None:
        return
    for ws in list(telemetry_clients):
        try:
            asyncio.run_coroutine_threadsafe(
                ws.send_json({"type": "telemetry", **payload}),
                telemetry_loop,
            )
        except Exception:
            if ws in telemetry_clients:
                telemetry_clients.remove(ws)
