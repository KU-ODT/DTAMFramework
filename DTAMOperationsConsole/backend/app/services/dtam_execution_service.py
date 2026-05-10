"""DTAM execution preparation owned by the Operations Console."""

from __future__ import annotations

import copy
import json
import math
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import HTTPException

from backend.app.services.module_process_service import (
    cleanup_stale_visualization_processes,
    ensure_module_backend,
    stop_module,
)


FRAMEWORK_ROOT = Path(__file__).resolve().parents[4]
UNREAL_SETTINGS_PATH = (
    FRAMEWORK_ROOT
    / "DTAMVisualization"
    / "Unreal"
    / "Environments"
    / "DTAMVisualization"
    / "settings.json"
)
DOCUMENTS_AIRSIM_SETTINGS_PATH = Path.home() / "Documents" / "AirSim" / "settings.json"
VM_CONFIG_PATH = FRAMEWORK_ROOT / "DTAMVisualization" / "vm_config.json"
UNREAL_PROJECT_PATH = (
    FRAMEWORK_ROOT
    / "DTAMVisualization"
    / "Unreal"
    / "Environments"
    / "DTAMVisualization"
    / "DTAMVisualization.uproject"
)
UNREAL_MISSION_GUIDE_PATH = UNREAL_PROJECT_PATH.parent / "Data" / "mission_guides.json"
AIRSIM_RPC_HOST = "127.0.0.1"
AIRSIM_RPC_PORT = 41451
MISSION_INCOMPLETE_MESSAGE = "임무계획을 완료해 주세요"
VALID_CONTROLLERS = {"Joystick", "Keyboard", "Autopilot"}
CONTROL_MODE_BY_CONTROLLER = {
    "Autopilot": "mission",
    "Keyboard": "keyboard",
    "Joystick": "joystick",
}

if str(FRAMEWORK_ROOT) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT))

from DTAM_MissionPlanner.app.config import DATA_DIR as MP_DATA_DIR  # noqa: E402
from DTAM_MissionPlanner.app.domain.converter_tool import get_vertiport_spawn_point  # noqa: E402
from DTAM_MissionPlanner.app.domain.coord_transform import wgs84_to_airsim_ned  # noqa: E402
from DTAM_MissionPlanner.app.services.route_planner import RoutePlanner  # noqa: E402
from DTAMAirMobility.app.domain.transform.odt_pose_frame import (  # noqa: E402
    DEFAULT_CUSTOM_X_AXIS_HEADING_DEG,
    DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG,
    convert_target_to_unreal,
)


_ROUTE_PLANNER_CACHE: RoutePlanner | None = None


