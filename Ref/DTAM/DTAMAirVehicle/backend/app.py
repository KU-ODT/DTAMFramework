"""FastAPI app factory — DTAMAirVehicle dashboard."""
from __future__ import annotations

import asyncio
import json
import logging
import os
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

from ..service.global_keyboard_capture import GlobalKeyboardCapture
from ..service.integrated_service import ClockMode, ControlMode, IntegratedAirMobilityService

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
STATIC_DIR = FRONTEND / "static"
TEMPLATE_DIR = FRONTEND / "templates"
DEFAULT_VISUALIZATION_URL = "http://127.0.0.1:8096"
VISUALIZATION_URL_ENV = "DTAM_VISUALIZATION_URL"


class VisualizationSyncError(RuntimeError):
    pass


def _status_to_dict(
    service: IntegratedAirMobilityService,
    keyboard_capture: Optional[GlobalKeyboardCapture] = None,
) -> Dict[str, Any]:
    st = service.status()
    status = {
        "control_mode": st.control_mode,
        "dynamics_model": st.dynamics_model,
        "clock_mode": st.clock_mode,
        "running": st.running,
        "publisher_connected": st.publisher_connected,
        "publisher_error": st.publisher_error,
        "target_ip": service.publisher.target_ip,
        "target_port": service.publisher.target_port,
        "my_port": service.publisher.my_port,
        "sim_time_s": st.sim_time_s,
        "sim_time_hms": st.sim_time_hms,
        "rx_3001_count": st.rx_3001_count,
        "rx_0003_count": st.rx_0003_count,
        "rx_2002_count": st.rx_2002_count,
        "rx_3002_count": st.rx_3002_count,
        "rx_3003_count": st.rx_3003_count,
        "last_rx_3001": st.last_rx_3001,
        "last_rx_0003": st.last_rx_0003,
        "last_rx_2002": st.last_rx_2002,
        "last_rx_3002": st.last_rx_3002,
        "last_rx_3003": st.last_rx_3003,
        "last_heartbeat_error": st.last_heartbeat_error,
        "manual": st.manual,
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


def _fetch_visualization_catalog(*, vehicle_id: str = "", refresh: bool = True) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "base_url": _visualization_base_url(),
        "reachable": False,
        "connected": False,
        "selected_vehicle_id": str(vehicle_id or "").strip(),
        "selected_airsim_vehicle": "",
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
        pose_mapping = {
            "initial_north_m": "north",
            "initial_east_m": "east",
            "initial_down_m": "down",
            "initial_heading_deg": "yaw_deg",
        }
        for config_key, pose_key in pose_mapping.items():
            if _optional_float(prepared.get(config_key)) is None:
                pose_value = _optional_float(pose.get(pose_key))
                if pose_value is not None:
                    prepared[config_key] = pose_value

    return prepared


def create_app(service: Optional[IntegratedAirMobilityService] = None) -> FastAPI:
    """Create the FastAPI app. `service` 가 None 이면 기본값으로 새로 생성."""
    svc = service or IntegratedAirMobilityService(
        target_ip="127.0.0.1",
        target_port=17000,
        my_port=17030,
    )
    keyboard_capture = GlobalKeyboardCapture(svc.set_manual_input)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        try:
            keyboard_capture.stop()
        except Exception:
            pass
        try:
            svc.close()
        except Exception:
            pass

    app = FastAPI(
        title="DTAMAirVehicle",
        summary="Flight plan → 10 Hz trajectory → DTAM 4001 publisher.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.service = svc
    app.state.keyboard_capture = keyboard_capture

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
        return _status_to_dict(svc, keyboard_capture)

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
            target_port=int(body["target_port"]) if body.get("target_port") is not None else None,
            my_port=int(body["my_port"]) if body.get("my_port") is not None else None,
        )
        return _status_to_dict(svc, keyboard_capture)

    @app.post("/api/plans")
    async def api_add_plan(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        """body 는 비행계획 JSON (단일 object 또는 list)."""
        try:
            ids = svc.add_plans_from_json(body)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid plan: {exc}")
        return {"added": ids, "status": _status_to_dict(svc, keyboard_capture)}

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
        return {"added": added_all, "errors": errors, "status": _status_to_dict(svc, keyboard_capture)}

    @app.delete("/api/plans/{vehicle_id}")
    async def api_remove_plan(vehicle_id: str) -> Dict[str, Any]:
        ok = svc.remove_plan(vehicle_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"unknown vehicle: {vehicle_id}")
        return _status_to_dict(svc, keyboard_capture)

    @app.delete("/api/plans")
    async def api_clear_plans() -> Dict[str, Any]:
        svc.clear_plans()
        return _status_to_dict(svc, keyboard_capture)

    @app.post("/api/clock/mode")
    async def api_clock_mode(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        mode = body.get("mode")
        try:
            svc.set_clock_mode(ClockMode(str(mode)))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _status_to_dict(svc, keyboard_capture)

    @app.post("/api/control/mode")
    async def api_control_mode(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        mode = body.get("mode")
        try:
            resolved_mode = ControlMode(str(mode))
            if resolved_mode != ControlMode.KEYBOARD:
                keyboard_capture.stop()
            svc.set_control_mode(resolved_mode)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _status_to_dict(svc, keyboard_capture)

    @app.post("/api/control/manual/config")
    async def api_manual_config(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        request_body = dict(body or {})
        request_body["vehicle_id"] = _resolved_manual_vehicle_id(svc, request_body)
        visualization: Optional[Dict[str, Any]] = None
        prepared = request_body
        try:
            visualization = await asyncio.to_thread(
                _sync_visualization_vehicle,
                vehicle_id=request_body["vehicle_id"],
                preferred_name=str(request_body.get("airsim_vehicle_name") or ""),
                require_connected=False,
                require_selection=False,
            )
        except VisualizationSyncError as exc:
            visualization = await asyncio.to_thread(
                _fetch_visualization_catalog,
                vehicle_id=request_body["vehicle_id"],
                refresh=False,
            )
            visualization["error"] = str(exc)
        prepared = _prepare_manual_config(svc, request_body, visualization)
        try:
            manual = svc.configure_manual_vehicle(prepared)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        status = _status_to_dict(svc, keyboard_capture)
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
            manual = svc.configure_manual_vehicle(
                _prepare_manual_config(svc, request_body, visualization)
            )
            svc.set_control_mode(ControlMode.KEYBOARD)
            svc.start()
            capture = await asyncio.to_thread(keyboard_capture.start)
        except VisualizationSyncError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "ok": True,
            "manual": manual,
            "visualization": visualization,
            "keyboard_capture": capture.to_dict(),
            "status": _status_to_dict(svc, keyboard_capture),
        }

    @app.post("/api/control/input")
    async def api_control_input(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        try:
            manual = svc.set_manual_input(body)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True, "manual": manual, "status": _status_to_dict(svc, keyboard_capture)}

    @app.post("/api/control/keyboard/stop")
    async def api_keyboard_stop() -> Dict[str, Any]:
        try:
            capture = await asyncio.to_thread(keyboard_capture.stop)
            manual = svc.set_manual_input({"roll": 0, "pitch": 0, "yaw": 0, "throttle": 0})
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "ok": True,
            "manual": manual,
            "keyboard_capture": capture.to_dict(),
            "status": _status_to_dict(svc, keyboard_capture),
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
        return _status_to_dict(svc, keyboard_capture)

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
        return _status_to_dict(svc, keyboard_capture)

    @app.post("/api/service/start")
    async def api_start(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        mode = body.get("mode")
        if mode:
            try:
                svc.set_clock_mode(ClockMode(str(mode)))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        svc.start()
        return _status_to_dict(svc, keyboard_capture)

    @app.post("/api/service/stop")
    async def api_stop() -> Dict[str, Any]:
        keyboard_capture.stop()
        svc.set_manual_input({"roll": 0, "pitch": 0, "yaw": 0, "throttle": 0})
        svc.stop()
        return _status_to_dict(svc, keyboard_capture)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
