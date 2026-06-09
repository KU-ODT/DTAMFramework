"""DTAM Server Emulator FastAPI 서버.

- `/` 로 GUI 제공 (app/web/index.html)
- REST: 상태 스냅샷, 모듈 endpoint 수정, 수동 push
- WebSocket `/ws/events`: hub 의 TrafficEvent 를 실시간 브로드캐스트
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import (
    DTAM_SDK_ROOT,
    FRAMEWORK_ROOT,
    MESSAGE_TABLE,
    WEB_DIR,
    ServerConfig,
    load_config,
)
from .hub import ServerHub, TrafficEvent

logger = logging.getLogger(__name__)

# sequence_diagram.json 위치 — odt_Integration 의 것을 재사용
SEQUENCE_DIAGRAM_PATH = FRAMEWORK_ROOT / "odt_Integration" / "static" / "data" / "sequence_diagram.json"


def create_app(config: Optional[ServerConfig] = None) -> FastAPI:
    cfg = config or load_config()
    hub = ServerHub(cfg)
    event_loop: Optional[asyncio.AbstractEventLoop] = None
    clients: Set[WebSocket] = set()

    app = FastAPI(title="DTAM Server Emulator")
    app.state.hub = hub
    app.state.config = cfg

    @app.on_event("startup")
    async def _startup() -> None:
        nonlocal event_loop
        event_loop = asyncio.get_running_loop()

        def _broadcast(evt: TrafficEvent) -> None:
            loop = event_loop
            if loop is None:
                return
            data = evt.to_dict()
            for ws in list(clients):
                try:
                    asyncio.run_coroutine_threadsafe(
                        ws.send_json({"type": "traffic", **data}),
                        loop,
                    )
                except Exception:
                    logger.exception("ws broadcast failed")

        hub.on_event = _broadcast
        hub.start()
        print(f"[DSE] hub started — UDP {cfg.server.bind_ip}:{cfg.server.udp_port} / "
              f"TCP {cfg.server.bind_ip}:{cfg.server.tcp_port}")
        print(f"[DSE] Database session: {hub.db.session_dir}")

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        hub.on_event = None
        hub.stop()
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

    @app.get("/api/sequence-diagram")
    async def get_sequence_diagram() -> Response:
        if not SEQUENCE_DIAGRAM_PATH.is_file():
            return JSONResponse({"actors": [], "messages": []})
        return Response(
            content=SEQUENCE_DIAGRAM_PATH.read_text(encoding="utf-8"),
            media_type="application/json",
        )

    # ── 상태 스냅샷 ───────────────────────────────────────────
    @app.get("/api/state")
    async def api_state() -> JSONResponse:
        return JSONResponse(hub.snapshot())

    @app.get("/api/modules")
    async def api_modules() -> JSONResponse:
        return JSONResponse(hub.snapshot()["registry"])

    @app.get("/api/db/stats")
    async def api_db_stats() -> JSONResponse:
        return JSONResponse(hub.db.stats())

    @app.get("/api/db/messages/{mid}/latest")
    async def api_db_latest_message(
        mid: str,
        field: Optional[str] = None,
        value: Optional[str] = None,
    ) -> JSONResponse:
        event = hub.db.find_latest_event(mid, field=field, value=value)
        if event is None:
            return JSONResponse(
                {
                    "ok": False,
                    "mid": mid,
                    "error": "message payload not found",
                },
                status_code=404,
            )
        return JSONResponse({"ok": True, **event})

    @app.post("/api/db/open-folder")
    async def api_db_open_folder() -> JSONResponse:
        folder = Path(hub.db.session_dir).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if hasattr(os, "startfile"):
                os.startfile(folder)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse({"ok": True, "folder_path": str(folder)})

    # ── 모듈 endpoint 수정 ────────────────────────────────────
    @app.patch("/api/modules/{role}")
    async def api_module_patch(role: str, request: Request) -> JSONResponse:
        body = await request.json()
        ip = body.get("ip")
        udp_port = body.get("udp_port") or body.get("port")
        tcp_port = body.get("tcp_port")
        expected_source = body.get("expected_source")
        info = hub.update_module_endpoint(
            role,
            ip=str(ip) if ip else None,
            udp_port=int(udp_port) if udp_port is not None else None,
            tcp_port=int(tcp_port) if tcp_port is not None else None,
            expected_source=str(expected_source) if expected_source is not None else None,
        )
        if info is None:
            return JSONResponse({"error": f"unknown role {role}"}, status_code=404)
        return JSONResponse(info)

    # ── 수동 push (디버그/ops 용) ────────────────────────────
    @app.post("/api/push/{mid}")
    async def api_push(mid: str, request: Request) -> JSONResponse:
        body = await request.json() if await _has_json_body(request) else {}
        role = str(body.get("role") or "").strip()
        payload = body.get("payload") or {}
        if role:
            try:
                hub.db.write_event(mid, payload)
            except Exception:
                logger.exception("Database write failed for api push %s", mid)
            result = hub.push_to_role(role, mid, payload)
        else:
            # 예약된 메시지면 스케줄 로직 재사용
            result = hub.push_scheduled_mid(mid)
        return JSONResponse(result)

    # ── WebSocket — 실시간 이벤트 ────────────────────────────
    @app.websocket("/ws/events")
    async def ws_events(websocket: WebSocket) -> None:
        await websocket.accept()
        clients.add(websocket)
        try:
            # 초기 스냅샷 전송
            await websocket.send_json({"type": "snapshot", **hub.snapshot()})
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg.get("type") == "snapshot":
                    await websocket.send_json({"type": "snapshot", **hub.snapshot()})
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(websocket)

    return app


async def _has_json_body(request: Request) -> bool:
    ctype = request.headers.get("content-type") or ""
    return "json" in ctype.lower()


__all__ = ["create_app"]