def prepare_dtam_execution(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the console mission and prepare external DTAM modules."""
    mode_payload = _mode_payload_from_request(request_payload)
    missions, controller = _validate_mode_payload(mode_payload)

    # If the VM module/editor already has AirSim alive, reuse that runtime.
    # Closing it here made Operation Console launches tear down Unreal sessions
    # that were started from the Visualization module.
    existing_airsim_runtime = _is_rpc_port_open(AIRSIM_RPC_HOST, AIRSIM_RPC_PORT)
    if not existing_airsim_runtime:
        try:
            stop_module("visualization")
        except Exception:
            pass
        cleanup_stale_visualization_processes()

    settings_result = _write_unreal_vehicle_settings(missions)
    mission_guide_path = _write_unreal_mission_guides(missions, settings_result["vehicles"])
    server_url = ensure_module_backend("server", timeout_s=25.0)
    mission_url = ensure_module_backend("mission", timeout_s=30.0)
    airmobility_url = ensure_module_backend("airmobility", timeout_s=30.0)
    visualization_url = ensure_module_backend("visualization", timeout_s=45.0)

    vehicle_map = settings_result["vehicle_map"]
    _request_json(
        f"{visualization_url}/api/airsim/vehicle-map",
        method="PATCH",
        body=vehicle_map,
        timeout_s=4.0,
    )
    editor_processes = _find_dtam_unreal_editor_processes()
    if editor_processes:
        try:
            airsim_status = _wait_for_airsim_connection(visualization_url, timeout_s=8.0)
            unreal_status = {
                "running": True,
                "external_editor": True,
                "editor_processes": editor_processes,
                "message": "Connected to the existing Unreal Editor AirSim runtime.",
            }
        except HTTPException as exc:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Unreal Editor가 DTAMVisualization 프로젝트로 열려 있습니다. "
                    "Editor에서 Play를 먼저 누르거나, Editor를 닫은 뒤 DTAM 실행을 다시 눌러 주세요. "
                    f"자동 패키지 실행은 포트 충돌을 막기 위해 중단했습니다. ({exc.detail})"
                ),
            ) from exc
    else:
        if existing_airsim_runtime:
            unreal_status = _request_json(
                f"{visualization_url}/api/unreal/launch",
                method="POST",
                body={},
                timeout_s=8.0,
            )
            airsim_status = _wait_for_airsim_connection(visualization_url, timeout_s=15.0)
        elif not _wait_for_rpc_port_closed(AIRSIM_RPC_HOST, AIRSIM_RPC_PORT, timeout_s=8.0):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"AirSim RPC 포트 {AIRSIM_RPC_PORT}가 아직 사용 중입니다. "
                    "기존 Unreal/AirSim 창을 닫은 뒤 다시 실행해 주세요."
                ),
            )
        else:
            unreal_status = _request_json(
                f"{visualization_url}/api/unreal/launch",
                method="POST",
                body={},
                timeout_s=8.0,
            )
            airsim_status = _wait_for_airsim_connection(visualization_url, timeout_s=45.0)
    airmobility_status = _prepare_airmobility_control(
        airmobility_url=airmobility_url,
        controller=controller,
        vehicle_map=vehicle_map,
    )

    return {
        "ok": True,
        "message": "DTAM execution prepared",
        "controller": controller,
        "control_mode": CONTROL_MODE_BY_CONTROLLER[controller],
        "vehicle_count": len(settings_result["vehicles"]),
        "vehicles": settings_result["vehicles"],
        "vehicle_map": vehicle_map,
        "settings_path": str(UNREAL_SETTINGS_PATH),
        "vm_config_path": str(VM_CONFIG_PATH),
        "mission_guide_path": str(mission_guide_path),
        "modules": {
            "server": server_url,
            "mission": mission_url,
            "airmobility": airmobility_url,
            "visualization": visualization_url,
        },
        "unreal": unreal_status,
        "airsim": airsim_status,
        "airmobility": airmobility_status,
    }


def _mode_payload_from_request(request_payload: dict[str, Any]) -> dict[str, Any]:
    payload = request_payload.get("payload") if isinstance(request_payload, dict) else None
    if isinstance(payload, dict):
        return payload
    if isinstance(request_payload, dict):
        return request_payload
    raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)


def _validate_mode_payload(mode_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    operation_mode = str(mode_payload.get("operationMode") or "").strip()
    if operation_mode != "single":
        raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)

    single_flight = mode_payload.get("singleFlight") or {}
    vehicle_sim_type = single_flight.get("vehicleSimType") or {}
    controller = str(vehicle_sim_type.get("mainVehicleController") or "").strip()
    if controller not in VALID_CONTROLLERS:
        raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)

    mission_planning = single_flight.get("missionPlanning") or {}
    raw_missions = mission_planning.get("missions") or []
    if not isinstance(raw_missions, list) or not raw_missions:
        raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)

    missions: list[dict[str, Any]] = []
    for entry in raw_missions:
        if not isinstance(entry, dict):
            raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
        departure = str(entry.get("departureName") or "").strip()
        arrival = str(entry.get("arrivalName") or "").strip()
        route_data = entry.get("routeData")
        if not departure or not arrival or not isinstance(route_data, dict):
            raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
        _resolve_settings_start_point(entry)
        missions.append(entry)

    return missions, controller


def _write_unreal_vehicle_settings(missions: list[dict[str, Any]]) -> dict[str, Any]:
    settings = _read_json_file(UNREAL_SETTINGS_PATH)
    existing_vehicles = settings.get("Vehicles")
    if not isinstance(existing_vehicles, dict) or not existing_vehicles:
        existing_vehicles = {"Drone1": _default_vehicle_template()}

    first_template = copy.deepcopy(next(iter(existing_vehicles.values())))
    vehicles: dict[str, Any] = {}
    vehicle_map: dict[str, str] = {}
    vehicle_summary: list[dict[str, Any]] = []

    used_aircraft_ids: set[str] = set()
    for index, mission in enumerate(missions, start=1):
        vehicle_name = f"Drone{index}"
        aircraft_id = _aircraft_id_from_mission(mission, index, used_aircraft_ids)
        used_aircraft_ids.add(aircraft_id)

        source_template = existing_vehicles.get(vehicle_name) or first_template
        vehicle = copy.deepcopy(source_template)
        start_point = _resolve_settings_start_point(mission)
        north_m, east_m, _down_m = wgs84_to_airsim_ned(
            float(start_point["lat"]),
            float(start_point["lon"]),
            _point_altitude_m(start_point),
        )

        vehicle["VehicleType"] = vehicle.get("VehicleType") or "SimpleFlight"
        vehicle["AutoCreate"] = True
        vehicle["DefaultVehicleState"] = vehicle.get("DefaultVehicleState") or "Armed"
        vehicle["X"] = round(float(north_m), 3)
        vehicle["Y"] = round(float(east_m), 3)
        vehicle["Z"] = _vehicle_spawn_z(existing_vehicles.get(vehicle_name), first_template)

        yaw_deg = _point_yaw_deg(start_point)
        if yaw_deg is None:
            yaw_deg = _initial_route_heading_deg(mission)
        if yaw_deg is not None:
            vehicle["Yaw"] = round(float(yaw_deg) % 360.0, 3)

        vehicles[vehicle_name] = vehicle
        vehicle_map[aircraft_id] = vehicle_name
        vehicle_summary.append({
            "aircraft_id": aircraft_id,
            "vehicle_name": vehicle_name,
            "departure": mission.get("departureName") or "",
            "arrival": mission.get("arrivalName") or "",
            "x": vehicle["X"],
            "y": vehicle["Y"],
            "z": vehicle["Z"],
            "yaw": vehicle.get("Yaw"),
            "lat": float(start_point["lat"]),
            "lon": float(start_point["lon"]),
            "spawn_point_id": start_point.get("spawn_point_id"),
        })

    settings["Vehicles"] = vehicles
    _write_json_file(UNREAL_SETTINGS_PATH, settings)
    _write_json_file(DOCUMENTS_AIRSIM_SETTINGS_PATH, settings)
    _write_vm_vehicle_map(vehicle_map)

    return {
        "vehicles": vehicle_summary,
        "vehicle_map": vehicle_map,
    }


def _write_vm_vehicle_map(vehicle_map: dict[str, str]) -> None:
    config = _read_json_file(VM_CONFIG_PATH)
    airsim = config.get("airsim")
    if not isinstance(airsim, dict):
        airsim = {}
        config["airsim"] = airsim
    airsim["vehicle_map"] = vehicle_map
    _write_json_file(VM_CONFIG_PATH, config)


def _write_unreal_mission_guides(
    missions: list[dict[str, Any]],
    vehicle_summary: list[dict[str, Any]],
) -> Path:
    guides: list[dict[str, Any]] = []
    for index, mission in enumerate(missions):
        vehicle = vehicle_summary[index] if index < len(vehicle_summary) else {}
        points = _mission_guide_points_from_route(mission)
        if len(points) < 2:
            continue
        _attach_airsim_ned_to_guide_points(points, vehicle)

        guides.append({
            "aircraft_id": str(vehicle.get("aircraft_id") or _aircraft_id_from_mission(mission, index + 1, set())),
            "vehicle_name": str(vehicle.get("vehicle_name") or f"Drone{index + 1}"),
            "departure": str(mission.get("departureName") or vehicle.get("departure") or ""),
            "arrival": str(mission.get("arrivalName") or vehicle.get("arrival") or ""),
            "coordinate_frame": "airsim_global_ned_from_departure_relative",
            "spawn_ned": {
                "north": round(float(_as_float(vehicle.get("x")) or 0.0), 3),
                "east": round(float(_as_float(vehicle.get("y")) or 0.0), 3),
                "down": round(float(_as_float(vehicle.get("z")) or 0.0), 3),
            },
            "points": points,
        })

    payload = {
        "version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "vehicles": guides,
    }
    _write_json_file(UNREAL_MISSION_GUIDE_PATH, payload)
    return UNREAL_MISSION_GUIDE_PATH


def _mission_guide_points_from_route(mission: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    route_data = mission.get("routeData") if isinstance(mission.get("routeData"), dict) else {}

    for key in ("departureTakeoff", "departure_takeoff"):
        _append_mission_guide_point(points, route_data.get(key))
        if points:
            break

    route_points = None
    for key in ("points", "routePoints", "route_points"):
        value = route_data.get(key)
        if isinstance(value, list) and value:
            route_points = value
            break
    if route_points is None:
        for key in ("missionWaypoints", "mission_waypoints", "waypoints"):
            value = route_data.get(key)
            if isinstance(value, list) and value:
                route_points = value
                break
    _append_mission_guide_point_array(points, route_points)

    for key in ("arrivalTouchdown", "arrival_touchdown"):
        before = len(points)
        _append_mission_guide_point(points, route_data.get(key))
        if len(points) > before:
            break

    if len(points) < 2:
        _append_icd_enroute_points(points, mission.get("enRoute") or mission.get("en_route"))

    return points


def _attach_airsim_ned_to_guide_points(points: list[dict[str, Any]], vehicle: dict[str, Any]) -> None:
    if not points:
        return

    origin = points[0]
    if not _is_geo_point(origin):
        return

    spawn_north_m = float(_as_float(vehicle.get("x")) or 0.0)
    spawn_east_m = float(_as_float(vehicle.get("y")) or 0.0)
    spawn_down_m = float(_as_float(vehicle.get("z")) or 0.0)
    origin_lat = float(origin["lat"])
    origin_lon = float(origin["lon"])
    origin_alt_m = _point_altitude_m(origin)

    for point in points:
        if not _is_geo_point(point):
            continue
        try:
            offset = convert_target_to_unreal(
                player_start_lat=origin_lat,
                player_start_lon=origin_lon,
                player_start_alt_m=origin_alt_m,
                target_lat=float(point["lat"]),
                target_lon=float(point["lon"]),
                target_alt_m=_point_altitude_m(point),
                x_axis_heading_deg=DEFAULT_CUSTOM_X_AXIS_HEADING_DEG,
                y_axis_heading_deg=DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG,
            )
            rel = offset["custom_unreal_m"]
            point["ned"] = {
                "north": round(spawn_north_m + float(rel["x"]), 3),
                "east": round(spawn_east_m + float(rel["y"]), 3),
                "down": round(spawn_down_m + float(rel["z"]), 3),
            }
            point["local_ned"] = {
                "north": round(float(rel["x"]), 3),
                "east": round(float(rel["y"]), 3),
                "down": round(float(rel["z"]), 3),
            }
        except Exception:
            continue


def _append_mission_guide_point_array(points: list[dict[str, Any]], values: Any) -> None:
    if not isinstance(values, list):
        return
    for item in values:
        _append_mission_guide_point(points, item)


def _append_icd_enroute_points(points: list[dict[str, Any]], segments: Any) -> None:
    if not isinstance(segments, list):
        return
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        for key in ("startLLA", "start_lla", "start"):
            if _append_mission_guide_point(points, segment.get(key)):
                break
        for key in ("endLLA", "end_lla", "end"):
            if _append_mission_guide_point(points, segment.get(key)):
                break


def _append_mission_guide_point(points: list[dict[str, Any]], raw_point: Any) -> bool:
    if not _is_geo_point(raw_point):
        return False
    assert isinstance(raw_point, dict)

    lat = float(raw_point["lat"])
    lon = float(raw_point["lon"])
    alt_m = _point_altitude_m(raw_point)
    point = {
        "lat": round(lat, 8),
        "lon": round(lon, 8),
        "alt_m": round(float(alt_m), 3),
    }
    label = _mission_guide_point_label(raw_point)
    if label:
        point["name"] = label

    if points:
        previous = points[-1]
        if (
            abs(float(previous["lat"]) - point["lat"]) < 1.0e-8
            and abs(float(previous["lon"]) - point["lon"]) < 1.0e-8
            and abs(float(previous["alt_m"]) - point["alt_m"]) < 0.05
        ):
            return False

    points.append(point)
    return True


def _mission_guide_point_label(point: dict[str, Any]) -> str:
    for key in ("name", "id", "waypointId", "waypoint_id", "phase", "type"):
        value = point.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _prepare_airmobility_control(
    *,
    airmobility_url: str,
    controller: str,
    vehicle_map: dict[str, str],
) -> dict[str, Any]:
    try:
        _request_json(
            f"{airmobility_url}/api/service/stop",
            method="POST",
            body={},
            timeout_s=5.0,
        )
    except HTTPException:
        pass

    control_mode = CONTROL_MODE_BY_CONTROLLER[controller]
    if controller == "Autopilot":
        return _request_json(
            f"{airmobility_url}/api/control/mode",
            method="POST",
            body={"mode": control_mode},
            timeout_s=5.0,
        )

    aircraft_id, airsim_vehicle_name = next(iter(vehicle_map.items()))
    endpoint = "keyboard" if controller == "Keyboard" else "joystick"
    return _request_json(
        f"{airmobility_url}/api/control/{endpoint}/start",
        method="POST",
        body={
            "vehicle_id": aircraft_id,
            "airsim_vehicle_name": airsim_vehicle_name,
        },
        timeout_s=8.0,
    )


def _wait_for_airsim_connection(visualization_url: str, *, timeout_s: float) -> dict[str, Any]:
    deadline = time.time() + max(timeout_s, 1.0)
    last_status: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            status = _request_json(
                f"{visualization_url}/api/airsim/connect",
                method="POST",
                body={},
                timeout_s=3.0,
            )
            last_status = status if isinstance(status, dict) else {}
            if bool(last_status.get("connected")):
                return last_status
        except HTTPException as exc:
            last_status = {"error": exc.detail}
        time.sleep(1.0)

    reason = last_status.get("last_error") or last_status.get("error") or "AirSim connection timeout"
    raise HTTPException(status_code=504, detail=f"Unreal은 켜졌지만 AirSim 연결이 완료되지 않았습니다: {reason}")


def _wait_for_rpc_port_closed(host: str, port: int, *, timeout_s: float) -> bool:
    deadline = time.time() + max(timeout_s, 0.5)
    while time.time() < deadline:
        if not _is_rpc_port_open(host, port):
            return True
        time.sleep(0.25)
    return not _is_rpc_port_open(host, port)


def _is_rpc_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.2):
            return True
    except OSError:
        return False


def _find_dtam_unreal_editor_processes() -> list[dict[str, Any]]:
    if not sys.platform.startswith("win"):
        return []
    project_path = str(UNREAL_PROJECT_PATH)
    command = (
        "$ErrorActionPreference='SilentlyContinue'; "
        "Get-CimInstance Win32_Process -Filter \"Name='UnrealEditor.exe'\" | "
        f"Where-Object {{ $_.CommandLine -like '*{_escape_ps_like(project_path)}*' }} | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=4.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    raw = result.stdout.decode("utf-8", errors="replace").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    items = payload if isinstance(payload, list) else [payload]
    processes: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            pid = int(item.get("ProcessId") or 0)
        except (TypeError, ValueError):
            pid = 0
        if pid <= 0:
            continue
        processes.append({
            "pid": pid,
            "command_line": str(item.get("CommandLine") or ""),
        })
    return processes


def _escape_ps_like(value: str) -> str:
    return value.replace("`", "``").replace("[", "`[").replace("]", "`]").replace("'", "''")


def _resolve_settings_start_point(mission: dict[str, Any]) -> dict[str, Any]:
    """Use the same ODT S25/F2 departure spawn that MissionPlanner uses."""
    route_data = mission.get("routeData") if isinstance(mission.get("routeData"), dict) else {}
    departure = str(mission.get("departureName") or "").strip()
    if not departure:
        path = route_data.get("path")
        if isinstance(path, list) and path:
            departure = str(path[0] or "").strip()

    planner = _get_route_planner()
    port = planner.ports.get(departure) if planner is not None and departure else None
    if port is not None:
        fallback_point = _extract_start_point(mission)
        ground_m = _route_ground_m(route_data)
        if ground_m is None:
            ground_m = _as_float(fallback_point.get("ground_m"))
        if ground_m is None:
            alt = _as_float(fallback_point.get("alt_m"))
            ground_m = float(alt) - 1.6 if alt is not None else 0.0
        try:
            spawn = get_vertiport_spawn_point(
                vertiport_name=departure,
                vertiport_lat=float(port.lat),
                vertiport_lon=float(port.lon),
                vertiport_ground_m=float(ground_m),
                spawn_point_id="S25",
            )
        except Exception:
            spawn = None
        if isinstance(spawn, dict) and _is_geo_point(spawn):
            return {
                "name": f"{departure} S25 F2",
                "lat": float(spawn["lat"]),
                "lon": float(spawn["lon"]),
                "alt_m": float(spawn.get("alt_m") or ground_m),
                "ground_m": float(spawn.get("ground_m") or ground_m),
                "yaw_deg": _point_yaw_deg(spawn),
                "spawn_point_id": "S25",
            }

    return _extract_start_point(mission)


def _get_route_planner() -> RoutePlanner | None:
    global _ROUTE_PLANNER_CACHE
    if _ROUTE_PLANNER_CACHE is not None:
        return _ROUTE_PLANNER_CACHE
    vp_csv, wp_csv = _route_planner_csv_pair()
    if not (vp_csv.exists() and wp_csv.exists()):
        return None
    try:
        _ROUTE_PLANNER_CACHE = RoutePlanner.from_csv(vp_csv, wp_csv)
    except Exception:
        _ROUTE_PLANNER_CACHE = None
    return _ROUTE_PLANNER_CACHE


def _route_planner_csv_pair() -> tuple[Path, Path]:
    operations_env_dir = FRAMEWORK_ROOT / "DB" / "operational_environment" / "active"
    candidates = (
        (
            MP_DATA_DIR / "vertiport_default.csv",
            MP_DATA_DIR / "waypoint_default.csv",
        ),
        (
            operations_env_dir / "vertiport_default.csv",
            operations_env_dir / "corridor_default.csv",
        ),
    )
    for vp_csv, wp_csv in candidates:
        if vp_csv.exists() and wp_csv.exists():
            return vp_csv, wp_csv
    return candidates[-1]


def _route_ground_m(route_data: dict[str, Any]) -> float | None:
    candidates: list[Any] = []
    for key in ("departureTakeoff", "departure_takeoff"):
        point = route_data.get(key)
        if isinstance(point, dict):
            candidates.append(point)
    for key in ("missionWaypoints", "mission_waypoints", "waypoints", "points"):
        points = route_data.get(key)
        if isinstance(points, list):
            candidates.extend(point for point in points if isinstance(point, dict))
    for point in candidates:
        value = _as_float(point.get("ground_m"))
        if value is not None:
            return float(value)
    return None


def _extract_start_point(mission: dict[str, Any]) -> dict[str, Any]:
    route_data = mission.get("routeData") or {}
    for key in ("departureTakeoff", "departure_takeoff"):
        point = route_data.get(key)
        if _is_geo_point(point):
            return point

    for key in ("missionWaypoints", "mission_waypoints", "waypoints", "points"):
        points = route_data.get(key)
        if isinstance(points, list):
            for point in points:
                if _is_geo_point(point):
                    return point

    raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)


def _initial_route_heading_deg(mission: dict[str, Any]) -> float | None:
    route_data = mission.get("routeData") or {}
    points: list[dict[str, Any]] = []
    for key in ("missionWaypoints", "mission_waypoints", "waypoints", "points"):
        values = route_data.get(key)
        if isinstance(values, list):
            points = [item for item in values if _is_geo_point(item)]
            if len(points) >= 2:
                break
    if len(points) < 2:
        return None
    start = _extract_start_point(mission)
    for point in points:
        if _geo_distance_hint(start, point) > 1.0e-9:
            return _bearing_deg(start, point)
    return None


def _bearing_deg(start: dict[str, Any], end: dict[str, Any]) -> float | None:
    lat1 = math.radians(float(start["lat"]))
    lat2 = math.radians(float(end["lat"]))
    dlon = math.radians(float(end["lon"]) - float(start["lon"]))
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    if abs(x) < 1.0e-12 and abs(y) < 1.0e-12:
        return None
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _geo_distance_hint(start: dict[str, Any], end: dict[str, Any]) -> float:
    return abs(float(start["lat"]) - float(end["lat"])) + abs(float(start["lon"]) - float(end["lon"]))


def _is_geo_point(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return _as_float(value.get("lat")) is not None and _as_float(value.get("lon")) is not None


def _point_altitude_m(point: dict[str, Any]) -> float:
    for key in ("alt_m", "alt", "altitude", "ground_m"):
        value = _as_float(point.get(key))
        if value is not None:
            return float(value)
    return 0.0


def _point_yaw_deg(point: dict[str, Any]) -> float | None:
    for key in ("yaw_deg", "Yaw_deg", "yaw", "Yaw", "heading_deg", "heading"):
        value = _as_float(point.get(key))
        if value is not None:
            return float(value) % 360.0
    return None


def _vehicle_spawn_z(vehicle_template: Any, fallback_template: dict[str, Any]) -> float:
    if isinstance(vehicle_template, dict):
        value = _as_float(vehicle_template.get("Z"))
        if value is not None:
            return float(value)
    value = _as_float(fallback_template.get("Z"))
    return float(value) if value is not None else -3.1


def _aircraft_id_from_mission(mission: dict[str, Any], index: int, used: set[str]) -> str:
    name = str(mission.get("aircraftName") or "").strip()
    match = re.search(r"(\d+)\s*$", name)
    number = int(match.group(1)) if match else index
    aircraft_id = f"UAM{number:04d}"
    if aircraft_id not in used:
        return aircraft_id
    return f"UAM{index:04d}"


def _default_vehicle_template() -> dict[str, Any]:
    return {
        "VehicleType": "SimpleFlight",
        "AutoCreate": True,
        "DefaultVehicleState": "Armed",
        "X": 0.0,
        "Y": 0.0,
        "Z": -3.1,
        "Yaw": 0.0,
    }


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid JSON file: {path}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail=f"Expected JSON object: {path}")
    return data


def _write_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout_s: float = 5.0,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib_request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib_request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read()
    except urllib_error.HTTPError as exc:
        detail = _http_error_detail(exc)
        raise HTTPException(status_code=502, detail=f"{method.upper()} {url} failed: {detail}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{method.upper()} {url} failed: {type(exc).__name__}: {exc}") from exc

    if not raw:
        return {}
    try:
        data_obj = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"{method.upper()} {url} returned invalid JSON") from exc
    return data_obj if isinstance(data_obj, dict) else {"value": data_obj}


def _http_error_detail(exc: urllib_error.HTTPError) -> str:
    raw = exc.read()
    if not raw:
        return str(exc.reason)
    try:
        payload = json.loads(raw.decode("utf-8"))
        if isinstance(payload, dict) and payload.get("detail"):
            return str(payload["detail"])
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return raw.decode("utf-8", errors="replace")


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
