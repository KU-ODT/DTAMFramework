"""DTAM Simulation State FastAPI 앱 팩토리.

세션 서버로서 WebSocket 데이터 통신(``/ws/dtam``)과 DB 로깅, 시뮬레이션 엔진(시간)을 관리합니다.
또한 라이브 모니터 웹 UI 를 ``/`` 에 호스팅합니다 (자기 자신의 ``/ws/events`` 와 same-origin).
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from DTAM_CoreServer.app.model.config import ServerConfig
from DTAM_CoreServer.app.model.message import PHASE_INFO, phase_tag
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
            "description": f"**{info['name_en']}** — {info['description']}",
        })
    tags.extend([
        {"name": "📊 서버 상태", "description": "모듈 / 트래픽 / 모듈 endpoint / heartbeat 조회·수정"},
        {"name": "💾 데이터베이스", "description": "파일 DB 통계, 메시지별 최근 페이로드, DB 폴더 열기"},
        {"name": "📹 카메라", "description": "4101 이 적재한 vehicle 카메라 프레임을 MJPEG 으로 스트림"},
        {"name": "📡 WebSocket 문서", "description": "/ws/dtam 프로토콜 별도 HTML 문서 (Swagger 가 WS 를 직접 테스트 불가)"},
    ])
    return tags

def create_app(config: ServerConfig, db_root: str) -> FastAPI:
    app = FastAPI(
        title="DTAM Simulation State Server",
        version="2.0.0",
        description=(
            "## DTAM Simulation State (data plane)\n\n"
            "시뮬레이션 세션의 데이터·통신·DB 를 담당합니다.\n\n"
            "### 통신 방식\n"
            "- **WebSocket `/ws/dtam`** — 모듈 ↔ 서버 ICD 메시지 송수신 ([프로토콜 문서](/docs/websocket))\n"
            "- **WebSocket `/ws/events`** — 라이브 모니터 GUI 실시간 트래픽 stream\n"
            "- **REST `POST /api/msg/{mid}`** — 운영자/스크립트 단발 ICD 송신 (이 페이지에서 직접 테스트 가능)\n"
            "- **REST `GET  /api/state` / `/api/modules` / `/api/db/*`** — 단발 조회\n"
            "- **REST `POST /api/heartbeat`** — 강제 heartbeat 주입\n\n"
            "### 라이브 모니터\n"
            "[`/`](/) 페이지에서 시퀀스 다이어그램 위로 흐르는 메시지를 실시간 확인.\n\n"
            "### Phase 기반 메시지 흐름\n"
            "각 메시지는 시퀀스 다이어그램의 Phase 별로 그룹화. `POST /api/msg/{mid}` 로 송신.\n"
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
    engine = SimulationEngine(hub) # 엔진이 직접 허브를 통해 메시지를 보낼 수 있도록 의존성 주입

    # 라우터 등록
    app.include_router(ws_dtam.router)
    app.include_router(ws_events.router)
    app.include_router(push.router)
    app.include_router(state.router)
    app.include_router(db_router.router)
    app.include_router(sequence_router.router)
    app.include_router(ws_docs_router.router)
    app.include_router(camera_router.router)

    # 라이브 모니터 웹 UI (same-origin)
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
        # ── startup ───────────────────────────────────────────
        loop = asyncio.get_running_loop()
        hub.set_event_loop(loop)

        # 허브에서 수신한 메시지를 DB에 기록 및 제어 명령 처리, 그리고 GUI에 브로드캐스트
        def on_event(evt):
            # 1. DB 기록
            if evt.kind == "rx" or evt.mid in ("0003",):
                try:
                    # payload_preview 대신 실제 데이터를 저장해야 하지만
                    # 현재 구조상 hub에서 파일 저장을 위해 on_event로 전달받습니다.
                    payload = evt.full_payload if isinstance(evt.full_payload, dict) else evt.payload_preview
                    db.write_event(evt.mid, payload or {}, extra_bytes=evt.extra_bytes or b"")
                except Exception as e:
                    logger.error(f"DB write error: {e}")
                    
            # 엔진 제어 명령 처리 (1002 Simulation Setup)
            is_local_state_command = (
                evt.peer_role == "sim_state"
                and evt.proto == "local"
                and evt.note == "local sink"
            )

            if is_local_state_command and evt.mid == "1002":
                payload = evt.full_payload
                # payload가 dataclass 객체일 수 있으므로 getattr 사용, 아니면 dict.get 사용
                def get_val(obj, key):
                    if hasattr(obj, key): return getattr(obj, key)
                    if isinstance(obj, dict): return obj.get(key)
                    return None

                action = str(get_val(payload, "playState") or get_val(payload, "action") or "").lower()
                if action == "play":
                    engine.start_clock()
                    # [NEW] Play 시 2002(DTAM Execute)를 필요한 모든 모듈에 자동 브로드캐스트하여 즉시 비행 시작 유도
                    logger.info("[SIM] 1002 play received; simulation clock started")
                elif action in ("pause", "stop", "reset"):
                    engine.stop_clock()

            # [NEW] 1001(모드 설정) 수신 시 Mission Planner에게 2001(비행계획 요청) 자동 트리거
            if is_local_state_command and evt.mid == "1001":
                try:
                    payload = evt.full_payload
                    def get_val(obj, key):
                        if hasattr(obj, key): return getattr(obj, key)
                        if isinstance(obj, dict): return obj.get(key)
                        return None
                    
                    # 시나리오 파일명이 있으면 전달, 없으면 기본값
                    scenario = get_val(payload, "traffic")
                    scenario_file = get_val(scenario, "trafficScenario") if scenario else "default_scenario.json"
                    
                    req_2001 = {
                        "timestamp": _event_iso_timestamp(evt, payload),
                        "scenarioFileName": scenario_file or "default_scenario.json"
                    }
                    # Mission Planner에게 2001 전송
                    hub.push_to_role("mission", "2001", req_2001)
                    logger.info(f"Auto-triggered 2001 Flight Plan Request for scenario: {scenario_file}")
                except Exception as e:
                    logger.error(f"Auto-trigger 2001 failed: {e}")
                    
            # 3. GUI 브로드캐스트
            if loop is None or not clients:
                return
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

        # [NEW] 상태 서버 자체 하트비트 루프 (상태 서버가 살아있음을 레지스트리에 표시)
        async def _self_heartbeat_loop():
            while hub._running:
                # 자기 자신(sim_state) 하트비트 갱신
                hub.registry.heartbeat({"source": "DTAM_SimulationState"})
                await asyncio.sleep(1.0)

        asyncio.create_task(_self_heartbeat_loop())

        try:
            yield
        finally:
            # ── shutdown ──────────────────────────────────────
            hub.on_event = None
            hub.stop()
            engine.stop_clock()

    app.router.lifespan_context = _lifespan
    return app

__all__ = ["create_app"]
