"""FastAPI app factory — VehicleModule dashboard."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from dtam_client.schema import parse_payload

from .services.global_joystick_capture import GlobalJoystickCapture
from .services.global_keyboard_capture import GlobalKeyboardCapture
from .services.integrated_service import ClockMode, ControlMode, IntegratedAirMobilityService

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent


def _first_existing(default: Path, *fallbacks: Path) -> Path:
    for path in (default, *fallbacks):
        if path.exists():
            return path
    return default


WEB_DIR = _first_existing(APP_DIR / "web", ROOT / "web")
STATIC_DIR = WEB_DIR
TEMPLATE_DIR = WEB_DIR
DEFAULT_VISUALIZATION_URL = "http://127.0.0.1:8097"
VISUALIZATION_URL_ENV = "DTAM_VISUALIZATION_URL"
DEFAULT_VISUALIZATION_CAMERA_NAME = "front_center"
HAT_CAMERA_YAW_STEP_DEG = 6.0
HAT_CAMERA_ZOOM_STEP = 4.0
VIEW_CATALOG_CACHE_TTL_S = 0.35
VIEW_CATALOG_STALE_TTL_S = 3.0
VIEW_CATALOG_TIMEOUT_S = 0.08


class VisualizationSyncError(RuntimeError):
    pass


def _iso_ts() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _status_to_dict(
    service: IntegratedAirMobilityService,
    keyboard_capture: Optional[GlobalKeyboardCapture] = None,
    joystick_capture: Optional[GlobalJoystickCapture] = None,
) -> Dict[str, Any]:
    st = service.status()
    status = {
        "control_mode": st.control_mode,
        "dynamics_model": st.dynamics_model,
        "clock_mode": st.clock_mode,
        "running": st.running,
        "play_state": st.play_state,
        "playback_speed_x": st.playback_speed_x,
        "publisher_connected": st.publisher_connected,
        "publisher_error": st.publisher_error,
        "target_ip": service.publisher.target_ip,
        "ws_port": service.publisher.ws_port,
        "server_url": service.server_url,
        "sim_time_s": st.sim_time_s,
        "sim_time_hms": st.sim_time_hms,
        "rx_3001_count": st.rx_3001_count,
        "rx_0003_count": st.rx_0003_count,
        "rx_2002_count": st.rx_2002_count,
        "rx_3002_count": st.rx_3002_count,
        "rx_3003_count": st.rx_3003_count,
        "rx_4103_count": st.rx_4103_count,
        "rx_5001_count": st.rx_5001_count,
        "last_rx_3001": st.last_rx_3001,
        "last_rx_0003": st.last_rx_0003,
        "last_rx_2002": st.last_rx_2002,
        "last_rx_3002": st.last_rx_3002,
        "last_rx_3003": st.last_rx_3003,
        "last_rx_4103": st.last_rx_4103,
        "last_rx_5001": st.last_rx_5001,
        "last_heartbeat_error": st.last_heartbeat_error,
        "last_collision_event": st.last_collision_event,
        "collisions_by_vehicle": st.collisions_by_vehicle,
        "collision_responses_by_vehicle": st.collision_responses_by_vehicle,
        "manual": st.manual,
        "manual_by_vehicle": st.manual_by_vehicle,
        "vehicle_control_modes": st.vehicle_control_modes,
        "vehicle_dynamics": st.vehicle_dynamics,
        "vehicle_providers": st.vehicle_providers,
        "provider_statuses": st.provider_statuses,
        "manual_source_targets": st.manual_source_targets,
        "vehicles": [
            {
                "vehicle_id": v.vehicle_id,
                "flight_plan_number": v.flight_plan_number,
                "state": v.state.value,
                "etot_s": v.etot_s,
                "elapsed_s": v.elapsed_s,
                "total_duration_s": v.total_duration_s,
                "last_point": v.last_point,
                "last_error": v.last_error,
            }
            for v in st.vehicles
        ],
    }
    if keyboard_capture is not None:
        status["keyboard_capture"] = keyboard_capture.status().to_dict()
    if joystick_capture is not None:
        status["joystick_capture"] = joystick_capture.status().to_dict()
    return status


def _visualization_base_url() -> str:
    return str(os.environ.get(VISUALIZATION_URL_ENV, DEFAULT_VISUALIZATION_URL)).strip().rstrip("/")


def _visualization_request(
    path: str,
    *,
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
    timeout_s: float = 2.5,
) -> Any:
    payload = None
    headers: Dict[str, str] = {}
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib_request.Request(
        f"{_visualization_base_url()}{path}",
        data=payload,
        headers=headers,
        method=method.upper(),
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read()
            content_type = response.headers.get("content-type", "")
    except urllib_error.HTTPError as exc:
        detail: Any = exc.reason
        raw = exc.read()
        if raw:
            try:
                detail = json.loads(raw.decode("utf-8"))
                if isinstance(detail, dict) and detail.get("detail"):
                    detail = detail["detail"]
            except Exception:
                detail = raw.decode("utf-8", errors="replace")
        raise VisualizationSyncError(f"{method.upper()} {path} failed: {detail}") from exc
    except Exception as exc:
        raise VisualizationSyncError(
            f"Visualization Manager request failed: {type(exc).__name__}: {exc}"
        ) from exc

    if "json" not in content_type.lower():
        return raw.decode("utf-8", errors="replace")
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _pick_visualization_vehicle(
    catalog: Dict[str, Any],
    *,
    vehicle_id: str,
    preferred_name: str = "",
) -> str:
    vehicles = catalog.get("vehicles") or []
    known_names = {
        str(item.get("name") or "").strip()
        for item in vehicles
        if str(item.get("name") or "").strip()
    }
    available_names = [
        str(item.get("name") or "").strip()
        for item in vehicles
        if item.get("available") and str(item.get("name") or "").strip()
    ]
    if preferred_name:
        if known_names and preferred_name not in known_names:
            raise VisualizationSyncError(f"Unknown AirSim vehicle: {preferred_name}")
        return preferred_name

    vehicle_map = catalog.get("vehicle_map") or {}
    mapped_name = str(vehicle_map.get(vehicle_id) or "").strip()
    if mapped_name and mapped_name in available_names:
        return mapped_name

    return available_names[0] if len(available_names) == 1 else ""


def _aircraft_id_for_airsim_name(vehicle_map: Dict[str, str], airsim_name: str) -> str:
    target = str(airsim_name or "").strip()
    if not target:
        return ""
    for aircraft_id, mapped_name in sorted((vehicle_map or {}).items()):
        if str(mapped_name or "").strip() == target:
            return str(aircraft_id or "").strip()
    # Common DTAM runtime naming: Drone1 -> UAM0001.
    lowered = target.lower()
    if lowered.startswith("drone"):
        suffix = target[5:].strip()
        if suffix.isdigit():
            return f"UAM{int(suffix):04d}"
    return ""


def _fetch_visualization_catalog(*, vehicle_id: str = "", refresh: bool = True) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "base_url": _visualization_base_url(),
        "reachable": False,
        "connected": False,
        "selected_vehicle_id": str(vehicle_id or "").strip(),
        "selected_airsim_vehicle": "",
        "view_vehicle_id": "",
        "view_airsim_vehicle": "",
        "suggested_airsim_vehicle": "",
        "vehicle_map": {},
        "vehicles": [],
        "airsim": {},
        "origin_geopoint": {},
        "unreal": {},
        "error": "",
    }
    connect_error = ""

    if refresh:
        try:
            _visualization_request("/api/airsim/connect", method="POST", body={})
        except VisualizationSyncError as exc:
            connect_error = str(exc)

    try:
        catalog = _visualization_request("/api/airsim/vehicles")
    except VisualizationSyncError as exc:
        data["error"] = connect_error or str(exc)
        return data

    airsim = dict(catalog.get("airsim") or {})
    vehicle_map = dict(catalog.get("vehicle_map") or {})
    data.update({
        "reachable": True,
        "connected": bool(airsim.get("connected")),
        "vehicle_map": vehicle_map,
        "vehicles": list(catalog.get("vehicles") or []),
        "airsim": airsim,
        "origin_geopoint": dict(catalog.get("origin_geopoint") or {}),
        "unreal": dict(catalog.get("unreal") or {}),
        "selected_airsim_vehicle": str(vehicle_map.get(data["selected_vehicle_id"]) or "").strip(),
        "view_airsim_vehicle": str(catalog.get("default_vehicle_name") or "").strip(),
        "view_vehicle_id": _aircraft_id_for_airsim_name(vehicle_map, str(catalog.get("default_vehicle_name") or "")),
    })
    if connect_error:
        data["error"] = connect_error
    try:
        data["suggested_airsim_vehicle"] = _pick_visualization_vehicle(
            catalog,
            vehicle_id=data["selected_vehicle_id"],
        )
    except VisualizationSyncError as exc:
        data["error"] = str(exc)
    if not data["connected"]:
        data["error"] = str(airsim.get("last_error") or data["error"] or "AirSim is disconnected")
    return data


def _sync_visualization_vehicle(
    *,
    vehicle_id: str,
    preferred_name: str = "",
    require_connected: bool,
    require_selection: bool,
) -> Dict[str, Any]:
    catalog = _fetch_visualization_catalog(vehicle_id=vehicle_id, refresh=True)
    if not catalog.get("reachable"):
        raise VisualizationSyncError(catalog.get("error") or "Visualization Manager is unavailable")
    if require_connected and not catalog.get("connected"):
        raise VisualizationSyncError(catalog.get("error") or "AirSim is not connected")

    chosen = _pick_visualization_vehicle(
        catalog,
        vehicle_id=vehicle_id,
        preferred_name=str(preferred_name or "").strip(),
    )
    if not chosen and require_selection:
        available_names = [
            str(item.get("name") or "").strip()
            for item in catalog.get("vehicles") or []
            if item.get("available") and str(item.get("name") or "").strip()
        ]
        if available_names:
            raise VisualizationSyncError("Select an AirSim vehicle before starting keyboard capture")
        raise VisualizationSyncError("No AirSim vehicles are available from Visualization Manager")

    if chosen:
        chosen_entry = _find_visualization_vehicle(catalog, chosen)
        if require_connected and (not chosen_entry or not chosen_entry.get("available")):
            raise VisualizationSyncError(f"AirSim vehicle is not available: {chosen}")
        current_name = str((catalog.get("vehicle_map") or {}).get(vehicle_id) or "").strip()
        if current_name != chosen:
            _visualization_request(
                "/api/airsim/vehicle-map",
                method="PATCH",
                body={vehicle_id: chosen},
            )
        catalog = _fetch_visualization_catalog(vehicle_id=vehicle_id, refresh=False)
        catalog["selected_airsim_vehicle"] = chosen
        catalog["suggested_airsim_vehicle"] = chosen
    return catalog


def _handle_joystick_hat_action(
    service: IntegratedAirMobilityService,
    action: str,
) -> Dict[str, Any]:
    resolved_action = str(action or "").strip().lower()
    if resolved_action not in ("left", "right", "up", "down"):
        return {"ok": False, "error": f"unsupported hat action: {action}"}

    yaw_delta_deg = 0.0
    focal_length_delta = 0.0
    if resolved_action == "left":
        yaw_delta_deg = -HAT_CAMERA_YAW_STEP_DEG
    elif resolved_action == "right":
        yaw_delta_deg = HAT_CAMERA_YAW_STEP_DEG
    elif resolved_action == "up":
        focal_length_delta = HAT_CAMERA_ZOOM_STEP
    elif resolved_action == "down":
        focal_length_delta = -HAT_CAMERA_ZOOM_STEP

    aircraft_id = str(service.get_manual_source_target("joystick") or "").strip() or "UAM0001"
    payload = {
        "timestamp": _iso_ts(),
        "aircraftId": aircraft_id,
        "cameraName": DEFAULT_VISUALIZATION_CAMERA_NAME,
        "source": "joystick",
        "action": "adjust",
        "yawDeltaDeg": yaw_delta_deg,
        "pitchDeltaDeg": 0.0,
        "focalLengthDelta": focal_length_delta,
    }
    try:
        if service.send(parse_payload("5002", payload)):
            return {"ok": True, "transport": "icd", "mid": "5002", "payload": payload}
    except Exception as exc:
        logger.debug("5002 camera command failed: %s", exc)
        return {
            "ok": False,
            "transport": "icd",
            "mid": "5002",
            "payload": payload,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    return {
        "ok": False,
        "transport": "icd",
        "mid": "5002",
        "payload": payload,
        "errors": ["WebSocket send failed"],
    }


def _find_visualization_vehicle(catalog: Dict[str, Any], name: str) -> Dict[str, Any]:
    target = str(name or "").strip()
    for item in catalog.get("vehicles") or []:
        if str(item.get("name") or "").strip() == target:
            return dict(item)
    return {}


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _resolved_manual_vehicle_id(
    service: IntegratedAirMobilityService,
    body: Dict[str, Any],
) -> str:
    requested = str(body.get("vehicle_id") or "").strip()
    if requested:
        return requested
    current = str((service.manual_snapshot() or {}).get("vehicle_id") or "").strip()
    return current or "UAM0001"


def _prepare_manual_config(
    service: IntegratedAirMobilityService,
    body: Dict[str, Any],
    visualization: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    prepared = dict(body or {})
    prepared["vehicle_id"] = _resolved_manual_vehicle_id(service, prepared)

    manual_snapshot = service.manual_snapshot() or {}
    current_origin = dict(manual_snapshot.get("origin") or {})
    selected_name = str(
        prepared.get("airsim_vehicle_name")
        or (visualization or {}).get("selected_airsim_vehicle")
        or ""
    ).strip()

    origin_geopoint = dict((visualization or {}).get("origin_geopoint") or {})
    selected_vehicle = _find_visualization_vehicle(visualization or {}, selected_name)
    pose = dict(selected_vehicle.get("pose") or {})

    resolved_origin = {
        "origin_lat": _optional_float(prepared.get("origin_lat")),
        "origin_lon": _optional_float(prepared.get("origin_lon")),
        "origin_alt_m": _optional_float(prepared.get("origin_alt_m")),
    }
    if resolved_origin["origin_lat"] is None:
        resolved_origin["origin_lat"] = _optional_float(origin_geopoint.get("latitude"))
    if resolved_origin["origin_lon"] is None:
        resolved_origin["origin_lon"] = _optional_float(origin_geopoint.get("longitude"))
    if resolved_origin["origin_alt_m"] is None:
        resolved_origin["origin_alt_m"] = _optional_float(origin_geopoint.get("altitude"))
    if resolved_origin["origin_lat"] is None:
        resolved_origin["origin_lat"] = _optional_float(current_origin.get("origin_lat"))
    if resolved_origin["origin_lon"] is None:
        resolved_origin["origin_lon"] = _optional_float(current_origin.get("origin_lon"))
    if resolved_origin["origin_alt_m"] is None:
        resolved_origin["origin_alt_m"] = _optional_float(current_origin.get("origin_alt_m"))

    for key, value in resolved_origin.items():
        if value is not None:
            prepared[key] = value

    if pose:
        # AirSim/Cosys applies simSetVehiclePose in the selected vehicle's
        # spawn-relative replay frame.  The catalog pose reported by AirSim is
        # world/global NED, so copying pose north/east/down into manual initial
        # state adds the spawn offset a second time.  Keep manual position local
        # to the spawn (normally 0/0/0) and only inherit heading when explicit
        # configuration did not provide one.
        if _optional_float(prepared.get("initial_heading_deg")) is None:
            yaw_value = _optional_float(pose.get("yaw_deg"))
            if yaw_value is not None:
                prepared["initial_heading_deg"] = yaw_value

    prepared.setdefault("initial_north_m", 0.0)
    prepared.setdefault("initial_east_m", 0.0)
    prepared.setdefault("initial_down_m", 0.0)

    return prepared


def _source_control_mode(source: str, control_mode: str = "") -> str:
    source_key = str(source or "").strip().lower()
    mode_key = str(control_mode or "").strip().lower()
    if source_key == ControlMode.JOYSTICK.value or mode_key == ControlMode.JOYSTICK.value:
        return ControlMode.JOYSTICK.value
    if source_key == ControlMode.KEYBOARD.value or mode_key == ControlMode.KEYBOARD.value:
        return ControlMode.KEYBOARD.value
    return mode_key or source_key


def _resolve_view_manual_target(
    service: IntegratedAirMobilityService,
    catalog: Dict[str, Any],
    *,
    source: str,
    control_mode: str,
) -> Dict[str, Any]:
    """Resolve keyboard/joystick target from the current Unreal main-view vehicle.

    Policy:
    - Autopilot/Mission never requires or forces view switching.
    - Keyboard/Joystick authority follows the vehicle selected in Unreal with
      the 1/2/3/4/5 view keys.
    - If the selected vehicle is not configured for the input source, the input
      is ignored instead of silently overriding an Autopilot aircraft.
    """
    expected_mode = _source_control_mode(source, control_mode)
    vehicle_map = dict(catalog.get("vehicle_map") or {})
    view_name = str(catalog.get("default_vehicle_name") or catalog.get("view_airsim_vehicle") or "").strip()
    if not view_name:
        for item in catalog.get("vehicles") or []:
            if item.get("is_default_view"):
                view_name = str(item.get("name") or "").strip()
                break

    vehicle_id = _aircraft_id_for_airsim_name(vehicle_map, view_name)
    if not vehicle_id:
        return {
            "ok": False,
            "target": "",
            "view_airsim_vehicle": view_name,
            "reason": "current Unreal view vehicle is not mapped to a DTAM aircraft",
        }

    mode_info = (
        service.control_mode_info(vehicle_id)
        if hasattr(service, "control_mode_info")
        else {}
    )
    actual_mode = str(mode_info.get("mode") or "").strip().lower()
    default_mode = str(mode_info.get("defaultMode") or "").strip().lower()
    explicit_mode = bool(mode_info.get("explicit"))
    if expected_mode in (ControlMode.KEYBOARD.value, ControlMode.JOYSTICK.value) and actual_mode != expected_mode:
        return {
            "ok": False,
            "target": "",
            "view_vehicle_id": vehicle_id,
            "view_airsim_vehicle": view_name,
            "expected_mode": expected_mode,
            "actual_mode": actual_mode,
            "explicit_mode": explicit_mode,
            "defaultMode": default_mode,
            "reason": f"selected vehicle is {actual_mode or 'unknown'}, not {expected_mode}",
        }

    return {
        "ok": True,
        "target": vehicle_id,
        "view_vehicle_id": vehicle_id,
        "view_airsim_vehicle": view_name,
        "expected_mode": expected_mode,
        "actual_mode": actual_mode,
        "explicit_mode": explicit_mode,
        "defaultMode": default_mode,
    }


def create_app(service: Optional[IntegratedAirMobilityService] = None) -> FastAPI:
    """Create the FastAPI app. `service` 가 None 이면 기본값으로 새로 생성."""
    svc = service or IntegratedAirMobilityService(
        target_ip="127.0.0.1",
        ws_port=8096,
    )
    view_cache: Dict[str, Any] = {
        "ts": 0.0,
        "attempt_ts": 0.0,
        "catalog": {},
        "error": "",
        "refreshing": False,
    }
    view_cache_lock = threading.RLock()
    capture_target_state: Dict[str, str] = {
        ControlMode.KEYBOARD.value: "",
        ControlMode.JOYSTICK.value: "",
    }

    def _remember_view_catalog(catalog: Dict[str, Any]) -> None:
        if not isinstance(catalog, dict):
            return
        # _sync_visualization_vehicle returns an enriched catalog with
        # view_airsim_vehicle rather than the raw default_vehicle_name key.
        # Keep both spellings so the capture routing code can consume either.
        normalized = dict(catalog)
        if not normalized.get("default_vehicle_name") and normalized.get("view_airsim_vehicle"):
            normalized["default_vehicle_name"] = normalized.get("view_airsim_vehicle")
        now = time.monotonic()
        with view_cache_lock:
            view_cache.update({
                "ts": now,
                "attempt_ts": now,
                "catalog": normalized,
                "error": "",
                "refreshing": False,
            })

    def _refresh_view_catalog_worker() -> None:
        try:
            catalog = _visualization_request("/api/airsim/vehicles", timeout_s=VIEW_CATALOG_TIMEOUT_S)
            if not isinstance(catalog, dict):
                catalog = {}
            _remember_view_catalog(catalog)
        except Exception as exc:
            with view_cache_lock:
                view_cache["error"] = f"{type(exc).__name__}: {exc}"
                view_cache["refreshing"] = False

    def _schedule_view_catalog_refresh(now: float) -> None:
        with view_cache_lock:
            last_attempt = float(view_cache.get("attempt_ts") or 0.0)
            if bool(view_cache.get("refreshing")) or now - last_attempt <= VIEW_CATALOG_CACHE_TTL_S:
                return
            view_cache["attempt_ts"] = now
            view_cache["refreshing"] = True
        threading.Thread(
            target=_refresh_view_catalog_worker,
            name="dtam-vehicle-view-catalog-refresh",
            daemon=True,
        ).start()

    def _cached_view_catalog(*, allow_blocking_refresh: bool = False) -> Dict[str, Any]:
        now = time.monotonic()
        with view_cache_lock:
            last_success = float(view_cache.get("ts") or 0.0)
            last_attempt = float(view_cache.get("attempt_ts") or 0.0)
            cached_catalog = dict(view_cache.get("catalog") or {})
            if now - last_success <= VIEW_CATALOG_CACHE_TTL_S:
                return cached_catalog

        if not allow_blocking_refresh:
            # Keyboard/joystick capture threads run through this function.
            # They must never wait for Visualization/Unreal HTTP calls; a
            # timeout here directly becomes visible stick lag. Refresh in the
            # background and immediately return the last known catalog.
            _schedule_view_catalog_refresh(now)
            with view_cache_lock:
                last_success = float(view_cache.get("ts") or 0.0)
                cached_catalog = dict(view_cache.get("catalog") or {})
                if cached_catalog and now - last_success <= VIEW_CATALOG_STALE_TTL_S:
                    return cached_catalog
            return {}

        if now - last_attempt <= VIEW_CATALOG_CACHE_TTL_S:
            return cached_catalog
        with view_cache_lock:
            view_cache["attempt_ts"] = now
        try:
            catalog = _visualization_request("/api/airsim/vehicles", timeout_s=VIEW_CATALOG_TIMEOUT_S)
            if not isinstance(catalog, dict):
                catalog = {}
            _remember_view_catalog(catalog)
            return dict(catalog)
        except Exception as exc:
            with view_cache_lock:
                view_cache["error"] = f"{type(exc).__name__}: {exc}"
            if cached_catalog and now - last_success <= VIEW_CATALOG_STALE_TTL_S:
                return cached_catalog
            return {}

    def _zero_previous_capture_target(source_key: str, previous_target: str, control_mode: str) -> None:
        if not previous_target:
            return
        try:
            svc.submit_operator_control_input(
                {
                    "aircraftId": previous_target,
                    "axes": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "throttle": 0.0},
                    "active": False,
                },
                source=source_key,
                control_mode=control_mode,
                send_via_server=False,
            )
        except Exception as exc:
            logger.debug("failed to neutralize previous %s target %s: %s", source_key, previous_target, exc)

    def _submit_capture_input(data: Dict[str, float], *, source: str, control_mode: str) -> Dict[str, Any]:
        source_key = _source_control_mode(source, control_mode)
        raw = dict(data or {})
        catalog = _cached_view_catalog(allow_blocking_refresh=False)
        target_info: Dict[str, Any] = {}
        target = ""
        fallback_target = str(svc.get_manual_source_target(source_key) or "").strip()
        if catalog:
            target_info = _resolve_view_manual_target(
                svc,
                catalog,
                source=source_key,
                control_mode=control_mode,
            )
            target = str(target_info.get("target") or "").strip()
            if (
                not target
                and fallback_target
                and (
                    not str(target_info.get("view_vehicle_id") or "").strip()
                    or not bool(target_info.get("explicit_mode"))
                )
            ):
                # Visualization is reachable, but the current-view vehicle could not
                # be identified reliably (e.g. packaged exe without a direct default
                # vehicle query, or equal poses before the first frame).  Do not make
                # the aircraft feel "dead"; keep the capture-start target alive until
                # a definite explicitly configured view vehicle is known.  Explicit
                # Autopilot/another-source vehicles still block the input.
                target = fallback_target
                target_info = {
                    **target_info,
                    "ok": True,
                    "target": target,
                    "fallback": "manual_source_target_no_view_match",
                }
        else:
            # Older/no Visualization runtime fallback: preserve the already
            # selected source target, but do not invent a new one.
            target = fallback_target
            target_info = {
                "ok": bool(target),
                "target": target,
                "fallback": "manual_source_target",
                "error": str(view_cache.get("error") or ""),
            }

        previous = capture_target_state.get(source_key, "")
        if previous and previous != target:
            _zero_previous_capture_target(source_key, previous, control_mode)
        capture_target_state[source_key] = target

        if not target:
            return {"ok": False, "ignored": True, "view_target": target_info}

        svc.set_manual_source_target(source_key, target)
        raw["aircraftId"] = target
        result = svc.submit_operator_control_input(
            raw,
            source=source_key,
            control_mode=control_mode,
            send_via_server=False,
        )
        result["view_target"] = target_info
        return result

    keyboard_capture = GlobalKeyboardCapture(
        lambda data: _submit_capture_input(
            data,
            source="keyboard",
            control_mode=ControlMode.KEYBOARD.value,
        )
    )
    joystick_capture = GlobalJoystickCapture(
        lambda data: _submit_capture_input(
            data,
            source="joystick",
            control_mode=ControlMode.JOYSTICK.value,
        ),
        on_hat_action=lambda action: _handle_joystick_hat_action(svc, action),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        try:
            keyboard_capture.stop()
        except Exception:
            pass
        try:
            joystick_capture.stop()
        except Exception:
            pass
        try:
            svc.close()
        except Exception:
            pass

    app = FastAPI(
        title="VehicleModule",
        summary="Flight plan -> 30 Hz trajectory -> DTAM 4001 publisher.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.service = svc
    app.state.keyboard_capture = keyboard_capture
    app.state.joystick_capture = joystick_capture

    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        # Starlette ≥0.29 은 request 를 첫 인자로 요구. 구버전 호환 위해 fallback.
        try:
            return templates.TemplateResponse(request, "index.html")
        except TypeError:
            return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/api/status")
    async def api_status() -> Dict[str, Any]:
        return _status_to_dict(svc, keyboard_capture, joystick_capture)

    @app.get("/api/health")
    async def api_health() -> Dict[str, Any]:
        status = _status_to_dict(svc, keyboard_capture, joystick_capture)
        return {
            "ok": True,
            "module": "VehicleModule",
            "running": bool(status.get("running")),
            "play_state": status.get("play_state"),
            "rx_3001_count": status.get("rx_3001_count"),
            "rx_2002_count": status.get("rx_2002_count"),
            "rx_0003_count": status.get("rx_0003_count"),
            "vehicle_dynamics": status.get("vehicle_dynamics", {}),
            "vehicle_providers": status.get("vehicle_providers", {}),
            "provider_statuses": status.get("provider_statuses", {}),
            "vehicles": status.get("vehicles", []),
        }

    @app.get("/api/vfds/status")
    async def api_vfds_status() -> Dict[str, Any]:
        return {
            "ok": True,
            "provider": svc.vfds_status(),
            "status": _status_to_dict(svc, keyboard_capture, joystick_capture),
        }

    @app.post("/api/vfds/ensure")
    async def api_vfds_ensure(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        try:
            timeout_s = float(body.get("timeout_s") or body.get("timeoutS") or 20.0)
            runtime = await asyncio.to_thread(svc.ensure_vfds_runtime, timeout_s=timeout_s)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        return {
            "ok": bool(runtime.get("ok")),
            "runtime": runtime,
            "provider": svc.vfds_status(),
            "status": _status_to_dict(svc, keyboard_capture, joystick_capture),
        }

    @app.post("/api/collision/clear")
    async def api_collision_clear(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        vehicle_id = str(
            body.get("aircraftId")
            or body.get("vehicleId")
            or body.get("vehicle_id")
            or ""
        ).strip()
        all_flag = bool(body.get("all") or body.get("clearAll"))
        clear_history = bool(body.get("clearHistory") or body.get("clear_history"))
        result = svc.clear_collision_response(
            "" if all_flag else vehicle_id,
            clear_history=clear_history,
        )
        return {
            "ok": True,
            **result,
            "status": _status_to_dict(svc, keyboard_capture, joystick_capture),
        }

    @app.post("/api/collision/{vehicle_id}/clear")
    async def api_collision_clear_vehicle(vehicle_id: str) -> Dict[str, Any]:
        result = svc.clear_collision_response(str(vehicle_id or "").strip())
        return {
            "ok": True,
            **result,
            "status": _status_to_dict(svc, keyboard_capture, joystick_capture),
        }

    @app.get("/api/visualization/vehicles")
    async def api_visualization_vehicles(refresh: bool = True) -> Dict[str, Any]:
        manual = svc.manual_snapshot()
        vehicle_id = str((manual or {}).get("vehicle_id") or "").strip()
        return await asyncio.to_thread(
            _fetch_visualization_catalog,
            vehicle_id=vehicle_id,
            refresh=False,
        )

    @app.post("/api/publisher")
    async def api_publisher(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        svc.reconfigure_publisher(
            target_ip=body.get("target_ip"),
            ws_port=int(body["ws_port"]) if body.get("ws_port") is not None else None,
        )
        return _status_to_dict(svc, keyboard_capture, joystick_capture)

    @app.post("/api/plans")
    async def api_add_plan(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        """body 는 비행계획 JSON (단일 object 또는 list)."""
        try:
            ids = svc.add_plans_from_json(body)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid plan: {exc}")
        return {"added": ids, "status": _status_to_dict(svc, keyboard_capture, joystick_capture)}

    @app.post("/api/plans/batch")
    async def api_add_plans_batch(body: List[Dict[str, Any]] = Body(...)) -> Dict[str, Any]:
        """브라우저에서 파일을 읽어 여러 플랜을 한번에 등록."""
        added_all: List[str] = []
        errors: List[str] = []
        for data in body:
            try:
                added_all.extend(svc.add_plans_from_json(data))
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        return {"added": added_all, "errors": errors, "status": _status_to_dict(svc, keyboard_capture, joystick_capture)}

    @app.delete("/api/plans/{vehicle_id}")
    async def api_remove_plan(vehicle_id: str) -> Dict[str, Any]:
        ok = svc.remove_plan(vehicle_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"unknown vehicle: {vehicle_id}")
        return _status_to_dict(svc, keyboard_capture, joystick_capture)

    @app.delete("/api/plans")
    async def api_clear_plans() -> Dict[str, Any]:
        svc.clear_plans()
        return _status_to_dict(svc, keyboard_capture, joystick_capture)

    @app.post("/api/clock/mode")
    async def api_clock_mode(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        mode = body.get("mode")
        try:
            svc.set_clock_mode(ClockMode(str(mode)))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _status_to_dict(svc, keyboard_capture, joystick_capture)

    @app.post("/api/control/mode")
    async def api_control_mode(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        mode = body.get("mode")
        try:
            resolved_mode = ControlMode(str(mode))
            if resolved_mode != ControlMode.KEYBOARD:
                keyboard_capture.stop()
            if resolved_mode != ControlMode.JOYSTICK:
                joystick_capture.stop()
            if resolved_mode == ControlMode.MISSION:
                svc.set_manual_input({"roll": 0, "pitch": 0, "yaw": 0, "throttle": 0})
            svc.set_control_mode(resolved_mode)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _status_to_dict(svc, keyboard_capture, joystick_capture)

    @app.post("/api/control/modes")
    async def api_control_modes(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        try:
            default_raw = body.get("defaultMode") or body.get("default_mode") or body.get("mode")
            vehicle_raw = body.get("vehicleModes") or body.get("vehicle_modes") or {}
            dynamics_raw = body.get("dynamicsByAircraft") or body.get("dynamics_by_aircraft") or {}
            provider_raw = body.get("providerByAircraft") or body.get("provider_by_aircraft") or {}
            normalized: Dict[str, str] = {}
            if isinstance(vehicle_raw, dict):
                for vehicle_id, mode in vehicle_raw.items():
                    vehicle_key = str(vehicle_id or "").strip()
                    if not vehicle_key:
                        continue
                    normalized[vehicle_key] = ControlMode(str(mode)).value
            dynamics_by_aircraft: Dict[str, str] = {}
            if isinstance(dynamics_raw, dict):
                for vehicle_id, dynamics in dynamics_raw.items():
                    vehicle_key = str(vehicle_id or "").strip()
                    if vehicle_key:
                        dynamics_by_aircraft[vehicle_key] = str(dynamics or "").strip()
            provider_by_aircraft: Dict[str, str] = {}
            if isinstance(provider_raw, dict):
                for vehicle_id, provider in provider_raw.items():
                    vehicle_key = str(vehicle_id or "").strip()
                    if vehicle_key:
                        provider_by_aircraft[vehicle_key] = str(provider or "").strip()
            applied = svc.set_vehicle_control_modes(
                default_mode=ControlMode(str(default_raw)) if default_raw else None,
                vehicle_modes=normalized,
                dynamics_by_aircraft=dynamics_by_aircraft,
                provider_by_aircraft=provider_by_aircraft,
            )
            if applied["defaultMode"] == ControlMode.MISSION.value and all(
                mode == ControlMode.MISSION.value for mode in applied["vehicleModes"].values()
            ):
                keyboard_capture.stop()
                joystick_capture.stop()
                applied = svc.set_vehicle_control_modes(
                    default_mode=ControlMode.MISSION,
                    vehicle_modes=normalized,
                    dynamics_by_aircraft=dynamics_by_aircraft,
                    provider_by_aircraft=provider_by_aircraft,
                )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        status = _status_to_dict(svc, keyboard_capture, joystick_capture)
        status["applied_control_modes"] = applied
        return status

    @app.post("/api/control/manual/config")
    async def api_manual_config(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        request_body = dict(body or {})
        request_body["vehicle_id"] = _resolved_manual_vehicle_id(svc, request_body)
        visualization: Optional[Dict[str, Any]] = None
        sync_visualization = bool(request_body.get("sync_visualization", False))
        if sync_visualization:
            try:
                visualization = await asyncio.wait_for(
                    asyncio.to_thread(
                        _sync_visualization_vehicle,
                        vehicle_id=request_body["vehicle_id"],
                        preferred_name=str(request_body.get("airsim_vehicle_name") or ""),
                        require_connected=False,
                        require_selection=False,
                    ),
                    timeout=float(request_body.get("visualization_timeout_s") or 3.0),
                )
            except (asyncio.TimeoutError, VisualizationSyncError) as exc:
                # /api/control/manual/config is primarily a local dynamics/origin
                # setup call used while OperationModule saves mission settings.
                # Do not block or fail the save path just because Unreal/AirSim is
                # still booting.  Keyboard/joystick capture start endpoints still
                # perform the strict Visualization/AirSim sync before accepting
                # real-time input.
                visualization = {"error": str(exc) or "Visualization sync timed out"}
        else:
            visualization = {"skipped": True}
        if isinstance(visualization, dict):
            _remember_view_catalog(visualization)
        prepared = _prepare_manual_config(svc, request_body, visualization)
        try:
            manual = svc.configure_manual_vehicle(prepared)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        status = _status_to_dict(svc, keyboard_capture, joystick_capture)
        status["manual"] = manual
        status["visualization"] = visualization
        return status

    @app.post("/api/control/keyboard/start")
    async def api_keyboard_start(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        request_body = dict(body or {})
        request_body["vehicle_id"] = _resolved_manual_vehicle_id(svc, request_body)
        try:
            visualization = await asyncio.to_thread(
                _sync_visualization_vehicle,
                vehicle_id=request_body["vehicle_id"],
                preferred_name=str(request_body.get("airsim_vehicle_name") or ""),
                require_connected=True,
                require_selection=True,
            )
            _remember_view_catalog(visualization)
            manual = svc.configure_manual_vehicle(
                _prepare_manual_config(svc, request_body, visualization)
            )
            svc.set_vehicle_control_mode(request_body["vehicle_id"], ControlMode.KEYBOARD)
            svc.set_manual_source_target("keyboard", request_body["vehicle_id"])
            svc.start()
            capture = await asyncio.to_thread(keyboard_capture.start)
            if not capture.active:
                raise RuntimeError(capture.last_error or "Keyboard capture did not start")
        except VisualizationSyncError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "ok": True,
            "manual": manual,
            "visualization": visualization,
            "keyboard_capture": capture.to_dict(),
            "status": _status_to_dict(svc, keyboard_capture, joystick_capture),
        }

    @app.post("/api/control/joystick/start")
    async def api_joystick_start(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        request_body = dict(body or {})
        request_body["vehicle_id"] = _resolved_manual_vehicle_id(svc, request_body)
        try:
            visualization = await asyncio.to_thread(
                _sync_visualization_vehicle,
                vehicle_id=request_body["vehicle_id"],
                preferred_name=str(request_body.get("airsim_vehicle_name") or ""),
                require_connected=True,
                require_selection=True,
            )
            _remember_view_catalog(visualization)
            manual = svc.configure_manual_vehicle(
                _prepare_manual_config(svc, request_body, visualization)
            )
            svc.set_vehicle_control_mode(request_body["vehicle_id"], ControlMode.JOYSTICK)
            svc.set_manual_source_target("joystick", request_body["vehicle_id"])
            svc.start()
            capture = await asyncio.to_thread(joystick_capture.start)
            if not capture.active:
                raise RuntimeError(capture.last_error or "Joystick capture did not start")
        except VisualizationSyncError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "ok": True,
            "manual": manual,
            "visualization": visualization,
            "joystick_capture": capture.to_dict(),
            "status": _status_to_dict(svc, keyboard_capture, joystick_capture),
        }

    @app.post("/api/control/input")
    async def api_control_input(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        try:
            result = svc.submit_operator_control_input(
                body,
                source=str(body.get("source") or "api"),
                control_mode=str(body.get("controlMode") or body.get("mode") or ""),
                send_via_server=bool(body.get("sendViaServer") or body.get("send_via_server")),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True, **result, "status": _status_to_dict(svc, keyboard_capture, joystick_capture)}

    @app.post("/api/simulation/setup")
    async def api_simulation_setup(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        try:
            applied = svc.apply_simulation_setup(body)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "ok": True,
            "applied": applied,
            "status": _status_to_dict(svc, keyboard_capture, joystick_capture),
        }

    @app.post("/api/control/keyboard/stop")
    async def api_keyboard_stop() -> Dict[str, Any]:
        try:
            target = svc.get_manual_source_target("keyboard")
            capture = await asyncio.to_thread(keyboard_capture.stop)
            neutral = {"roll": 0, "pitch": 0, "yaw": 0, "throttle": 0, "active": False}
            if target:
                neutral["aircraftId"] = target
            result = svc.submit_operator_control_input(
                neutral,
                source="keyboard",
                control_mode=ControlMode.KEYBOARD.value,
                send_via_server=False,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "ok": True,
            "manual": result.get("manual"),
            "icd": result,
            "keyboard_capture": capture.to_dict(),
            "status": _status_to_dict(svc, keyboard_capture, joystick_capture),
        }

    @app.post("/api/control/joystick/stop")
    async def api_joystick_stop() -> Dict[str, Any]:
        try:
            target = svc.get_manual_source_target("joystick")
            capture = await asyncio.to_thread(joystick_capture.stop)
            neutral = {"roll": 0, "pitch": 0, "yaw": 0, "throttle": 0, "active": False}
            if target:
                neutral["aircraftId"] = target
            result = svc.submit_operator_control_input(
                neutral,
                source="joystick",
                control_mode=ControlMode.JOYSTICK.value,
                send_via_server=False,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "ok": True,
            "manual": result.get("manual"),
            "icd": result,
            "joystick_capture": capture.to_dict(),
            "status": _status_to_dict(svc, keyboard_capture, joystick_capture),
        }

    @app.post("/api/clock/feed")
    async def api_feed_time(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        hms = body.get("hms")
        sec = body.get("seconds")
        try:
            if hms is not None:
                svc.feed_time_hhmmss(str(hms))
            elif sec is not None:
                svc.feed_time_seconds(float(sec))
            else:
                raise ValueError("'hms' or 'seconds' required")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _status_to_dict(svc, keyboard_capture, joystick_capture)

    @app.post("/api/clock/step")
    async def api_step_once(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        hms = body.get("hms")
        sec = body.get("seconds")
        try:
            if hms is not None:
                parts = str(hms).split(":")
                sim_s = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            elif sec is not None:
                sim_s = float(sec)
            else:
                raise ValueError("'hms' or 'seconds' required")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        svc.step_once(float(sim_s))
        return _status_to_dict(svc, keyboard_capture, joystick_capture)

    @app.post("/api/service/start")
    async def api_start(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        mode = body.get("mode")
        if mode:
            try:
                svc.set_clock_mode(ClockMode(str(mode)))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        svc.start()
        return _status_to_dict(svc, keyboard_capture, joystick_capture)

    @app.post("/api/service/stop")
    async def api_stop() -> Dict[str, Any]:
        was_mission = svc.status().control_mode == ControlMode.MISSION.value
        keyboard_capture.stop()
        joystick_capture.stop()
        if not was_mission:
            svc.set_manual_input({"roll": 0, "pitch": 0, "yaw": 0, "throttle": 0})
        svc.stop()
        if was_mission:
            svc.set_control_mode(ControlMode.MISSION)
            svc.set_clock_mode(ClockMode.EXTERNAL)
        return _status_to_dict(svc, keyboard_capture, joystick_capture)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
