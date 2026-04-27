"""DTAM Simulation State FastAPI 앱 팩토리.

세션 서버로서 실제 데이터 통신(UDP/TCP/WS)과 DB 로깅, 시뮬레이션 엔진(시간)을 관리합니다.
"""
from __future__ import annotations

import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from DTAM_CoreServer.app.model.config import ServerConfig
from DTAM_CoreServer.app.model.message import PHASE_INFO, phase_tag
from .service.hub import ServerHub
from .database.file_db import DtamFileDb
from .service.engine import SimulationEngine
from .router import ws_dtam, ws_events, push, state

logger = logging.getLogger("sim_state.server")

def _build_tags_metadata():
    tags = []
    for phase_num in sorted(PHASE_INFO.keys()):
        info = PHASE_INFO[phase_num]
        tags.append({
            "name": phase_tag(phase_num),
            "description": f"**{info['name_en']}** — {info['description']}",
        })
    tags.extend([
        {"name": "상태 관리", "description": "State 및 시스템 관리"},
    ])
    return tags

def create_app(config: ServerConfig, db_root: str) -> FastAPI:
    app = FastAPI(
        title="DTAM Simulation State Server",
        version="2.0.0",
        description="시뮬레이션 인게임 통신/데이터 관리 서버",
        openapi_tags=_build_tags_metadata(),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    hub = ServerHub(config)
    app.state.hub = hub
    db = DtamFileDb(db_root)
    engine = SimulationEngine(hub) # 엔진이 직접 허브를 통해 메시지를 보낼 수 있도록 의존성 주입

    # 라우터 등록
    app.include_router(ws_dtam.router)
    app.include_router(ws_events.router)
    app.include_router(push.router)
    app.include_router(state.router)

    clients = ws_events.gui_clients

    @app.on_event("startup")
    async def _startup() -> None:
        loop = asyncio.get_running_loop()
        hub.set_event_loop(loop)
        
        # 허브에서 수신한 메시지를 DB에 기록 및 제어 명령 처리, 그리고 GUI에 브로드캐스트
        def on_event(evt):
            # 1. DB 기록
            if evt.kind == "rx" or evt.mid in ("0003",):
                try:
                    # payload_preview 대신 실제 데이터를 저장해야 하지만
                    # 현재 구조상 hub에서 파일 저장을 위해 on_event로 전달받습니다.
                    db.write_event(evt.mid, evt.payload_preview or {}, extra_bytes=b"")
                except Exception as e:
                    logger.error(f"DB write error: {e}")
                    
            # 엔진 제어 명령 처리 (1002 Simulation Setup)
            if evt.mid == "1002":
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
                    logger.info(f"[AUTO-TRIGGER] Play Button Pressed. Sending Execute Command (2002) to mission & vehicle...")
                    hub.push_to_role("mission", "2002", {"timestamp": evt.ts_iso or "", "flightPlanFolderName": "auto_sync"})
                    hub.push_to_role("vehicle", "2002", {"timestamp": evt.ts_iso or "", "flightPlanFolderName": "auto_sync"})
                elif action in ("pause", "stop", "reset"):
                    engine.stop_clock()

            # [NEW] 1001(모드 설정) 수신 시 Mission Planner에게 2001(비행계획 요청) 자동 트리거
            if evt.mid == "1001":
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
                        "timestamp": evt.ts_iso or "",
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

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        hub.on_event = None
        hub.stop()
        engine.stop_clock()

    return app

__all__ = ["create_app"]
