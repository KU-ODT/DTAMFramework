"""DTAM execution preparation owned by the Operations Console."""

from __future__ import annotations

import copy
import csv
import json
import logging
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

logger = logging.getLogger(__name__)

from app.services.module_process_service import (
    cleanup_stale_visualization_processes,
    ensure_module_backend,
    stop_module,
)


FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
UNREAL_SETTINGS_PATH = (
    FRAMEWORK_ROOT
    / "VisualizationModule"
    / "runtime"
    / "Unreal"
    / "Environments"
    / "DTAMVisualization"
    / "settings.json"
)
DOCUMENTS_AIRSIM_SETTINGS_PATH = Path.home() / "Documents" / "AirSim" / "settings.json"
VM_CONFIG_PATH = FRAMEWORK_ROOT / "VisualizationModule" / "data" / "configs" / "vm_config.json"
UNREAL_DEFAULT_MAP_ARG = "/AirSim/KP2A/KP2A_Map"
UNREAL_PROJECT_PATH = (
    FRAMEWORK_ROOT
    / "VisualizationModule"
    / "runtime"
    / "Unreal"
    / "Environments"
    / "DTAMVisualization"
    / "DTAMVisualization.uproject"
)
UNREAL_MISSION_GUIDE_PATH = UNREAL_PROJECT_PATH.parent / "Data" / "mission_guides.json"
PACKAGED_LAUNCH_SETTINGS_PATH = (
    UNREAL_PROJECT_PATH.parent
    / "Saved"
    / "StagedBuilds"
    / "Windows"
    / "settings.json"
)
VISUALIZATION_LAUNCH_BASELINE_SETTINGS_PATH = (
    UNREAL_PROJECT_PATH.parent
    / "Saved"
    / "StagedBuilds"
    / "Windows"
    / "Config"
    / "settings.json"
)
AIRSIM_RPC_HOST = "127.0.0.1"
AIRSIM_RPC_PORT = 41451
VISUALIZATION_BACKEND_URL = "http://127.0.0.1:8097"
AIRMOBILITY_BACKEND_URL = "http://127.0.0.1:8100"
MISSION_INCOMPLETE_MESSAGE = "Complete mission planning first."
# Demo scenarios lock the console mission editor, so the 1001 payload carries no
# usable missionPlanning.missions[].  Bridge the gap from the pre-authored demo
# plan packs (Msg3001 wire dicts) instead.
DEMO_PLAN_PACKS = {
    "S1": "S1_nominal",
    "S3": "S3_uao_battery_alt_vertiport",
}
# S2 데모는 FlightScheduler 의 3,360편 prebuilt 셋을 사용 (사용자 결정 2026-06-11).
# 스폰 합성은 FPL 폴더에서 기체별 dedupe 로 수행 (아래 _demo_missions_from_pack).
DEMO_FPL_PACKS = {
    "S2": "20260611_131306_98f166edc22f",
}
DEMO_PLANS_DIR = FRAMEWORK_ROOT / "MissionModule" / "data" / "demo_plans"
# FlightScheduler plugin output: FPL/<run folder>/FPL_all.csv (utf-8-sig, no route).
FPL_FOLDERS_DIR = FRAMEWORK_ROOT / "PlugIn" / "FlightScheduler" / "FPL"
# fpn fallback base when fpl_id has no usable numeric part.
FPL_FPN_FALLBACK_BASE = 1301
VALID_CONTROLLERS = {"Joystick", "Keyboard", "Autopilot"}
VALID_DYNAMICS_MODELS = {"simple", "highFidelity"}
DEFAULT_DYNAMICS_MODEL = "simple"
CONTROL_MODE_BY_CONTROLLER = {
    "Autopilot": "mission",
    "Keyboard": "keyboard",
    "Joystick": "joystick",
}
STREAM_CAMERA_NAME = "front_center"
STREAM_CAMERA_IMAGE_TYPE = 0
STREAM_CAMERA_WIDTH = 640
STREAM_CAMERA_HEIGHT = 360
STREAM_CAMERA_FOV_DEG = 90
# AirSim vehicle spawn Z uses NED: positive means "down", negative means "up".
# Keep the initial DT World spawn on the departure vertiport surface, not on the
# route's departure-takeoff clearance point.  Otherwise X/Y looks correct but the
# aircraft appears tens of meters above the pad until the first 4001 pose arrives.
AIRSIM_VEHICLE_GROUND_SPAWN_Z_M = 0.0
AIRSIM_SPAWN_Z_OVERRIDE_KEYS = ("DTAMSpawnZOverride", "spawn_z_override_m", "SpawnZOverrideM")
VERTIPORT_SURFACE_CLEARANCE_M = 10.0
# AirSim settings Z is NED down.  The coordinateDB FATO Z_m is a visual/database
# height, not the actual pawn spawn surface in the packaged DT World runtime.
# Spawn near the visual pad surface and keep a tiny clearance so the gear is not
# embedded in the mesh.
AIRSIM_FATO_SPAWN_CLEARANCE_M = 1.0
# DT World's KP2A map does not contain a saved PlayerStart.  Cosys-AirSim uses
# the existing KP2A pawn at Unreal (0,0,0) as the global NED origin.  The Cesium
# bootstrap then places that Unreal origin at this geodetic height.  Therefore
# AirSim settings Z must be computed as "Cesium origin height - pad height"
# rather than by the old CityHall coordinateDB Z fit.
DEFAULT_CESIUM_ORIGIN_HEIGHT_M = 350.0

if str(FRAMEWORK_ROOT) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT))

from MissionModule.app.config import DATA_DIR as MP_DATA_DIR  # noqa: E402
from MissionModule.app.domain.converter_tool import get_vertiport_spawn_point  # noqa: E402
from MissionModule.app.domain.coord_transform import wgs84_to_airsim_ned  # noqa: E402
from MissionModule.app.domain.unreal_spawn_mapping import lookup_unreal_spawn_point  # noqa: E402
from MissionModule.app.services.route_planner import RoutePlanner  # noqa: E402
from VehicleModule.app.domain.transform.odt_pose_frame import (  # noqa: E402
    DEFAULT_CUSTOM_X_AXIS_HEADING_DEG,
    DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG,
    convert_target_to_unreal,
)


_ROUTE_PLANNER_CACHE: RoutePlanner | None = None


def get_dtam_runtime_status() -> dict[str, Any]:
    """Return a lightweight DT World runtime status for the Operation UI."""

    airsim_rpc_open = _is_rpc_port_open(AIRSIM_RPC_HOST, AIRSIM_RPC_PORT)
    airmobility_status = _request_airmobility_status(AIRMOBILITY_BACKEND_URL, timeout_s=0.8)
    airmobility_ready = bool(airmobility_status.get("ok"))
    try:
        vm_state = _request_visualization_status(VISUALIZATION_BACKEND_URL, timeout_s=3.0)
    except HTTPException as exc:
        return {
            "ok": False,
            "visualization_ready": False,
            "airmobility_ready": airmobility_ready,
            "running": airsim_rpc_open,
            "airsim_rpc_open": airsim_rpc_open,
            "airmobility": airmobility_status,
            "error": str(exc.detail),
        }

    unreal = vm_state.get("unreal") if isinstance(vm_state.get("unreal"), dict) else {}
    airsim = vm_state.get("airsim") if isinstance(vm_state.get("airsim"), dict) else {}
    unreal_running = bool(unreal.get("running"))
    airsim_connected = bool(airsim.get("connected"))
    return {
        "ok": True,
        "visualization_ready": True,
        "airmobility_ready": airmobility_ready,
        "running": bool(unreal_running or airsim_connected or airsim_rpc_open),
        "airsim_rpc_open": airsim_rpc_open,
        "unreal": unreal,
        "airsim": airsim,
        "airmobility": airmobility_status,
    }


def launch_dtam_world() -> dict[str, Any]:
    """Launch DT World exactly through VisualizationModule's normal button path.

    Keep this endpoint intentionally thin.  The VisualizationModule Launch
    button only calls ``/api/unreal/launch`` on the Visualization backend; it
    does not submit the mission, does not send 2001/2002, and does not attach
    VehicleModule control state.  OperationModule should behave the same here;
    mission/control attachment is triggered later by the playback flow.
    """

    launch_settings = _restore_visualization_launch_settings()
    visualization_url = ensure_module_backend("visualization", timeout_s=45.0)
    unreal_status = _request_unreal_launch(visualization_url)
    try:
        runtime_status = _request_visualization_status(visualization_url, timeout_s=3.0)
    except HTTPException:
        runtime_status = {}
    return {
        "ok": True,
        "message": "DT World launch requested",
        "modules": {"visualization": visualization_url},
        "unreal": unreal_status,
        "runtime": runtime_status,
        "launch_settings": launch_settings,
    }


