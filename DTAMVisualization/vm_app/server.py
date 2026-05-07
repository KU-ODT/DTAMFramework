"""DTAM Visualization Manager FastAPI 서버.

- `/` → HTML GUI
- REST: AirSim connect/disconnect, DTAM endpoint reconfigure, streaming 제어, 수동 capture
- WebSocket `/ws/events` → Manager 이벤트 실시간 브로드캐스트
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import VMConfig, WEB_DIR, load_config
from .manager import HubEvent, VisualizationManager

logger = logging.getLogger(__name__)


def create_app(config: Optional[VMConfig] = None) -> FastAPI:
    cfg = config or load_config()
    manager = VisualizationManager(cfg)
    clients: Set[WebSocket] = set()
    event_loop: Optional[asyncio.AbstractEventLoop] = None

    app = FastAPI(title="DTAM Visualization Manager")
    app.state.manager = manager
    app.state.config = cfg

    @app.on_event("startup")
    async def _startup() -> None:
        nonlocal event_loop
        event_loop = asyncio.get_running_loop()

        def _broadcast(evt: HubEvent) -> None:
            loop = event_loop
            if loop is None:
                return
            data = evt.to_dict()
            for ws in list(clients):
                try:
                    asyncio.run_coroutine_threadsafe(
                        ws.send_json({"type": "event", **data}),
                        loop,
                    )
                except Exception:
                    pass

        manager.on_event = _broadcast
        manager.start()
        ep = cfg.dtam
        print(f"[DTAM VM] DTAM server   ws://{ep.server_ip}:{ep.server_port}/ws/dtam")
        print(f"[DTAM VM] AirSim target {cfg.airsim.host}:{cfg.airsim.port}")

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        manager.on_event = None
        manager.stop()
        for ws in list(clients):
            try:
                await ws.close()
            except Exception:
                pass
        clients.clear()

    # ── 정적 ─────────────────────────────────────────────────
    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(content=(WEB_DIR / "index.html").read_text(encoding="utf-8"))

    app.mount("/css", StaticFiles(directory=str(WEB_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(WEB_DIR / "js")), name="js")

    # ── 상태 ────────────────────────────────────────────────
    @app.get("/api/state")
    async def api_state() -> JSONResponse:
        return JSONResponse(manager.snapshot())

    # ── AirSim 제어 ─────────────────────────────────────────
    @app.post("/api/airsim/connect")
    async def api_airsim_connect(request: Request) -> JSONResponse:
        body: Dict[str, Any] = {}
        if _has_json(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
        host = body.get("host")
        port = body.get("port")
        status = manager.connect_airsim(
            host=str(host) if host else None,
            port=int(port) if port is not None else None,
        )
        return JSONResponse(status)

    @app.post("/api/airsim/disconnect")
    async def api_airsim_disconnect() -> JSONResponse:
        return JSONResponse(manager.disconnect_airsim())

    @app.get("/api/airsim/vehicles")
    async def api_airsim_vehicles() -> JSONResponse:
        return JSONResponse(manager.list_airsim_vehicles())

    @app.patch("/api/airsim/vehicle-map")
    async def api_vehicle_map(request: Request) -> JSONResponse:
        body = await request.json()
        mapping = {str(k): str(v) for k, v in (body or {}).items()}
        return JSONResponse(manager.update_vehicle_map(mapping))

    @app.post("/api/airsim/capture-once")
    async def api_capture_once() -> JSONResponse:
        return JSONResponse(manager.capture_camera_once())

    @app.post("/api/airsim/mission-guides")
    async def api_mission_guides(request: Request) -> JSONResponse:
        body: Dict[str, Any] = {}
        if _has_json(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
        action = str(body.get("action") or "").strip().lower()
        if action == "toggle":
            result = manager.toggle_mission_guides()
        elif action in ("hide", "off"):
            result = manager.set_mission_guides_visible(False)
        elif action in ("show", "on", ""):
            result = manager.set_mission_guides_visible(True)
        else:
            return JSONResponse({"ok": False, "error": f"unsupported action: {action}"}, status_code=400)
        return JSONResponse(result, status_code=200 if not result.get("errors") else 400)

    @app.post("/api/airsim/camera/control")
    async def api_camera_control(request: Request) -> JSONResponse:
        body: Dict[str, Any] = {}
        if _has_json(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
        result = manager.control_camera(
            camera_name=str(body.get("camera_name") or "front_center"),
            vehicle_name=str(body.get("vehicle_name") or ""),
            yaw_delta_deg=float(_as_float(body.get("yaw_delta_deg")) or 0.0),
            pitch_delta_deg=float(_as_float(body.get("pitch_delta_deg")) or 0.0),
            focal_length_delta=float(_as_float(body.get("focal_length_delta")) or 0.0),
        )
        return JSONResponse(result, status_code=200 if result.get("ok") else 400)

    @app.post("/api/unreal/launch")
    async def api_unreal_launch() -> JSONResponse:
        status = manager.launch_unreal()
        return JSONResponse(status, status_code=200 if status.get("ok", True) else 404)

    # ── DTAM 제어 ───────────────────────────────────────────
    @app.patch("/api/dtam/endpoint")
    async def api_dtam_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        ep = manager.reconfigure_dtam(
            server_ip=body.get("server_ip"),
            server_port=int(body["server_port"]) if body.get("server_port") is not None else None,
        )
        return JSONResponse(ep)

    @app.patch("/api/streaming")
    async def api_streaming(request: Request) -> JSONResponse:
        body = await request.json()
        out = manager.update_streaming(
            module_status_hz=_as_float(body.get("module_status_hz")),
            camera_enabled=_as_bool(body.get("camera_enabled")),
            camera_name=body.get("camera_name"),
            camera_image_type=_as_int(body.get("camera_image_type")),
            camera_hz=_as_float(body.get("camera_hz")),
            camera_quality=_as_int(body.get("camera_quality")),
            camera_vehicle=body.get("camera_vehicle"),
        )
        return JSONResponse(out)

    # ── WebSocket ───────────────────────────────────────────
    @app.websocket("/ws/events")
    async def ws_events(websocket: WebSocket) -> None:
        await websocket.accept()
        clients.add(websocket)
        try:
            await websocket.send_json({"type": "snapshot", **manager.snapshot()})
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg.get("type") == "snapshot":
                    await websocket.send_json({"type": "snapshot", **manager.snapshot()})
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(websocket)

    return app


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return None


def _has_json(request: Request) -> bool:
    ctype = request.headers.get("content-type") or ""
    return "json" in ctype.lower()


__all__ = ["create_app"]
