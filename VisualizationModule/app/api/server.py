"""DTAM Visualization Manager FastAPI server.

- ``/`` serves the HTML GUI.
- REST APIs expose AirSim connect/disconnect, DTAM endpoint changes,
  streaming controls, manual capture, mission guide visibility, and Unreal launch.
- WebSocket ``/ws/events`` broadcasts manager events in real time.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Set

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..config import VMConfig, WEB_DIR, load_config
from ..services.manager import HubEvent, VisualizationManager

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

    # Static GUI
    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(content=(WEB_DIR / "index.html").read_text(encoding="utf-8"))

    app.mount("/css", StaticFiles(directory=str(WEB_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(WEB_DIR / "js")), name="js")

    # State
    @app.get("/api/state")
    async def api_state() -> JSONResponse:
        return JSONResponse(await asyncio.to_thread(manager.snapshot))

    @app.get("/api/health")
    async def api_health() -> JSONResponse:
        return JSONResponse(await asyncio.to_thread(manager.health_snapshot))

    @app.get("/api/performance")
    async def api_performance() -> JSONResponse:
        return JSONResponse(manager.performance_snapshot())

    @app.get("/api/settings/performance")
    async def api_get_performance_settings() -> JSONResponse:
        return JSONResponse(manager.runtime_optimization_settings())

    @app.patch("/api/settings/performance")
    async def api_patch_performance_settings(request: Request) -> JSONResponse:
        body: Dict[str, Any] = {}
        if _has_json(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
        result = manager.update_runtime_optimization(
            vehicle_status_apply_hz=_as_float(body.get("vehicle_status_apply_hz")),
            vehicle_status_apply_hz_by_vehicle_count=(
                body.get("vehicle_status_apply_hz_by_vehicle_count")
                if isinstance(body.get("vehicle_status_apply_hz_by_vehicle_count"), list)
                else None
            ),
            telemetry_hz=_as_float(body.get("telemetry_hz")),
            visual_state_hz=_as_float(body.get("visual_state_hz")),
            direct_camera_default_fps=_as_float(body.get("direct_camera_default_fps")),
            direct_camera_max_fps=_as_float(body.get("direct_camera_max_fps")),
            teststream_default_fps=_as_float(body.get("teststream_default_fps")),
            collision_poll_hz=_as_float(body.get("collision_poll_hz")),
            pose_feedback_check_enabled=_as_bool(body.get("pose_feedback_check_enabled")),
            pose_feedback_publish_to_server=_as_bool(body.get("pose_feedback_publish_to_server")),
            pose_feedback_recommended_action=(
                str(body.get("pose_feedback_recommended_action"))
                if body.get("pose_feedback_recommended_action") is not None
                else None
            ),
            pose_feedback_sample_hz=_as_float(body.get("pose_feedback_sample_hz")),
        )
        return JSONResponse(result)

    @app.get("/api/settings/rendering")
    async def api_get_rendering_settings() -> JSONResponse:
        return JSONResponse(manager.rendering_settings())

    @app.patch("/api/settings/rendering")
    async def api_patch_rendering_settings(request: Request) -> JSONResponse:
        body: Dict[str, Any] = {}
        if _has_json(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
        apply_runtime = _as_bool(body.get("apply_runtime"))
        if apply_runtime is None:
            apply_runtime = _as_bool(body.get("apply_now"))
        persistent = _as_bool(body.get("persistent"))
        if persistent is None:
            persistent = _as_bool(body.get("persist"))
        apply_cesium_runtime = _as_bool(body.get("apply_cesium_runtime"))
        runtime_scope = str(body.get("runtime_scope") or body.get("apply_runtime_scope") or "all")
        result = manager.update_rendering_settings(
            body,
            preset=str(body.get("preset")) if body.get("preset") is not None else None,
            apply_runtime=bool(apply_runtime),
            apply_cesium_runtime=apply_cesium_runtime,
            runtime_scope=runtime_scope,
            persistent=bool(persistent),
        )
        return JSONResponse(result)

    # Backward-friendly alias for UI experiments that use "visual quality" wording.
    @app.get("/api/settings/visual-quality")
    async def api_get_visual_quality_settings() -> JSONResponse:
        return JSONResponse(manager.rendering_settings())

    @app.patch("/api/settings/visual-quality")
    async def api_patch_visual_quality_settings(request: Request) -> JSONResponse:
        body: Dict[str, Any] = {}
        if _has_json(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
        apply_runtime = _as_bool(body.get("apply_runtime"))
        if apply_runtime is None:
            apply_runtime = _as_bool(body.get("apply_now"))
        persistent = _as_bool(body.get("persistent"))
        if persistent is None:
            persistent = _as_bool(body.get("persist"))
        apply_cesium_runtime = _as_bool(body.get("apply_cesium_runtime"))
        runtime_scope = str(body.get("runtime_scope") or body.get("apply_runtime_scope") or "all")
        result = manager.update_rendering_settings(
            body,
            preset=str(body.get("preset")) if body.get("preset") is not None else None,
            apply_runtime=bool(apply_runtime),
            apply_cesium_runtime=apply_cesium_runtime,
            runtime_scope=runtime_scope,
            persistent=bool(persistent),
        )
        return JSONResponse(result)

    # AirSim / Unreal control
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
        parsed_port = _as_int(port)
        if port is not None and parsed_port is None:
            raise HTTPException(status_code=400, detail="port must be an integer")
        status = manager.connect_airsim(
            host=str(host) if host else None,
            port=parsed_port,
        )
        return JSONResponse(status)

    @app.post("/api/airsim/disconnect")
    async def api_airsim_disconnect() -> JSONResponse:
        return JSONResponse(manager.disconnect_airsim())

    @app.get("/api/airsim/vehicles")
    async def api_airsim_vehicles() -> JSONResponse:
        return JSONResponse(await asyncio.to_thread(manager.list_airsim_vehicles))

    @app.patch("/api/airsim/vehicle-map")
    async def api_vehicle_map(request: Request) -> JSONResponse:
        body = await request.json()
        mapping = {str(k): str(v) for k, v in (body or {}).items()}
        return JSONResponse(manager.update_vehicle_map(mapping))

    @app.get("/api/airsim/collision-mode")
    async def api_get_collision_mode() -> JSONResponse:
        state = manager.snapshot()
        return JSONResponse({
            "ignore_collisions": bool((state.get("airsim_config") or {}).get("ignore_collisions")),
            "collision_mode": "teleport" if bool((state.get("airsim_config") or {}).get("ignore_collisions")) else "sweep",
            "collision_poll_hz": (state.get("collision") or {}).get("target_hz"),
            "pose_feedback_check_enabled": bool((state.get("collision") or {}).get("pose_feedback_check_enabled")),
            "pose_feedback_publish_to_server": bool((state.get("collision") or {}).get("pose_feedback_publish_to_server")),
            "pose_feedback_recommended_action": (state.get("collision") or {}).get("pose_feedback_recommended_action"),
            "pose_feedback_error_threshold_m": (state.get("collision") or {}).get("pose_feedback_error_threshold_m"),
            "pose_feedback_sample_hz": (state.get("collision") or {}).get("pose_feedback_sample_hz"),
            "persistent": False,
        })

    @app.patch("/api/airsim/collision-mode")
    async def api_collision_mode(request: Request) -> JSONResponse:
        body: Dict[str, Any] = {}
        if _has_json(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
        result = manager.update_collision_mode(
            ignore_collisions=_as_bool(body.get("ignore_collisions")),
            collision_poll_hz=_as_float(body.get("collision_poll_hz")),
            pose_feedback_check_enabled=_as_bool(body.get("pose_feedback_check_enabled")),
            pose_feedback_publish_to_server=_as_bool(body.get("pose_feedback_publish_to_server")),
            pose_feedback_recommended_action=(
                str(body.get("pose_feedback_recommended_action"))
                if body.get("pose_feedback_recommended_action") is not None
                else None
            ),
            pose_feedback_error_threshold_m=_as_float(body.get("pose_feedback_error_threshold_m")),
            pose_feedback_sample_hz=_as_float(body.get("pose_feedback_sample_hz")),
        )
        return JSONResponse(result)

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

    @app.get("/api/media/stream")
    async def api_media_stream(
        request: Request,
        vehicle_id: str = "UAM0001",
        vehicle_name: str = "",
        camera_name: str = "front_center",
        image_type: int = 0,
        fps: Optional[float] = None,
        quality: int = 60,
    ) -> StreamingResponse:
        """Direct low-load MJPEG media-plane stream.

        This endpoint intentionally bypasses IntegrationHub for video bytes.
        Discovery/audit can still be performed through MSG 4102, and camera
        movement should still use MSG 5002.
        """
        safe_fps = manager.direct_camera_default_fps(fps)
        safe_quality = max(10, min(95, int(quality or 60)))
        worker = manager.ensure_direct_camera_stream(
            aircraft_id=vehicle_id,
            camera_name=camera_name,
            image_type=int(image_type or 0),
            vehicle_name=vehicle_name,
            fps=safe_fps,
            quality=safe_quality,
        )

        async def generate():
            last_sequence = 0
            worker.acquire_consumer()
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    frame_obj = await asyncio.to_thread(
                        worker.wait_for_frame,
                        last_sequence,
                        max(0.5, min(2.0, 4.0 / safe_fps)),
                    )
                    if frame_obj is None:
                        continue
                    frame = frame_obj.frame
                    last_sequence = frame_obj.sequence
                    if frame:
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"Cache-Control: no-cache\r\n"
                            b"Pragma: no-cache\r\n"
                            + f"X-DTAM-Frame-Sequence: {frame_obj.sequence}\r\n".encode("ascii")
                            + f"X-DTAM-Capture-Ms: {frame_obj.capture_ms:.3f}\r\n".encode("ascii")
                            + f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
                            + frame
                            + b"\r\n"
                        )
            finally:
                worker.release_consumer()

        return StreamingResponse(
            generate(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get("/api/media/probe")
    async def api_media_probe(
        vehicle_id: str = "UAM0001",
        vehicle_name: str = "",
        camera_name: str = "front_center",
        image_type: int = 0,
        quality: int = 60,
    ) -> JSONResponse:
        """Capture exactly one media-plane frame and return capture metadata.

        This endpoint is for diagnosing a 4102 URL that opens but never yields
        MJPEG parts. It does not return image bytes; it only reports whether the
        VisualizationModule could obtain a JPEG from AirSim/Cosys-AirSim.
        """
        safe_quality = max(10, min(95, int(quality or 60)))
        frame, meta = await asyncio.to_thread(
            manager.capture_direct_camera_frame,
            aircraft_id=vehicle_id,
            camera_name=camera_name,
            image_type=int(image_type or 0),
            vehicle_name=vehicle_name,
            quality=safe_quality,
        )
        meta = dict(meta or {})
        meta["bytes_len"] = int(len(frame or b""))
        meta["has_jpeg_soi"] = bool(frame.startswith(b"\xff\xd8")) if frame else False
        meta["requested"] = {
            "vehicle_id": vehicle_id,
            "vehicle_name": vehicle_name,
            "camera_name": camera_name,
            "image_type": int(image_type or 0),
            "quality": safe_quality,
        }
        return JSONResponse(
            {"ok": bool(frame), "frame_available": bool(frame), "meta": meta},
            status_code=200 if frame else 503,
        )

    @app.get("/api/media/stats")
    async def api_media_stats() -> JSONResponse:
        """Return active direct-camera producer/cache stats."""
        return JSONResponse(manager.camera_stream_stats())

    @app.get("/api/vpo/camera-stream")
    async def api_vpo_camera_stream(
        request: Request,
        camera_id: str,
        fps: float = 8.0,
        quality: int = 65,
    ) -> StreamingResponse:
        """Direct MJPEG stream for one fixed VPO/vertiport SceneCapture camera."""
        safe_camera_id = str(camera_id or "").strip()
        if not safe_camera_id:
            raise HTTPException(status_code=400, detail="camera_id is required")
        safe_fps = max(0.2, min(12.0, float(fps or 8.0)))
        safe_quality = max(10, min(95, int(quality or 65)))
        worker = manager.ensure_vpo_camera_stream(
            camera_id=safe_camera_id,
            fps=safe_fps,
            quality=safe_quality,
        )

        async def generate():
            last_sequence = 0
            worker.acquire_consumer()
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    frame_obj = await asyncio.to_thread(
                        worker.wait_for_frame,
                        last_sequence,
                        max(0.5, min(2.0, 4.0 / safe_fps)),
                    )
                    if frame_obj is None:
                        continue
                    frame = frame_obj.frame
                    last_sequence = frame_obj.sequence
                    if frame:
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"Cache-Control: no-cache\r\n"
                            b"Pragma: no-cache\r\n"
                            + f"X-DTAM-Frame-Sequence: {frame_obj.sequence}\r\n".encode("ascii")
                            + f"X-DTAM-Capture-Ms: {frame_obj.capture_ms:.3f}\r\n".encode("ascii")
                            + f"X-DTAM-VPO-Camera-Id: {safe_camera_id}\r\n".encode("ascii", errors="ignore")
                            + f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
                            + frame
                            + b"\r\n"
                        )
            finally:
                worker.release_consumer()

        return StreamingResponse(
            generate(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get("/api/vpo/camera-probe")
    async def api_vpo_camera_probe(camera_id: str, quality: int = 65) -> JSONResponse:
        safe_quality = max(10, min(95, int(quality or 65)))
        frame, meta = await asyncio.to_thread(
            manager.capture_vpo_camera_frame,
            camera_id=camera_id,
            quality=safe_quality,
        )
        meta = dict(meta or {})
        meta["bytes_len"] = int(len(frame or b""))
        meta["has_jpeg_soi"] = bool(frame.startswith(b"\xff\xd8")) if frame else False
        meta["requested"] = {"camera_id": camera_id, "quality": safe_quality}
        return JSONResponse(
            {"ok": bool(frame), "frame_available": bool(frame), "meta": meta},
            status_code=200 if frame else 503,
        )

    @app.get("/api/vpo/media-stats")
    async def api_vpo_media_stats() -> JSONResponse:
        return JSONResponse(manager.vpo_camera_stream_stats())

    @app.get("/api/vpo/camera-streams")
    async def api_vpo_camera_streams(
        request: Request,
        camera_id: str,
        vertiport_id: str = "",
        vertiport_name: str = "",
        fps: float = 8.0,
        quality: int = 65,
        announce: bool = False,
    ) -> JSONResponse:
        base_url = str(request.base_url).rstrip("/")
        descriptor = manager.vpo_camera_stream_descriptor(
            base_url=base_url,
            camera_id=camera_id,
            vertiport_id=vertiport_id,
            vertiport_name=vertiport_name,
            fps=fps,
            quality=quality,
        )
        publish = None
        if announce:
            publish = manager.publish_camera_stream_descriptor(descriptor)
        return JSONResponse({"streams": [descriptor], "publish": publish})

    @app.get("/api/media/streams")
    async def api_media_streams(
        request: Request,
        vehicle_id: str = "UAM0001",
        vehicle_name: str = "",
        camera_name: str = "front_center",
        image_type: int = 0,
        fps: Optional[float] = None,
        quality: int = 60,
        announce: bool = False,
    ) -> JSONResponse:
        base_url = str(request.base_url).rstrip("/")
        descriptor = manager.camera_stream_descriptor(
            base_url=base_url,
            vehicle_id=vehicle_id,
            vehicle_name=vehicle_name,
            camera_name=camera_name,
            image_type=image_type,
            fps=manager.direct_camera_default_fps(fps),
            quality=quality,
        )
        publish = None
        if announce:
            publish = manager.publish_camera_stream_descriptor(descriptor)
        return JSONResponse({"streams": [descriptor], "publish": publish})

    @app.post("/api/media/announce")
    async def api_media_announce(request: Request) -> JSONResponse:
        body: Dict[str, Any] = {}
        if _has_json(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
        base_url = str(request.base_url).rstrip("/")
        descriptor = manager.camera_stream_descriptor(
            base_url=base_url,
            vehicle_id=str(body.get("vehicle_id") or body.get("aircraftId") or "UAM0001"),
            vehicle_name=str(body.get("vehicle_name") or body.get("vehicleName") or ""),
            camera_name=str(body.get("camera_name") or body.get("cameraName") or "front_center"),
            image_type=int(_as_int(body.get("image_type") or body.get("imageType")) or 0),
            fps=manager.direct_camera_default_fps(_as_float(body.get("fps"))),
            quality=int(_as_int(body.get("quality")) or 60),
            note=str(body.get("note") or ""),
        )
        publish = manager.publish_camera_stream_descriptor(descriptor)
        return JSONResponse({"descriptor": descriptor, "publish": publish}, status_code=200 if publish.get("ok") else 202)

    @app.post("/api/unreal/launch")
    async def api_unreal_launch(request: Request) -> JSONResponse:
        body: Dict[str, Any] = {}
        if _has_json(request):
            try:
                body = await request.json()
            except Exception:
                body = {}
        # Pixel Streaming is not the selected camera-streaming path.
        # Always launch DT World through the normal Unreal/AirSim path.
        status = await asyncio.to_thread(manager.launch_unreal, pixel_streaming=False)
        return JSONResponse(status, status_code=200 if status.get("ok", True) else 404)

    @app.post("/api/pixel-streaming/start")
    async def api_pixel_streaming_start() -> JSONResponse:
        return JSONResponse(
            {
                "ok": False,
                "disabled": True,
                "message": "Pixel Streaming is disabled. Use direct MJPEG camera streaming.",
            },
            status_code=410,
        )

    # DTAM endpoint / streaming control
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

    # WebSocket event stream
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
        normalized = value.strip().lower()
        if normalized in ("true", "1", "yes", "on"):
            return True
        if normalized in ("false", "0", "no", "off"):
            return False
        return None
    return None


def _has_json(request: Request) -> bool:
    ctype = request.headers.get("content-type") or ""
    return "json" in ctype.lower()


__all__ = ["create_app"]