def _restore_visualization_launch_settings() -> dict[str, Any]:
    """Restore the AirSim settings that VisualizationModule Launch expects.

    Operation-side mission preparation can legitimately write mission-derived
    spawn coordinates into ``settings.json`` for control setup.  That file is
    also read by packaged Unreal at startup though; if the user only presses
    "DT World 실행", those mission coordinates make the launch diverge from
    VisualizationModule's own Launch button and can leave the runtime looking at
    sky/ocean while Cesium is still loading.  Before every DT World launch,
    reset the launch-time AirSim settings from the packaged baseline under
    ``Saved/StagedBuilds/Windows/Config``.
    """

    source_path = (
        VISUALIZATION_LAUNCH_BASELINE_SETTINGS_PATH
        if VISUALIZATION_LAUNCH_BASELINE_SETTINGS_PATH.exists()
        else PACKAGED_LAUNCH_SETTINGS_PATH
    )
    settings = _read_json_file(source_path)
    _apply_unreal_runtime_safety_settings(settings)
    _apply_camera_stream_capture_settings(settings)

    target_paths = [
        UNREAL_SETTINGS_PATH,
        DOCUMENTS_AIRSIM_SETTINGS_PATH,
        PACKAGED_LAUNCH_SETTINGS_PATH,
    ]
    for target_path in target_paths:
        _write_json_file(target_path, settings)

    vehicles = settings.get("Vehicles") if isinstance(settings.get("Vehicles"), dict) else {}
    return {
        "source": str(source_path),
        "targets": [str(path) for path in target_paths],
        "vehicles": {
            name: {
                "X": vehicle.get("X"),
                "Y": vehicle.get("Y"),
                "Z": vehicle.get("Z"),
                "Yaw": vehicle.get("Yaw"),
            }
            for name, vehicle in vehicles.items()
            if isinstance(vehicle, dict)
        },
    }


