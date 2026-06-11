"""DTAM Simulation State FastAPI factory.

Hosts WebSocket data communication, file DB logging, simulation time control, and the live monitor UI.
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from IntegrationHub.CoreServerModule.app.model.config import ServerConfig
from IntegrationHub.CoreServerModule.app.model.message import PHASE_INFO, phase_tag
from .config import WEB_DIR
from .services.hub import ServerHub
from .database.file_db import DtamFileDb
from .services.engine import SimulationEngine
from .routes import ws_dtam, ws_events, push, state
from .routes import db as db_router
from .routes import sequence as sequence_router
from .routes import ws_docs as ws_docs_router
from .routes import camera as camera_router

logger = logging.getLogger("sim_state.server")

# High-rate telemetry is forwarded in real time over WebSocket.  Persisting every
# frame synchronously on the event loop makes the data plane fall behind after a
# few minutes, so the file DB keeps only a throttled latest snapshot for these
# streams.
DB_WRITE_MIN_INTERVAL_S = {
    "4001": 0.25,
    "4101": 1.0,
    "5001": 0.25,
}
DB_WRITE_QUEUE_MAX = 256

GUI_EVENT_MIN_INTERVAL_S = {
    "0002": 0.5,
    "4001": 0.25,
    "4101": 1.0,
    "5001": 0.25,
}

def _event_iso_timestamp(evt, payload) -> str:
    value = None
    if hasattr(payload, "timestamp"):
        value = getattr(payload, "timestamp", None)
    elif isinstance(payload, dict):
        value = payload.get("timestamp")
    if value:
        return str(value)
    try:
        ts = float(getattr(evt, "ts", 0.0) or 0.0)
    except (TypeError, ValueError):
        ts = 0.0
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def _build_tags_metadata():
    tags = []
    for phase_num in sorted(PHASE_INFO.keys()):
        info = PHASE_INFO[phase_num]
        tags.append({
            "name": phase_tag(phase_num),
            "description": f"**{info['name_en']}** - {info['description']}",
        })
    tags.extend([
        {"name": "Server Status", "description": "Module, traffic, endpoint, and heartbeat state."},
        {"name": "Database", "description": "File DB statistics, recent payloads, and DB folders."},
        {"name": "Camera", "description": "MJPEG stream for the latest 4101 camera frame by vehicle."},
        {"name": "WebSocket Docs", "description": "Standalone /ws/dtam protocol documentation."},
    ])
    return tags

def create_app(config: ServerConfig, db_root: str) -> FastAPI:
    app = FastAPI(
        title="DTAM Simulation State Server",
        version="2.0.0",
        description=(
            "## DTAM Simulation State (data plane)\n\n"
            "Handles DTAM simulation data communication.\n\n"
            "### Communication methods\n"
            "- **WebSocket `/ws/dtam`**: ICD messages between modules and the state server.\n"
            "- **WebSocket `/ws/events`**: real-time traffic stream for the live monitor GUI.\n"
            "- **REST `POST /api/msg/{mid}`**: send one ICD message from scripts or Swagger UI.\n"
            "- **REST `GET /api/state`, `/api/modules`, `/api/db/*`**: inspect state and DB data.\n"
            "- **REST `POST /api/heartbeat`**: inject a heartbeat for debugging.\n\n"
            "### Live monitor\n"
            "Open [`/`](/) to see sequence-diagram-style real-time traffic.\n\n"
            "### Phase-based message flow\n"
            "Messages are grouped by phase and can be sent through `POST /api/msg/{mid}`.\n"
        ),
        openapi_tags=_build_tags_metadata(),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_origin_regex="http://.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    hub = ServerHub(config)
    app.state.hub = hub
    db = DtamFileDb(db_root)
    app.state.db = db
    engine = SimulationEngine(hub)  # Inject hub so the engine can publish messages directly.

    # Registration handling
    app.include_router(ws_dtam.router)
    app.include_router(ws_events.router)
    app.include_router(push.router)
    app.include_router(state.router)
    app.include_router(db_router.router)
    app.include_router(sequence_router.router)
    app.include_router(ws_docs_router.router)
    app.include_router(camera_router.router)

    # Registration handling
    if (WEB_DIR / "css").is_dir():
        app.mount("/css", StaticFiles(directory=str(WEB_DIR / "css")), name="css")
    if (WEB_DIR / "js").is_dir():
        app.mount("/js", StaticFiles(directory=str(WEB_DIR / "js")), name="js")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index() -> HTMLResponse:
        return HTMLResponse(content=(WEB_DIR / "index.html").read_text(encoding="utf-8"))

    clients = ws_events.gui_clients

    @asynccontextmanager
    async def _lifespan(_: FastAPI):
        # Startup
        loop = asyncio.get_running_loop()
        hub.set_event_loop(loop)
        db_last_write_ts: dict[str, float] = {}
        gui_last_event_ts: dict[str, float] = {}
        db_write_queue: queue.Queue = queue.Queue(maxsize=DB_WRITE_QUEUE_MAX)
        db_stop_event = threading.Event()

        def _db_writer_loop():
            while not db_stop_event.is_set():
                try:
                    item = db_write_queue.get(timeout=0.25)
                except queue.Empty:
                    continue
                if item is None:
                    db_write_queue.task_done()
                    break
                mid, payload_to_write, extra_bytes = item
                try:
                    db.write_event(mid, payload_to_write or {}, extra_bytes=extra_bytes or b"")
                except Exception as e:
                    logger.error(f"DB write error: {e}")
                finally:
                    db_write_queue.task_done()

        db_writer = threading.Thread(
            target=_db_writer_loop,
            name="dtam-state-db-writer",
            daemon=True,
        )
        db_writer.start()

        def _enqueue_db_write(mid: str, payload_to_write, extra_bytes: bytes = b"") -> None:
            try:
                db_write_queue.put_nowait((str(mid), payload_to_write or {}, extra_bytes or b""))
            except queue.Full:
                logger.debug("DB write queue full; dropping MID %s snapshot", mid)

        # Registration handling
        def on_event(evt):
            # 1. DB logging
            payload = None
            if evt.kind == "rx" or evt.mid in ("0003",):
                min_interval_s = float(DB_WRITE_MIN_INTERVAL_S.get(str(evt.mid), 0.0) or 0.0)
                if min_interval_s > 0.0:
                    now_mono = time.monotonic()
                    last_mono = float(db_last_write_ts.get(str(evt.mid), 0.0) or 0.0)
                    if now_mono - last_mono < min_interval_s:
                        should_write_db = False
                    else:
                        db_last_write_ts[str(evt.mid)] = now_mono
                        should_write_db = True
                else:
                    should_write_db = True

                if not should_write_db:
                    payload = None
                else:
                    payload = evt.full_payload if isinstance(evt.full_payload, dict) else evt.payload_preview

            if (evt.kind == "rx" or evt.mid in ("0003",)) and payload is not None:
                _enqueue_db_write(evt.mid, payload, evt.extra_bytes or b"")
                    
            # Registration handling
            is_local_state_command = (
                evt.peer_role == "sim_state"
                and evt.proto == "local"
                and evt.note == "local sink"
            )

            if is_local_state_command and evt.mid == "1002":
                payload = evt.full_payload
                engine.apply_control(payload)

            # (제거됨 2026-06-11) 1001 수신 시 2001 자동 발사 — 2001 은 콘솔 Play
            # 사슬(user)·PSU 만 발행한다. 자동 발사는 scenarioFileName 이 없는 가짜
            # 2001 ("default_scenario.json") 을 만들어 Mission 에러를 유발했고,
            # "2001 은 런당 1회" 규칙도 위반했다.

            # Registration handling
            if loop is None or not clients:
                return
            gui_min_interval_s = float(GUI_EVENT_MIN_INTERVAL_S.get(str(evt.mid), 0.0) or 0.0)
            if gui_min_interval_s > 0.0:
                now_mono = time.monotonic()
                last_mono = float(gui_last_event_ts.get(str(evt.mid), 0.0) or 0.0)
                if now_mono - last_mono < gui_min_interval_s:
                    return
                gui_last_event_ts[str(evt.mid)] = now_mono
            data = {"type": "traffic", **evt.to_dict()}
            dead = []
            for ws in list(clients):
                try:
                    asyncio.run_coroutine_threadsafe(ws.send_json(data), loop)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                clients.discard(ws)

        hub.on_event = on_event
        hub.start()

        # Registration handling
        async def _self_heartbeat_loop():
            while hub._running:
                # Registration handling
                hub.registry.heartbeat({"source": "StateServerModule"})
                await asyncio.sleep(1.0)

        asyncio.create_task(_self_heartbeat_loop())

        try:
            yield
        finally:
            # Shutdown
            hub.on_event = None
            db_stop_event.set()
            try:
                db_write_queue.put_nowait(None)
            except queue.Full:
                pass
            db_writer.join(timeout=2.0)
            hub.stop()
            engine.stop_clock()

    app.router.lifespan_context = _lifespan
    return app

__all__ = ["create_app"]