def apply_dtam_control_modes(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Apply OperationModule mission controller selections to VehicleModule."""

    mode_payload = _mode_payload_from_request(request_payload)
    missions, controller = _validate_mode_payload(
        mode_payload, demo_scenario_id=_demo_scenario_from_request(request_payload)
    )
    settings_result = _write_unreal_vehicle_settings(missions)
    airmobility_url = ensure_module_backend("airmobility", timeout_s=30.0)

    vehicle_map = settings_result["vehicle_map"]
    controller_by_aircraft = _controller_by_aircraft(settings_result["vehicles"], controller)
    dynamics_by_aircraft = _dynamics_by_aircraft(settings_result["vehicles"])
    provider_by_aircraft = _provider_by_aircraft(settings_result["vehicles"])
    _validate_dynamics_controller_pairs(controller_by_aircraft, dynamics_by_aircraft)
    vehicle_spawns = _manual_vehicle_spawn_configs(settings_result["vehicles"])

    visualization_url = ""
    try:
        visualization_url = ensure_module_backend("visualization", timeout_s=10.0)
        _request_json(
            f"{visualization_url}/api/airsim/vehicle-map",
            method="PATCH",
            body=vehicle_map,
            timeout_s=4.0,
        )
    except HTTPException:
        visualization_url = ""

    if _is_rpc_port_open(AIRSIM_RPC_HOST, AIRSIM_RPC_PORT) and visualization_url:
        airmobility_status = _prepare_airmobility_control(
            airmobility_url=airmobility_url,
            controller=controller,
            vehicle_map=vehicle_map,
            controller_by_aircraft=controller_by_aircraft,
            dynamics_by_aircraft=dynamics_by_aircraft,
            provider_by_aircraft=provider_by_aircraft,
            vehicle_spawns=vehicle_spawns,
        )
        capture_deferred = False
    else:
        airmobility_status = _apply_airmobility_control_modes_only(
            airmobility_url=airmobility_url,
            controller=controller,
            vehicle_map=vehicle_map,
            controller_by_aircraft=controller_by_aircraft,
            dynamics_by_aircraft=dynamics_by_aircraft,
            provider_by_aircraft=provider_by_aircraft,
            vehicle_spawns=vehicle_spawns,
        )
        capture_deferred = True
    vfds_runtime = _ensure_vfds_runtime_for_mapping(airmobility_url, dynamics_by_aircraft)

    return {
        "ok": True,
        "message": "DTAM controller modes applied",
        "controller": controller,
        "control_mode": CONTROL_MODE_BY_CONTROLLER[controller],
        "controller_by_aircraft": controller_by_aircraft,
        "dynamics_by_aircraft": dynamics_by_aircraft,
        "provider_by_aircraft": provider_by_aircraft,
        "vehicle_map": vehicle_map,
        "modules": {
            "airmobility": airmobility_url,
            "visualization": visualization_url,
        },
        "airmobility": airmobility_status,
        "vfds": vfds_runtime,
        "capture_deferred": capture_deferred,
    }


def ensure_vfds_runtime(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure VehicleModule's embedded VFDS server is ready for high-fidelity missions."""
    mode_payload = _mode_payload_from_request(request_payload)
    missions, _controller = _validate_mode_payload(
        mode_payload, demo_scenario_id=_demo_scenario_from_request(request_payload)
    )
    fallback_dynamics = str(
        ((mode_payload.get("singleFlight") or {}).get("vehicleSimType") or {}).get("dynamics")
        or DEFAULT_DYNAMICS_MODEL
    ).strip()
    dynamics_by_aircraft = _high_fidelity_aircraft_from_missions(missions, fallback_dynamics)
    airmobility_url = ensure_module_backend("airmobility", timeout_s=30.0)
    return _ensure_vfds_runtime_for_mapping(airmobility_url, dynamics_by_aircraft)


def prepare_dtam_execution(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the console mission and prepare external DTAM modules."""
    mode_payload = _mode_payload_from_request(request_payload)
    skip_unreal_launch = _bool_payload_value(
        mode_payload.get("skipUnrealLaunch"),
        mode_payload.get("_skip_unreal_launch"),
        request_payload.get("skipUnrealLaunch") if isinstance(request_payload, dict) else None,
    )
    missions, controller = _validate_mode_payload(
        mode_payload, demo_scenario_id=_demo_scenario_from_request(request_payload)
    )
    editor_processes = _find_dtam_unreal_editor_processes()
    # If DT World was already launched through the Visualization-equivalent path,
    # attach to it instead of rebuilding the Unreal/AirSim process from
    # OperationModule.  This keeps Operation's DT World button visually identical
    # to VisualizationModule's Launch button.
    existing_airsim_runtime = _is_rpc_port_open(AIRSIM_RPC_HOST, AIRSIM_RPC_PORT)
    existing_visualization_backend = _is_visualization_backend_ready()
    if (
        skip_unreal_launch
        and not editor_processes
        and len(missions) > 1
        and not existing_airsim_runtime
        and not existing_visualization_backend
    ):
        # skipUnrealLaunch is used by the Play path to attach to an already
        # running DT World.  Do not turn that into a relaunch when a runtime is
        # actually alive.  Only fall back to a real launch if there is no runtime
        # to attach to at all.
        skip_unreal_launch = False
    if not skip_unreal_launch and not existing_airsim_runtime and not existing_visualization_backend:
        try:
            stop_module("visualization")
        except Exception:
            pass
        cleanup_stale_visualization_processes()

    settings_result = _write_unreal_vehicle_settings(
        missions,
        preserve_existing_spawn=skip_unreal_launch,
    )
    mission_guide_path = _write_unreal_mission_guides(missions, settings_result["vehicles"])
    # _write_unreal_vehicle_settings() also updates vm_config.json.  If a
    # Visualization backend / packaged Unreal was already open, restart it now
    # so the AirSim home geolocation and Cesium stream camera location are
    # rebuilt from the freshly written settings.  Unreal Editor sessions are
    # explicitly preserved because the user owns Play/Stop in the editor.
    if not skip_unreal_launch and existing_airsim_runtime and not editor_processes:
        try:
            stop_module("visualization")
        except Exception:
            pass
        cleanup_stale_visualization_processes()
        existing_airsim_runtime = False
        existing_visualization_backend = False
    elif not skip_unreal_launch and not existing_airsim_runtime and existing_visualization_backend:
        try:
            stop_module("visualization")
        except Exception:
            pass
        cleanup_stale_visualization_processes()
        existing_visualization_backend = False
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
    if skip_unreal_launch:
        unreal_status = _request_visualization_status(visualization_url, timeout_s=3.0).get("unreal", {})
        airsim_status = _wait_for_airsim_connection(visualization_url, timeout_s=90.0)
    elif editor_processes:
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
                    "Unreal Editor is already open with the DTAMVisualization project. "
                    "Start Play in the editor first, or close the editor and run DTAM again. "
                    f"Automatic package execution was stopped to avoid a port conflict. ({exc.detail})"
                ),
            ) from exc
    else:
        if existing_airsim_runtime:
            unreal_status = _request_unreal_launch(visualization_url)
            airsim_status = _wait_for_airsim_connection(visualization_url, timeout_s=15.0)
        elif not _wait_for_rpc_port_closed(AIRSIM_RPC_HOST, AIRSIM_RPC_PORT, timeout_s=8.0):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"AirSim RPC port {AIRSIM_RPC_PORT} is still in use. "
                    "Close the existing Unreal/AirSim window, then run DTAM again."
                ),
            )
        else:
            unreal_status = _request_unreal_launch(visualization_url)
            airsim_status = _wait_for_airsim_connection(visualization_url, timeout_s=150.0)
    controller_by_aircraft = _controller_by_aircraft(settings_result["vehicles"], controller)
    dynamics_by_aircraft = _dynamics_by_aircraft(settings_result["vehicles"])
    provider_by_aircraft = _provider_by_aircraft(settings_result["vehicles"])
    _validate_dynamics_controller_pairs(controller_by_aircraft, dynamics_by_aircraft)
    airmobility_status = _prepare_airmobility_control(
        airmobility_url=airmobility_url,
        controller=controller,
        vehicle_map=vehicle_map,
        controller_by_aircraft=controller_by_aircraft,
        dynamics_by_aircraft=dynamics_by_aircraft,
        provider_by_aircraft=provider_by_aircraft,
        vehicle_spawns=_manual_vehicle_spawn_configs(settings_result["vehicles"]),
    )
    vfds_runtime = _ensure_vfds_runtime_for_mapping(airmobility_url, dynamics_by_aircraft)

    return {
        "ok": True,
        "message": "DTAM execution prepared",
        "controller": controller,
        "control_mode": CONTROL_MODE_BY_CONTROLLER[controller],
        "controller_by_aircraft": controller_by_aircraft,
        "dynamics_by_aircraft": dynamics_by_aircraft,
        "provider_by_aircraft": provider_by_aircraft,
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
        "vfds": vfds_runtime,
    }


def _request_unreal_launch(visualization_url: str) -> dict[str, Any]:
    status = _request_json(
        f"{visualization_url}/api/unreal/launch",
        method="POST",
        body={"pixel_streaming": False},
        timeout_s=12.0,
    )
    if not bool(status.get("ok", True)):
        detail = status.get("error") or status.get("message") or status
        log_path = status.get("log_path")
        if log_path:
            detail = f"{detail} (log: {log_path})"
        raise HTTPException(status_code=502, detail=f"Unreal launch failed: {detail}")
    exit_code = status.get("exit_code")
    if exit_code is not None:
        log_path = status.get("log_path")
        suffix = f" See log: {log_path}" if log_path else ""
        raise HTTPException(status_code=502, detail=f"Unreal exited immediately with code {exit_code}.{suffix}")
    return status


def _mode_payload_from_request(request_payload: dict[str, Any]) -> dict[str, Any]:
    payload = request_payload.get("payload") if isinstance(request_payload, dict) else None
    if isinstance(payload, dict):
        return payload
    if isinstance(request_payload, dict):
        return request_payload
    raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)


def _demo_scenario_from_request(request_payload: dict[str, Any]) -> str:
    """Read the request-level demoScenarioId (sibling of the ICD payload, not inside it)."""
    if isinstance(request_payload, dict):
        return str(request_payload.get("demoScenarioId") or "").strip()
    return ""


def _demo_missions_from_pack(scenario_id: str) -> list[dict[str, Any]] | None:
    """Synthesize console-shaped mission entries from a demo plan pack of Msg3001 files."""
    sid = str(scenario_id or "").strip()
    # S2: FlightScheduler prebuilt 셋 — 기체별 dedupe (최초 편) 로 스폰 entries 합성.
    # 3,360편 전부를 스폰에 올리면 AirSim settings 가 비대해지므로 기체 단위로만.
    fpl_pack = DEMO_FPL_PACKS.get(sid)
    if fpl_pack:
        entries = _traffic_missions_from_fpl(fpl_pack)
        if not entries:
            return None
        dedup: dict[str, dict[str, Any]] = {}
        for entry in entries:
            name = str(entry.get("aircraftName") or "")
            prev = dedup.get(name)
            if prev is None or str(entry.get("std") or "") < str(prev.get("std") or ""):
                dedup[name] = entry
        return list(dedup.values()) or None
    pack = DEMO_PLAN_PACKS.get(sid)
    if not pack:
        return None
    pack_dir = DEMO_PLANS_DIR / pack
    if not pack_dir.is_dir():
        return None
    entries: list[dict[str, Any]] = []
    for plan_path in sorted(pack_dir.glob("3001_*.json")):
        try:
            rec = json.loads(plan_path.read_text(encoding="utf-8"))
            departure = rec.get("departure") or {}
            arrival = rec.get("arrival") or {}
            std = str(departure.get("std") or "")
            entries.append(
                {
                    "aircraftName": str(rec.get("aircraftId") or ""),
                    "departureName": str(departure.get("vertiport") or ""),
                    "arrivalName": str(arrival.get("vertiport") or ""),
                    "departureTime": std,
                    "std": std,
                    "routeData": {"enRoute": rec.get("enRoute") or []},
                }
            )
        except (OSError, ValueError, AttributeError) as exc:
            logger.warning("Skipping unreadable demo plan %s: %s", plan_path, exc)
    return entries or None


def _traffic_missions_from_fpl(folder_name: str) -> list[dict[str, Any]] | None:
    """Synthesize console-shaped mission entries from FlightScheduler FPL_all.csv.

    The CSV carries no enRoute geometry — routeData stays None and Mission's
    RoutePlanner computes the origin→destination route later.  Vertiport names
    are Korean and match the console map / RoutePlanner network naming.
    """
    name = str(folder_name or "").strip()
    if not name or name != Path(name).name or name in {".", ".."}:
        return None
    csv_path = FPL_FOLDERS_DIR / name / "FPL_all.csv"
    if not csv_path.is_file():
        return None
    entries: list[dict[str, Any]] = []
    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                aircraft = str(row.get("aircraft_id") or "").strip()
                departure = str(row.get("origin_vertiport") or "").strip()
                arrival = str(row.get("destination_vertiport") or "").strip()
                takeoff = str(row.get("takeoff_time") or "").strip()
                if not aircraft or not departure or not arrival:
                    continue
                entries.append(
                    {
                        "aircraftName": aircraft,
                        "departureName": departure,
                        "arrivalName": arrival,
                        "departureTime": takeoff,
                        "std": takeoff,
                        "routeData": None,
                        "fpn": _fpn_from_fpl_id(
                            row.get("fpl_id"),
                            FPL_FPN_FALLBACK_BASE + len(entries),
                        ),
                    }
                )
    except (OSError, csv.Error) as exc:
        logger.warning("Unreadable FPL_all.csv %s: %s", csv_path, exc)
        return None
    # 스폰은 기체 단위 — 같은 기체의 다회 운항(편)을 그대로 두면 편수만큼
    # pawn 이 생성된다 (실측: 68대 셋이 1,623 pawn → UE VRAM OOM).
    # 기체별 최초 출발 편 하나만 남긴다 (비행 자체는 Mission 이 전 편 발행).
    dedup: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = str(entry.get("aircraftName") or "")
        prev = dedup.get(key)
        if prev is None or str(entry.get("std") or "") < str(prev.get("std") or ""):
            dedup[key] = entry
    return list(dedup.values()) or None


def _fpn_from_fpl_id(fpl_id: Any, fallback: int) -> int:
    """FPL0116001 -> 116001; fall back to a sequential number from 1301."""
    match = re.search(r"(\d+)", str(fpl_id or ""))
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return int(fallback)


def _validate_mode_payload(
    mode_payload: dict[str, Any],
    demo_scenario_id: str = "",
) -> tuple[list[dict[str, Any]], str]:
    single_flight = mode_payload.get("singleFlight") or {}
    vehicle_sim_type = single_flight.get("vehicleSimType") or {}

    if demo_scenario_id:
        demo_missions = _demo_missions_from_pack(demo_scenario_id)
        if demo_missions:
            # Demo mode: the console editor is locked, so skip the
            # operationMode/missions payload checks and validate the
            # synthesized plan-pack entries through the same pipeline.
            controller = str(vehicle_sim_type.get("mainVehicleController") or "").strip()
            if controller not in VALID_CONTROLLERS:
                raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
            dynamics = str(vehicle_sim_type.get("dynamics") or DEFAULT_DYNAMICS_MODEL).strip()
            if dynamics not in VALID_DYNAMICS_MODELS:
                raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
            missions: list[dict[str, Any]] = []
            for entry in demo_missions:
                entry_controller = _mission_controller(entry, controller)
                if entry_controller not in VALID_CONTROLLERS:
                    raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
                entry_dynamics = _mission_dynamics(entry, dynamics)
                if entry_dynamics not in VALID_DYNAMICS_MODELS:
                    raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
                prepared_entry = dict(entry)
                prepared_entry["_dtam_controller"] = entry_controller
                prepared_entry["_dtam_dynamics"] = entry_dynamics
                _resolve_settings_start_point(prepared_entry)
                missions.append(prepared_entry)
            return missions, controller
        # Pack missing/misconfigured: fall through to normal validation so the
        # standard incomplete-mission error still surfaces.

    traffic_sim = mode_payload.get("trafficSim") if isinstance(mode_payload.get("trafficSim"), dict) else {}
    custom_mission_folder = str(traffic_sim.get("customMissionFolder") or "").strip()
    if custom_mission_folder:
        # Traffic mode (density "customed"): the console editor carries no
        # missions[]; synthesize entries from the FlightScheduler FPL CSV and
        # validate them through the same per-entry pipeline as demo packs.
        traffic_missions = _traffic_missions_from_fpl(custom_mission_folder)
        if not traffic_missions:
            raise HTTPException(
                status_code=400,
                detail=f"FPL folder '{custom_mission_folder}' has no readable FPL_all.csv flights.",
            )
        # Traffic payloads may lack singleFlight; prefer a top-level
        # vehicleSimType, then the singleFlight one, then Autopilot/simple.
        traffic_sim_type = (
            mode_payload.get("vehicleSimType")
            if isinstance(mode_payload.get("vehicleSimType"), dict)
            else {}
        )
        controller = str(
            traffic_sim_type.get("mainVehicleController")
            or vehicle_sim_type.get("mainVehicleController")
            or "Autopilot"
        ).strip()
        if controller not in VALID_CONTROLLERS:
            raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
        dynamics = str(
            traffic_sim_type.get("dynamics")
            or vehicle_sim_type.get("dynamics")
            or DEFAULT_DYNAMICS_MODEL
        ).strip()
        if dynamics not in VALID_DYNAMICS_MODELS:
            raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
        missions = []
        for entry in traffic_missions:
            entry_controller = _mission_controller(entry, controller)
            if entry_controller not in VALID_CONTROLLERS:
                raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
            entry_dynamics = _mission_dynamics(entry, dynamics)
            if entry_dynamics not in VALID_DYNAMICS_MODELS:
                raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
            prepared_entry = dict(entry)
            prepared_entry["_dtam_controller"] = entry_controller
            prepared_entry["_dtam_dynamics"] = entry_dynamics
            _resolve_settings_start_point(prepared_entry)
            missions.append(prepared_entry)
        return missions, controller

    operation_mode = str(mode_payload.get("operationMode") or "").strip()
    if operation_mode != "single":
        raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)

    controller = str(vehicle_sim_type.get("mainVehicleController") or "").strip()
    if controller not in VALID_CONTROLLERS:
        raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
    dynamics = str(vehicle_sim_type.get("dynamics") or DEFAULT_DYNAMICS_MODEL).strip()
    if dynamics not in VALID_DYNAMICS_MODELS:
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
        entry_controller = _mission_controller(entry, controller)
        if entry_controller not in VALID_CONTROLLERS:
            raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
        entry_dynamics = _mission_dynamics(entry, dynamics)
        if entry_dynamics not in VALID_DYNAMICS_MODELS:
            raise HTTPException(status_code=400, detail=MISSION_INCOMPLETE_MESSAGE)
        prepared_entry = dict(entry)
        prepared_entry["_dtam_controller"] = entry_controller
        prepared_entry["_dtam_dynamics"] = entry_dynamics
        _resolve_settings_start_point(prepared_entry)
        missions.append(prepared_entry)

    return missions, controller


def _mission_controller(entry: dict[str, Any], fallback: str) -> str:
    vehicle_sim_type = entry.get("vehicleSimType") if isinstance(entry.get("vehicleSimType"), dict) else {}
    for value in (
        vehicle_sim_type.get("mainVehicleController"),
        entry.get("controllerOverride"),
        entry.get("mainVehicleController"),
        entry.get("vehicleController"),
        entry.get("controller"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    return fallback


def _mission_dynamics(entry: dict[str, Any], fallback: str = DEFAULT_DYNAMICS_MODEL) -> str:
    vehicle_sim_type = entry.get("vehicleSimType") if isinstance(entry.get("vehicleSimType"), dict) else {}
    for value in (
        entry.get("_dtam_dynamics"),
        vehicle_sim_type.get("dynamics"),
        entry.get("dynamics"),
        entry.get("dynamicsModel"),
        entry.get("vehicleDynamics"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    return fallback or DEFAULT_DYNAMICS_MODEL


def _write_unreal_vehicle_settings(
    missions: list[dict[str, Any]],
    *,
    preserve_existing_spawn: bool = False,
) -> dict[str, Any]:
    settings = _read_json_file(UNREAL_SETTINGS_PATH)
    _sync_airsim_origin_geopoint_to_cesium(settings)
    _apply_unreal_runtime_safety_settings(settings)
    _apply_camera_stream_capture_settings(settings)
    settings_origin = _settings_origin_geopoint(settings)
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
        spawn_alt_m = _settings_spawn_altitude_m(start_point)
        direct_spawn_pose = _direct_airsim_pose_from_point(start_point)
        if direct_spawn_pose is not None:
            north_m, east_m, spawn_down_m = direct_spawn_pose
            _route_down_m = spawn_down_m
        else:
            north_m, east_m, _route_down_m = _wgs84_to_airsim_settings_ned(
                float(start_point["lat"]),
                float(start_point["lon"]),
                _point_altitude_m(start_point),
                settings_origin,
            )
            _spawn_north_m, _spawn_east_m, spawn_down_m = _wgs84_to_airsim_settings_ned(
                float(start_point["lat"]),
                float(start_point["lon"]),
                spawn_alt_m,
                settings_origin,
            )

        mission_dynamics = _mission_dynamics(mission)
        vehicle["VehicleType"] = vehicle.get("VehicleType") or "SimpleFlight"
        vehicle["DTAMDynamicsModel"] = mission_dynamics
        vehicle["DTAMVehicleModel"] = "KP-2A" if mission_dynamics == "highFidelity" else "Simple Dynamics"
        vehicle["AutoCreate"] = True
        vehicle["DefaultVehicleState"] = vehicle.get("DefaultVehicleState") or "Armed"
        existing_vehicle = existing_vehicles.get(vehicle_name)
        if preserve_existing_spawn and isinstance(existing_vehicle, dict):
            # Visualization-compatible launch mode: do not poison the AirSim
            # startup pose that the VisualizationModule Launch button would use.
            # Mission-relative movement is applied later through VehicleModule /
            # 4001, so launch-time X/Y/Z must stay Visualization-owned.
            for key, fallback in (("X", north_m), ("Y", east_m), ("Z", spawn_down_m)):
                current = _as_float(existing_vehicle.get(key))
                vehicle[key] = round(float(current if current is not None else fallback), 3)
        else:
            vehicle["X"] = round(float(north_m), 3)
            vehicle["Y"] = round(float(east_m), 3)
            vehicle["Z"] = _vehicle_spawn_z(
                existing_vehicle,
                first_template,
                computed_down_m=spawn_down_m,
            )

        yaw_deg = _point_yaw_deg(start_point)
        if yaw_deg is None:
            yaw_deg = _initial_route_heading_deg(mission)
        if preserve_existing_spawn and isinstance(existing_vehicle, dict) and _as_float(existing_vehicle.get("Yaw")) is not None:
            vehicle["Yaw"] = round(float(_as_float(existing_vehicle.get("Yaw"))), 3) % 360.0
        elif yaw_deg is not None:
            vehicle["Yaw"] = round(float(yaw_deg) % 360.0, 3)

        vehicles[vehicle_name] = vehicle
        vehicle_map[aircraft_id] = vehicle_name
        vehicle_summary.append({
            "aircraft_id": aircraft_id,
            "vehicle_name": vehicle_name,
            "controller": str(mission.get("_dtam_controller") or "Autopilot"),
            "dynamics": mission_dynamics,
            "vehicle_model": "KP-2A" if mission_dynamics == "highFidelity" else "Simple Dynamics",
            "departure": mission.get("departureName") or "",
            "arrival": mission.get("arrivalName") or "",
            "x": vehicle["X"],
            "y": vehicle["Y"],
            "z": vehicle["Z"],
            "yaw": vehicle.get("Yaw"),
            "lat": float(start_point["lat"]),
            "lon": float(start_point["lon"]),
            "alt_m": _point_altitude_m(start_point),
            "ground_m": _as_float(start_point.get("ground_m")),
            "spawn_alt_m": spawn_alt_m,
            "route_down_m": round(float(_route_down_m), 3),
            "spawn_point_id": start_point.get("spawn_point_id"),
        })

    settings["Vehicles"] = {
        name: vehicles[name]
        for name in sorted(vehicles, key=_drone_sort_key)
    }
    _apply_camera_stream_capture_settings(settings)
    _write_json_file(UNREAL_SETTINGS_PATH, settings)
    _write_json_file(DOCUMENTS_AIRSIM_SETTINGS_PATH, settings)
    _write_json_file(PACKAGED_LAUNCH_SETTINGS_PATH, settings)
    _write_vm_vehicle_map(vehicle_map)

    return {
        "vehicles": vehicle_summary,
        "vehicle_map": vehicle_map,
    }


def _apply_unreal_runtime_safety_settings(settings: dict[str, Any]) -> None:
    # Cosys/AirSim initializes the full-scene instance-segmentation annotator by
    # default.  In the packaged DTAMVisualization build this can touch skeletal
    # mesh/Nanite render proxies during startup and crash before the AirSim RPC
    # server opens.  DTAM runtime only needs scene camera frames, so keep the
    # expensive annotation path disabled for Operation Console launches.
    settings["EnableRpc"] = True
    settings["RpcEnabled"] = True
    settings["InitialInstanceSegmentation"] = False
    settings.setdefault("Annotation", [])


def _apply_camera_stream_capture_settings(settings: dict[str, Any]) -> None:
    """Keep the direct AirSim camera stream at a real-time friendly resolution.

    OperationModule regenerates AirSim settings on every DTAM execution and
    writes them to the Unreal runtime, packaged launch folder, and
    Documents/AirSim.  Applying this here prevents manual Documents edits from
    being overwritten back to heavy 1280x720 values.
    """
    vehicles = settings.get("Vehicles")
    if not isinstance(vehicles, dict):
        return

    # 캡처 카메라(렌더 타겟)는 VRAM 상주 자원 — 기체마다 붙이면 다수 기체
    # 스폰 시 GPU 메모리가 바닥난다 (실측: 1,623대 × 카메라 → UE OOM/행).
    # 스트림 뷰(4101)는 한 번에 한 대만 보므로 대표 기체 1대에만 부착한다.
    primary_name = None
    for name in sorted(vehicles, key=_drone_sort_key):
        if isinstance(vehicles.get(name), dict):
            primary_name = name
            break

    for name, vehicle in vehicles.items():
        if not isinstance(vehicle, dict):
            continue
        if name != primary_name:
            existing_cameras = vehicle.get("Cameras")
            if isinstance(existing_cameras, dict):
                existing_cameras.pop(STREAM_CAMERA_NAME, None)
                if not existing_cameras:
                    vehicle.pop("Cameras", None)
            continue
        cameras = vehicle.get("Cameras")
        if not isinstance(cameras, dict):
            cameras = {}
            vehicle["Cameras"] = cameras
        camera = cameras.get(STREAM_CAMERA_NAME)
        if not isinstance(camera, dict):
            camera = {
                "X": 0.4,
                "Y": 0.0,
                "Z": -0.1,
                "Pitch": 0,
                "Roll": 0,
                "Yaw": 0,
                "Label": "Front",
            }
            cameras[STREAM_CAMERA_NAME] = camera

        capture_settings = camera.get("CaptureSettings")
        if not isinstance(capture_settings, list):
            capture_settings = []
            camera["CaptureSettings"] = capture_settings

        scene_setting = None
        for item in capture_settings:
            if isinstance(item, dict) and int(item.get("ImageType", STREAM_CAMERA_IMAGE_TYPE)) == STREAM_CAMERA_IMAGE_TYPE:
                scene_setting = item
                break
        if scene_setting is None:
            scene_setting = {"ImageType": STREAM_CAMERA_IMAGE_TYPE}
            capture_settings.append(scene_setting)

        scene_setting["ImageType"] = STREAM_CAMERA_IMAGE_TYPE
        scene_setting["Width"] = STREAM_CAMERA_WIDTH
        scene_setting["Height"] = STREAM_CAMERA_HEIGHT
        scene_setting.setdefault("FOV_Degrees", STREAM_CAMERA_FOV_DEG)


def _write_vm_vehicle_map(vehicle_map: dict[str, str]) -> None:
    config = _read_json_file(VM_CONFIG_PATH)
    airsim = config.get("airsim")
    if not isinstance(airsim, dict):
        airsim = {}
        config["airsim"] = airsim
    airsim["vehicle_map"] = {
        key: vehicle_map[key]
        for key in sorted(vehicle_map)
    }
    _write_json_file(VM_CONFIG_PATH, config)


def _is_unreal_map_arg(arg: str) -> bool:
    text = str(arg or "").strip()
    if not text or text.startswith("-"):
        return False
    normalized = text.replace("\\", "/").lower()
    return (
        normalized.startswith("/airsim/")
        or normalized.startswith("/game/")
        or normalized.startswith("/dtamvisualization/")
        or normalized.endswith(".umap")
    )


def _drone_sort_key(name: str) -> tuple[int, str]:
    match = re.search(r"(\d+)$", str(name or ""))
    return (int(match.group(1)) if match else 999999, str(name or ""))


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
            "dynamics": str(vehicle.get("dynamics") or mission.get("_dtam_dynamics") or DEFAULT_DYNAMICS_MODEL),
            "vehicle_model": str(vehicle.get("vehicle_model") or ("KP-2A" if str(vehicle.get("dynamics") or mission.get("_dtam_dynamics") or DEFAULT_DYNAMICS_MODEL) == "highFidelity" else "Simple Dynamics")),
            "coordinate_frame": "odt_unreal_visual_spawn_relative",
            "spawn_pose": {
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
            # DT World's visual KP2A/Cesium scene is not laid out in pure
            # geographic N/E axes.  Its AirSim pose frame follows the legacy
            # ODT Unreal axes: X=east, Y=south(-north), Z=down.  The GPS/LLA
            # fields remain authoritative for Operation's 2D map, but Unreal
            # guide lines must use this visual pose frame.
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
            geo = offset.get("local_ned_m", {})
            point["geographic_local_ned_m"] = {
                "north": round(float(geo.get("north", 0.0)), 3),
                "east": round(float(geo.get("east", 0.0)), 3),
                "down": round(float(geo.get("down", 0.0)), 3),
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
    ground_m = _as_float(raw_point.get("ground_m"))
    if ground_m is not None:
        point["ground_m"] = round(float(ground_m), 3)
    point_type = raw_point.get("type") or raw_point.get("waypoint_type")
    if point_type not in (None, ""):
        point["type"] = str(point_type)
    spawn_point_id = raw_point.get("spawn_point_id") or raw_point.get("spawnPointId")
    if spawn_point_id not in (None, ""):
        point["spawn_point_id"] = str(spawn_point_id)
    yaw_deg = _point_yaw_deg(raw_point)
    if yaw_deg is not None:
        point["yaw_deg"] = round(float(yaw_deg), 3)
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
    controller_by_aircraft: dict[str, str],
    dynamics_by_aircraft: dict[str, str] | None = None,
    provider_by_aircraft: dict[str, str] | None = None,
    vehicle_spawns: dict[str, dict[str, Any]] | None = None,
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

    default_mode = CONTROL_MODE_BY_CONTROLLER[controller]
    vehicle_modes = {
        aircraft_id: CONTROL_MODE_BY_CONTROLLER.get(str(vehicle_controller), default_mode)
        for aircraft_id, vehicle_controller in controller_by_aircraft.items()
    }
    dynamics_by_aircraft = dict(dynamics_by_aircraft or {})
    provider_by_aircraft = dict(provider_by_aircraft or {})
    applied = _request_json(
        f"{airmobility_url}/api/control/modes",
        method="POST",
        body={
            "defaultMode": default_mode,
            "vehicleModes": vehicle_modes,
            "dynamicsByAircraft": dynamics_by_aircraft,
            "providerByAircraft": provider_by_aircraft,
        },
        timeout_s=5.0,
    )

    # Manual-mode vehicles must all be initialized from their own mission start.
    # The keyboard/joystick capture endpoints configure the primary capture
    # target, but common Keyboard/Joystick mode can apply to multiple aircraft at
    # once. Configure every manual vehicle here so inherited common control does
    # not leave non-primary aircraft at AirSim's default OriginGeopoint.
    vehicle_spawns = vehicle_spawns or {}
    manual_configs: dict[str, Any] = {}
    for aircraft_id, mode in vehicle_modes.items():
        if mode == CONTROL_MODE_BY_CONTROLLER["Autopilot"]:
            continue
        manual_configs[aircraft_id] = _request_json(
            f"{airmobility_url}/api/control/manual/config",
            method="POST",
            body=_manual_control_request_body(
                aircraft_id=aircraft_id,
                vehicle_map=vehicle_map,
                vehicle_spawns=vehicle_spawns,
            ),
            timeout_s=8.0,
        )

    capture_results: dict[str, Any] = {}
    for controller_name, endpoint in (("Keyboard", "keyboard"), ("Joystick", "joystick")):
        target_aircraft_id = next(
            (
                aircraft_id
                for aircraft_id, vehicle_controller in controller_by_aircraft.items()
                if str(vehicle_controller) == controller_name
            ),
            "",
        )
        if not target_aircraft_id:
            continue
        capture_results[endpoint] = _request_json(
            f"{airmobility_url}/api/control/{endpoint}/start",
            method="POST",
            body=_manual_control_request_body(
                aircraft_id=target_aircraft_id,
                vehicle_map=vehicle_map,
                vehicle_spawns=vehicle_spawns,
            ),
            timeout_s=8.0,
        )

    # The OperationModule DT World flow stops VehicleModule first to clear stale
    # keyboard/joystick capture state.  Without starting it again here, the
    # subsequent 2002/1002 ICD messages can be sent successfully while the
    # VehicleModule sender/subscriber loop is still stopped.  That made missions
    # launched from OperationModule appear "armed" but not actually move, even
    # though direct VehicleModule execution worked.
    service_start = _request_json(
        f"{airmobility_url}/api/service/start",
        method="POST",
        body={},
        timeout_s=8.0,
    )

    return {
        "ok": True,
        "defaultMode": default_mode,
        "vehicleModes": vehicle_modes,
        "dynamicsByAircraft": dynamics_by_aircraft,
        "providerByAircraft": provider_by_aircraft,
        "applied": applied,
        "manualConfigs": manual_configs,
        "captures": capture_results,
        "serviceStart": service_start,
    }


def _controller_by_aircraft(vehicles: list[dict[str, Any]], controller: str) -> dict[str, str]:
    return {
        str(vehicle["aircraft_id"]): str(vehicle.get("controller") or controller)
        for vehicle in vehicles
        if isinstance(vehicle, dict) and str(vehicle.get("aircraft_id") or "").strip()
    }


def _dynamics_by_aircraft(vehicles: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(vehicle["aircraft_id"]): str(vehicle.get("dynamics") or DEFAULT_DYNAMICS_MODEL)
        for vehicle in vehicles
        if isinstance(vehicle, dict) and str(vehicle.get("aircraft_id") or "").strip()
    }


def _provider_by_aircraft(vehicles: list[dict[str, Any]]) -> dict[str, str]:
    providers: dict[str, str] = {}
    for vehicle in vehicles:
        if not isinstance(vehicle, dict):
            continue
        aircraft_id = str(vehicle.get("aircraft_id") or "").strip()
        if not aircraft_id:
            continue
        dynamics = str(vehicle.get("dynamics") or DEFAULT_DYNAMICS_MODEL).strip()
        providers[aircraft_id] = "vfds-kp2a" if dynamics == "highFidelity" else "simple"
    return providers


def _validate_dynamics_controller_pairs(
    controller_by_aircraft: dict[str, str],
    dynamics_by_aircraft: dict[str, str],
) -> None:
    invalid: list[str] = []
    for aircraft_id, dynamics in dynamics_by_aircraft.items():
        if str(dynamics or "").strip() != "highFidelity":
            continue
        controller = str(controller_by_aircraft.get(aircraft_id) or "Autopilot").strip()
        if CONTROL_MODE_BY_CONTROLLER.get(controller) != CONTROL_MODE_BY_CONTROLLER["Autopilot"]:
            invalid.append(f"{aircraft_id}:{controller}")
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=(
                "highFidelity dynamics currently supports Autopilot only "
                f"({', '.join(invalid)})"
            ),
        )


def _apply_airmobility_control_modes_only(
    *,
    airmobility_url: str,
    controller: str,
    vehicle_map: dict[str, str],
    controller_by_aircraft: dict[str, str],
    dynamics_by_aircraft: dict[str, str] | None = None,
    provider_by_aircraft: dict[str, str] | None = None,
    vehicle_spawns: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    default_mode = CONTROL_MODE_BY_CONTROLLER[controller]
    vehicle_modes = {
        aircraft_id: CONTROL_MODE_BY_CONTROLLER.get(str(vehicle_controller), default_mode)
        for aircraft_id, vehicle_controller in controller_by_aircraft.items()
    }
    dynamics_by_aircraft = dict(dynamics_by_aircraft or {})
    provider_by_aircraft = dict(provider_by_aircraft or {})
    applied = _request_json(
        f"{airmobility_url}/api/control/modes",
        method="POST",
        body={
            "defaultMode": default_mode,
            "vehicleModes": vehicle_modes,
            "dynamicsByAircraft": dynamics_by_aircraft,
            "providerByAircraft": provider_by_aircraft,
        },
        timeout_s=5.0,
    )

    vehicle_spawns = vehicle_spawns or {}
    manual_configs: dict[str, Any] = {}
    for aircraft_id, mode in vehicle_modes.items():
        if mode == CONTROL_MODE_BY_CONTROLLER["Autopilot"]:
            continue
        manual_configs[aircraft_id] = _request_json(
            f"{airmobility_url}/api/control/manual/config",
            method="POST",
            body=_manual_control_request_body(
                aircraft_id=aircraft_id,
                vehicle_map=vehicle_map,
                vehicle_spawns=vehicle_spawns,
            ),
            timeout_s=8.0,
        )

    return {
        "ok": True,
        "defaultMode": default_mode,
        "vehicleModes": vehicle_modes,
        "dynamicsByAircraft": dynamics_by_aircraft,
        "providerByAircraft": provider_by_aircraft,
        "applied": applied,
        "manualConfigs": manual_configs,
        "captures": {},
        "captureDeferred": True,
    }


def _manual_vehicle_spawn_configs(vehicles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return per-aircraft manual-control origins from prepared mission starts.

    Important AirSim behavior: ``simSetVehiclePose`` is applied in the vehicle's
    own spawn-relative replay frame.  Autopilot already publishes pose values as
    mission-start relative NED (0,0,0 at the spawned aircraft). Keyboard/Joystick
    must use the same frame.  If we put the AirSim settings spawn X/Y into the
    manual initial pose, AirSim adds the spawn offset again and the aircraft
    appears roughly twice as far from the map origin.

    Therefore manual ``position`` starts at local 0/0/0, while GPS/Operation-map
    telemetry is anchored at the mission departure LLA.  The settings spawn X/Y/Z
    remain in Unreal settings only.
    """
    out: dict[str, dict[str, Any]] = {}
    for vehicle in vehicles or []:
        if not isinstance(vehicle, dict):
            continue
        aircraft_id = str(vehicle.get("aircraft_id") or "").strip()
        if not aircraft_id:
            continue
        lat = _as_float(vehicle.get("lat"))
        lon = _as_float(vehicle.get("lon"))
        alt_m = _as_float(vehicle.get("alt_m"))
        if lat is None or lon is None:
            continue
        spawn: dict[str, Any] = {
            "origin_lat": float(lat),
            "origin_lon": float(lon),
            "initial_north_m": 0.0,
            "initial_east_m": 0.0,
            "initial_down_m": 0.0,
            "gps_origin_lat": float(lat),
            "gps_origin_lon": float(lon),
            "gps_reference_north_m": 0.0,
            "gps_reference_east_m": 0.0,
            "gps_reference_down_m": 0.0,
        }
        if alt_m is not None:
            spawn["origin_alt_m"] = float(alt_m)
            spawn["gps_origin_alt_m"] = float(alt_m)
        yaw = _as_float(vehicle.get("yaw"))
        if yaw is not None:
            spawn["initial_heading_deg"] = float(yaw) % 360.0
        out[aircraft_id] = spawn
    return out


def _manual_control_request_body(
    *,
    aircraft_id: str,
    vehicle_map: dict[str, str],
    vehicle_spawns: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "vehicle_id": aircraft_id,
        "airsim_vehicle_name": vehicle_map.get(aircraft_id, ""),
        # OperationModule already passes the mission-derived spawn/origin data.
        # Manual config should therefore be a fast local VehicleModule setup
        # step; strict AirSim/Visualization synchronization is handled by the
        # keyboard/joystick capture start endpoints.
        "sync_visualization": False,
    }
    spawn = vehicle_spawns.get(aircraft_id)
    if isinstance(spawn, dict):
        body.update(spawn)
    return body


def _wait_for_airsim_connection(visualization_url: str, *, timeout_s: float) -> dict[str, Any]:
    deadline = time.time() + max(timeout_s, 1.0)
    last_status: dict[str, Any] = {}
    started_at = time.time()
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

        # Do not leave the DT World button spinning for the full AirSim timeout
        # if the packaged Unreal process already exited.  The Visualization API
        # owns the Popen handle and exposes its status through /api/state.
        if time.time() - started_at >= 3.0:
            try:
                vm_state = _request_visualization_status(visualization_url, timeout_s=3.0)
                unreal = vm_state.get("unreal") if isinstance(vm_state.get("unreal"), dict) else {}
                if unreal:
                    exit_code = unreal.get("exit_code")
                    running = bool(unreal.get("running"))
                    if exit_code is not None or not running:
                        log_path = unreal.get("log_path") or "D:\\DTAMFramework\\.dtam_runtime\\logs\\visualization_unreal.log"
                        raise HTTPException(
                            status_code=502,
                            detail=(
                                f"Unreal process is not running after launch"
                                f"{f' (exit_code={exit_code})' if exit_code is not None else ''}. "
                                f"See log: {log_path}"
                            ),
                        )
            except HTTPException as exc:
                if exc.status_code == 502:
                    raise
                last_status = {"error": exc.detail}
        time.sleep(1.0)

    reason = last_status.get("last_error") or last_status.get("error") or "AirSim connection timeout"
    raise HTTPException(status_code=504, detail=f"Unreal is running, but the AirSim connection did not complete. {reason}")


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


def _is_visualization_backend_ready() -> bool:
    try:
        _request_visualization_status(VISUALIZATION_BACKEND_URL, timeout_s=3.0)
        return True
    except HTTPException:
        return False


def _request_visualization_status(visualization_url: str, *, timeout_s: float) -> dict[str, Any]:
    """Fetch VisualizationModule runtime status without the heavy GUI event log."""
    base_url = visualization_url.rstrip("/")
    try:
        return _request_json(f"{base_url}/api/health", timeout_s=timeout_s)
    except HTTPException as exc:
        # Older VM processes do not have /api/health yet.  Keep a compatibility
        # fallback, but do not mask real timeout/connectivity failures because
        # /api/state can be much heavier during live telemetry.
        if "Not Found" not in str(exc.detail):
            raise
    return _request_json(f"{base_url}/api/state", timeout_s=max(timeout_s, 1.5))


def _request_airmobility_status(airmobility_url: str, *, timeout_s: float) -> dict[str, Any]:
    base_url = airmobility_url.rstrip("/")
    try:
        status = _request_json(f"{base_url}/api/health", timeout_s=timeout_s)
    except HTTPException:
        try:
            status = _request_json(f"{base_url}/api/status", timeout_s=max(timeout_s, 1.5))
        except HTTPException as exc:
            return {"ok": False, "error": str(exc.detail)}
    return _compact_airmobility_status(status)


def _compact_airmobility_status(status: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(status, dict):
        return {"ok": False, "error": "invalid VehicleModule status"}
    return {
        "ok": bool(status.get("ok", True)),
        "running": bool(status.get("running")),
        "play_state": status.get("play_state"),
        "rx_3001_count": int(status.get("rx_3001_count") or 0),
        "rx_2002_count": int(status.get("rx_2002_count") or 0),
        "rx_0003_count": int(status.get("rx_0003_count") or 0),
        "last_rx_3001": str(status.get("last_rx_3001") or ""),
        "last_rx_2002": str(status.get("last_rx_2002") or ""),
        "last_rx_0003": str(status.get("last_rx_0003") or ""),
        "vehicle_dynamics": status.get("vehicle_dynamics") if isinstance(status.get("vehicle_dynamics"), dict) else {},
        "vehicle_providers": status.get("vehicle_providers") if isinstance(status.get("vehicle_providers"), dict) else {},
        "provider_statuses": status.get("provider_statuses") if isinstance(status.get("provider_statuses"), dict) else {},
        "vehicles": status.get("vehicles") if isinstance(status.get("vehicles"), list) else [],
    }


def _high_fidelity_aircraft_from_missions(
    missions: list[dict[str, Any]],
    fallback_dynamics: str = DEFAULT_DYNAMICS_MODEL,
) -> dict[str, str]:
    selected: dict[str, str] = {}
    used: set[str] = set()
    for index, mission in enumerate(missions, start=1):
        if _mission_dynamics(mission, fallback_dynamics) != "highFidelity":
            continue
        aircraft_id = _aircraft_id_from_mission(mission, index, used)
        used.add(aircraft_id)
        selected[aircraft_id] = "highFidelity"
    return selected


def _ensure_vfds_runtime_for_mapping(
    airmobility_url: str,
    dynamics_by_aircraft: dict[str, str] | None,
) -> dict[str, Any]:
    high_fidelity_aircraft = sorted(
        aircraft_id
        for aircraft_id, dynamics in dict(dynamics_by_aircraft or {}).items()
        if str(dynamics or "").strip() == "highFidelity"
    )
    if not high_fidelity_aircraft:
        return {
            "ok": True,
            "skipped": True,
            "reason": "no highFidelity vehicle",
            "aircraft": [],
        }
    result = _request_json(
        f"{airmobility_url.rstrip('/')}/api/vfds/ensure",
        method="POST",
        body={"timeout_s": 20.0, "aircraft": high_fidelity_aircraft},
        timeout_s=25.0,
    )
    result["aircraft"] = high_fidelity_aircraft
    if not bool(result.get("ok")):
        detail = result.get("runtime", {}).get("error") if isinstance(result.get("runtime"), dict) else ""
        raise HTTPException(status_code=502, detail=detail or "VFDS/KP2A runtime is not ready")
    return result


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


def _direct_airsim_pose_from_point(point: dict[str, Any]) -> tuple[float, float, float] | None:
    x_m = _as_float(point.get("airsim_x_m") or point.get("X_m") or point.get("x_m"))
    y_m = _as_float(point.get("airsim_y_m") or point.get("Y_m") or point.get("y_m"))
    z_m = _as_float(
        point.get("airsim_spawn_z_m")
        or point.get("settings_z_m")
        or point.get("calibrated_z_m")
    )
    if z_m is None:
        z_m = _airsim_spawn_surface_z(point)
    if z_m is None:
        z_m = _as_float(point.get("airsim_z_m") or point.get("Z_m") or point.get("z_m"))
    if x_m is None or y_m is None or z_m is None:
        return None
    return float(x_m), float(y_m), float(z_m)


def _airsim_spawn_surface_z(point: dict[str, Any]) -> float | None:
    # Prefer the actual geodetic pad/FATO height when coordinateDB provides it.
    # The KP2A AirSim NED origin is the Unreal/Cesium origin, whose geodetic
    # height is ~350 m in the current DT World.  Positive NED D is down, so a
    # Jamsil pad at ~33.7 m MSL should spawn around D=315 m, not around D=18 m
    # from the older CityHall DB-Z fit.
    #
    # coordinateDB resources_vp.csv also carries the local FATO deck height
    # (Z_m).  Add that to the terrain/geodetic height before converting to NED
    # down.  Because AirSim D is positive downward, this makes the final Z value
    # smaller by the FATO height and places the aircraft on top of the pad.
    surface_h_m = _as_float(
        point.get("airsim_surface_h_m")
        or point.get("terrain_h_m")
        or point.get("pt_h_m")
        or point.get("surface_h_m")
    )
    if surface_h_m is not None:
        fato_height_m = _as_float(
            point.get("fato_height_m")
            or point.get("deck_height_m")
            or point.get("local_z_m")
        )
        if fato_height_m is not None and fato_height_m > 0.0:
            surface_h_m += float(fato_height_m)
        return (
            float(_dtam_cesium_origin_height_m())
            - float(surface_h_m)
            - float(AIRSIM_FATO_SPAWN_CLEARANCE_M)
        )

    lat = _as_float(point.get("lat"))
    lon = _as_float(point.get("lon"))
    if lat is None or lon is None:
        return None
    try:
        _x, _y, surface_down_m = wgs84_to_airsim_ned(float(lat), float(lon), 0.0)
    except Exception:
        return None
    # In NED, subtracting clearance moves the spawn upward.
    return float(surface_down_m) - float(AIRSIM_FATO_SPAWN_CLEARANCE_M)


def _lookup_vertiport_resource_point(
    vertiport_name: str,
    category: str,
    *,
    preferred_label: str,
) -> dict[str, Any] | None:
    name = str(vertiport_name or "").strip()
    if not name:
        return None
    aliases = {
        "여의도": "영등포",
    }
    names = [name]
    alias = aliases.get(name)
    if alias:
        names.append(alias)
    category_key = str(category or "").strip().upper()
    label_key = str(preferred_label or "").strip().upper()
    path = MP_DATA_DIR / "resources_vp.csv"
    if not path.exists():
        return None

    rows: list[dict[str, Any]] = []
    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                rows = list(csv.DictReader(handle))
            break
        except UnicodeDecodeError:
            continue
        except OSError:
            return None

    fallback: dict[str, Any] | None = None
    for row in rows:
        if str(row.get("Vertiport") or "").strip() not in names:
            continue
        if str(row.get("Category") or "").strip().upper() != category_key:
            continue
        point = _resource_row_to_start_point(row)
        if point is None:
            continue
        if fallback is None:
            fallback = point
        if str(row.get("Label") or "").strip().upper() == label_key:
            return point
    return fallback


def _resource_row_to_start_point(row: dict[str, Any]) -> dict[str, Any] | None:
    lat = _as_float(row.get("pt_lat_deg"))
    lon = _as_float(row.get("pt_lon_deg"))
    if lat is None or lon is None:
        return None
    label = str(row.get("Label") or "FATO").strip() or "FATO"
    ground_m = _as_float(row.get("Z_m"))
    pt_h_m = _as_float(row.get("pt_h_m"))
    yaw_deg = _as_float(row.get("Yaw_deg"))
    return {
        "name": f"{str(row.get('Vertiport') or '').strip()} {label}".strip(),
        "lat": float(lat),
        "lon": float(lon),
        # route alt stays a small clearance above the visual pad surface.
        # settings spawn Z is computed from terrain_h_m against the Cesium
        # origin height; CSV Z_m is kept only as a DB/visual reference.
        "alt_m": float((ground_m if ground_m is not None else pt_h_m or 0.0) + VERTIPORT_SURFACE_CLEARANCE_M),
        "ground_m": float(ground_m if ground_m is not None else pt_h_m or 0.0),
        "terrain_h_m": float(pt_h_m) if pt_h_m is not None else None,
        "fato_height_m": float(ground_m) if ground_m is not None else 0.0,
        "yaw_deg": float(yaw_deg) % 360.0 if yaw_deg is not None else None,
        "spawn_point_id": label,
        "airsim_x_m": _as_float(row.get("X_m")),
        "airsim_y_m": _as_float(row.get("Y_m")),
        "airsim_z_m": _as_float(row.get("Z_m")),
    }


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
    try:
        fallback_point = _extract_start_point(mission)
    except HTTPException:
        # Traffic/FPL missions carry no routeData geometry yet (Mission's
        # RoutePlanner computes it later).  Fall through to the vertiport-name
        # spawn resolution below instead of failing on the missing route.
        if not departure:
            raise
        fallback_point = {}
    explicit_alt_m = _point_altitude_m(fallback_point) if _is_geo_point(fallback_point) else None
    spawn_id = str(fallback_point.get("spawn_point_id") or fallback_point.get("spawnPointId") or "").strip().upper()
    # Prefer the calibrated Unreal Editor preview marker mapping over the older
    # coordinateDB resource fit.  This keeps Operation-generated settings.json
    # aligned with the visible Gate/FATO S-point markers in the Unreal editor.
    resource_label = "FATO 2"
    if spawn_id in {"S26", "FATO 1", "F1"}:
        resource_label = "FATO 1"
    elif spawn_id and spawn_id not in {"S25", "FATO 2", "F2"}:
        resource_label = spawn_id
    unreal_point = lookup_unreal_spawn_point(
        departure,
        category="FATO",
        preferred_label=resource_label,
        spawn_point_id=spawn_id or None,
    )
    if unreal_point is not None:
        return unreal_point

    resource_point = _lookup_vertiport_resource_point(departure, "FATO", preferred_label=resource_label)
    if resource_point is not None:
        return resource_point

    # AirSim startup must spawn on the pad surface.  Mission routes often set
    # the first departure_takeoff LLA altitude to a clearance height above the
    # pad (currently +10 m).  Do not use that clearance as the settings.json
    # spawn altitude, otherwise the aircraft appears floating before Play.
    fallback_ground_m = _as_float(fallback_point.get("ground_m"))
    if (
        explicit_alt_m is not None
        and spawn_id == "S25"
        and fallback_ground_m is not None
        and float(explicit_alt_m) <= 0.01
    ):
        return fallback_point

    if port is not None:
        ground_m = _route_ground_m(route_data)
        fallback_alt_m = explicit_alt_m
        if ground_m is None:
            ground_m = _as_float(fallback_point.get("ground_m"))
        if ground_m is None:
            ground_m = 0.0
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
                "local_z_m": _as_float(spawn.get("local_z_m")),
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

    for segment in route_data.get("enRoute") or route_data.get("en_route") or []:
        if not isinstance(segment, dict):
            continue
        for key in ("startLLA", "start_lla", "start", "endLLA", "end_lla", "end"):
            point = segment.get(key)
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
        for segment in route_data.get("enRoute") or route_data.get("en_route") or []:
            if not isinstance(segment, dict):
                continue
            for key in ("startLLA", "start_lla", "start", "endLLA", "end_lla", "end"):
                point = segment.get(key)
                if _is_geo_point(point):
                    points.append(point)
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


def _settings_origin_geopoint(settings: dict[str, Any]) -> tuple[float, float, float]:
    origin = settings.get("OriginGeopoint")
    if not isinstance(origin, dict):
        origin = {}
    lat = _as_float(origin.get("Latitude"))
    lon = _as_float(origin.get("Longitude"))
    alt = _as_float(origin.get("Altitude"))
    return (
        float(lat) if lat is not None else 37.5665,
        float(lon) if lon is not None else 126.978,
        float(alt) if alt is not None else 0.0,
    )


def _sync_airsim_origin_geopoint_to_cesium(settings: dict[str, Any]) -> None:
    """Keep AirSim's GPS origin altitude aligned with DT World's visual origin.

    AirSim spawn X/Y/Z is measured from the global NED transform selected in
    ``SimModeBase``.  In the KP2A map that transform is the existing pawn at
    Unreal (0,0,0); the Cesium bootstrap interprets the same Unreal origin as
    ``DTAMVisualizationCesiumSettings.OriginHeight``.  If settings.json keeps an
    old lower OriginGeopoint altitude, the generated visual spawn Z is off by
    roughly 250~300 m and AirSim GPS altitude becomes inconsistent too.
    """

    if not isinstance(settings, dict):
        return
    origin = settings.get("OriginGeopoint")
    if not isinstance(origin, dict):
        origin = {}
        settings["OriginGeopoint"] = origin
    if _as_float(origin.get("Latitude")) is None:
        origin["Latitude"] = 37.5665
    if _as_float(origin.get("Longitude")) is None:
        origin["Longitude"] = 126.978
    origin["Altitude"] = round(_dtam_cesium_origin_height_m(), 3)


def _dtam_cesium_origin_height_m() -> float:
    """Return DT World's Cesium georeference origin height.

    The value is normally the C++ default in
    ``DTAMVisualizationCesiumSettings.h``.  If a project config overrides it,
    honor that without requiring OperationModule changes.
    """

    candidates = (
        UNREAL_PROJECT_PATH.parent / "Config" / "DefaultGame.ini",
        FRAMEWORK_ROOT
        / "VisualizationModule_Source"
        / "Unreal"
        / "Environments"
        / "DTAMVisualization"
        / "Config"
        / "DefaultGame.ini",
        UNREAL_PROJECT_PATH.parent / "Saved" / "Config" / "WindowsEditor" / "Game.ini",
    )
    pattern = re.compile(r"^\s*OriginHeight\s*=\s*([-+]?\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
    for path in candidates:
        try:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                match = pattern.match(line)
                if match:
                    return float(match.group(1))
        except Exception:
            continue
    return float(DEFAULT_CESIUM_ORIGIN_HEIGHT_M)


def _wgs84_to_airsim_settings_ned(
    lat: float,
    lon: float,
    alt_m: float,
    origin: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Convert WGS84 into the DT World AirSim/Unreal spawn frame.

    Despite the NED naming in AirSim's API, the packaged KP2A map/vertiport
    meshes are laid out in the ODT Unreal frame fitted by
    ``MissionModule.app.domain.coord_transform.wgs84_to_airsim_ned``:
    X ~= east, Y ~= south(-north), Z = AirSim down.  If we write pure
    geographic N/E/D here, Jamsil's vertiport marker is still correct in the
    2D Operation map, but the Unreal aircraft spawns several kilometres away
    from the visual pad.
    """

    del origin  # The ODT affine mapper is already city-hall/GCP anchored.
    north_m, east_m, down_m = wgs84_to_airsim_ned(lat, lon, alt_m)
    return float(north_m), float(east_m), float(down_m)


def _settings_spawn_altitude_m(point: dict[str, Any]) -> float:
    ground_m = _as_float(point.get("ground_m"))
    alt_m = _as_float(point.get("alt_m"))
    point_type = str(point.get("type") or point.get("waypoint_type") or "").strip().lower()
    spawn_id = str(point.get("spawn_point_id") or point.get("spawnPointId") or "").strip().upper()
    name = str(point.get("name") or "").strip().upper()
    is_surface_spawn = (
        "departure_takeoff" in point_type
        or "arrival_touchdown" in point_type
        or "takeoff" in point_type
        or "touchdown" in point_type
        or spawn_id
        or " S25" in f" {name}"
        or "FATO" in name
    )

    local_z_m = _as_float(point.get("local_z_m"))
    if ground_m is not None and is_surface_spawn:
        # Generated ODT pad points carry local_z_m (pad deck height above the
        # vertiport base).  Raw route points often only carry ground_m and an
        # alt_m that is already a takeoff-clearance target; in that case use
        # ground_m so the aircraft starts on the pad, not in the air.
        return float(ground_m) + (float(local_z_m) if local_z_m is not None else 0.0)

    if ground_m is not None and (ground_m > 0.01 or alt_m is None or alt_m <= 0.01):
        return float(ground_m)

    if alt_m is not None:
        return float(alt_m)

    return _point_altitude_m(point)


def _point_yaw_deg(point: dict[str, Any]) -> float | None:
    for key in ("yaw_deg", "Yaw_deg", "yaw", "Yaw", "heading_deg", "heading"):
        value = _as_float(point.get(key))
        if value is not None:
            return float(value) % 360.0
    return None


def _vehicle_spawn_z(
    vehicle_template: Any,
    fallback_template: dict[str, Any],
    *,
    computed_down_m: float | None = None,
) -> float:
    for template in (vehicle_template, fallback_template):
        if not isinstance(template, dict):
            continue
        for key in AIRSIM_SPAWN_Z_OVERRIDE_KEYS:
            value = _as_float(template.get(key))
            if value is not None:
                return float(value)
    if computed_down_m is not None:
        return round(float(computed_down_m), 3)
    return AIRSIM_VEHICLE_GROUND_SPAWN_Z_M


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
        "Z": AIRSIM_VEHICLE_GROUND_SPAWN_Z_M,
        "Yaw": 0.0,
    }


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
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


def _bool_payload_value(*values: Any) -> bool:
    for value in values:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"1", "true", "yes", "y", "on"}:
                return True
            if text in {"0", "false", "no", "n", "off"}:
                return False
    return False


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
