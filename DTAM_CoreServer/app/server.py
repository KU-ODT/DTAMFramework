"""DTAM Core Server FastAPI 앱 팩토리.

CoreServer 는 control plane 만 담당:
  - ICD 문서 / Phase 정보 (REST)
  - 모듈 프로세스 start/stop (REST)
  - SimulationState 자식 프로세스 라이프사이클 관리

데이터 plane (트래픽, DB, 시퀀스 다이어그램, 라이브 모니터 UI) 은
``DTAM_SimulationState`` (port 8096) 가 호스팅합니다.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import sys

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .model.config import FRAMEWORK_ROOT, ServerConfig

logger = logging.getLogger(__name__)

# 라이브 모니터는 SimulationState 가 호스팅
SIMULATION_STATE_URL = "http://127.0.0.1:8096/"


def _build_tags_metadata():
    """CoreServer 는 control plane 만 호스팅하므로 관련 태그만."""
    return [
        {"name": "🚀 프로세스 관리", "description": "모듈 프로세스(Mission, Vehicle, Visual) 시작/종료 제어"},
        {"name": "📋 ICD 문서", "description": "ICD 마크다운 문서 및 Phase 정보 조회"},
        {"name": "📊 서버 상태", "description": "시퀀스 다이어그램 메타 등 정적 자료"},
    ]


def create_app(config: ServerConfig) -> FastAPI:
    app = FastAPI(
        title="DTAM Core Server (control plane)",
        version="2.0.0",
        description=(
            "## DTAM Core Server\n\n"
            "Cloud control plane. ICD 문서, 시퀀스 다이어그램, 모듈 프로세스 라이프사이클을 담당합니다.\n\n"
            "### 책임 분리\n"
            "- **CoreServer (이 서비스, port 8095)** — REST 만. ICD/Phase 문서, 프로세스 start/stop, "
            "  부팅 시 SimulationState (data plane) 자식 프로세스 spawn.\n"
            "- **SimulationState (port 8096)** — 데이터 plane. 모든 ICD 메시지 송수신 (`/ws/dtam`), "
            "  라이브 모니터 GUI, 파일 DB. [SimulationState Swagger](http://127.0.0.1:8096/docs) · "
            "  [WebSocket 프로토콜 문서](http://127.0.0.1:8096/docs/websocket) · "
            "  [라이브 모니터](http://127.0.0.1:8096/)\n\n"
            "### 이 서비스의 endpoint 분류\n"
            "- `GET  /api/icd*` — ICD 문서/Phase 메타\n"
            "- `GET  /api/sequence-diagram` — 시퀀스 다이어그램 JSON\n"
            "- `POST /api/v1/process/{role}/{start|stop}` — 모듈 프로세스 라이프사이클\n"
        ),
        openapi_tags=_build_tags_metadata(),
    )

    # ── 라우터 등록 ──────────────────────────────────────────
    from .routes.icd import router as icd_router
    from .routes.sequence import router as sequence_router
    from .routes.process import router as process_router, _process_heartbeat_loop

    app.include_router(icd_router)
    app.include_router(sequence_router)
    app.include_router(process_router, prefix="/api/v1/process")

    # 임시 편의 기능: 백그라운드에서 State Server를 자동으로 켜기
    state_process = None

    # ── 라이프사이클 ─────────────────────────────────────────
    @app.on_event("startup")
    async def _startup() -> None:
        nonlocal state_process
        # [NEW] 프로세스 하트비트 루프 시작
        asyncio.create_task(_process_heartbeat_loop())
        state_script = FRAMEWORK_ROOT / "DTAM_SimulationState" / "SS_main.py"
        try:
            state_process = subprocess.Popen(
                [sys.executable, str(state_script)],
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
            logger.info("Started Simulation State Server (SS_main.py) in background.")
        except Exception as e:
            logger.error(f"Failed to start State Server: {e}")

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        if state_process:
            logger.info("Stopping Simulation State Server...")
            state_process.terminate()
            try:
                state_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                state_process.kill()

    # ── 간단 admin 랜딩 ──────────────────────────────────────
    # 라이브 모니터 / 시퀀스 다이어그램은 SimulationState (8096) 가 호스팅합니다.
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index() -> HTMLResponse:
        return HTMLResponse(content=_ADMIN_INDEX_HTML)

    return app


_ADMIN_INDEX_HTML = """<!DOCTYPE html>
<html lang="ko" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <title>DTAM Core Server</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, sans-serif; background:#0e1116; color:#e6e9ef;
           margin:0; padding:40px; }
    .card { max-width:720px; margin:auto; background:#171b22; border:1px solid #2a313c;
            border-radius:12px; padding:28px 32px; }
    h1 { font-size:24px; margin:0 0 8px 0; }
    .sub { color:#8b95a3; margin-bottom:24px; }
    .row { display:flex; gap:12px; margin-bottom:12px; align-items:center; }
    .label { width:160px; color:#8b95a3; }
    a { color:#7aa2f7; }
    .pill { display:inline-block; padding:2px 8px; border-radius:999px;
            background:#1e2530; color:#7aa2f7; font-size:12px; }
    code { background:#0b0f14; padding:2px 6px; border-radius:4px; font-size:13px; }
    .links { margin-top:18px; }
    .links a { display:inline-block; margin-right:18px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>DTAM Core Server <span class="pill">control plane</span></h1>
    <div class="sub">ICD 문서 · 모듈 프로세스 라이프사이클 · cloud 연동을 담당합니다.</div>

    <div class="row"><div class="label">Live Monitor</div>
      <div><a href="http://127.0.0.1:8096/" target="_blank">http://127.0.0.1:8096/</a> (SimulationState)</div></div>
    <div class="row"><div class="label">Swagger (Core)</div>
      <div><a href="/docs">/docs</a></div></div>
    <div class="row"><div class="label">Swagger (State)</div>
      <div><a href="http://127.0.0.1:8096/docs" target="_blank">8096/docs</a></div></div>
    <div class="row"><div class="label">ICD 문서 목록</div>
      <div><a href="/api/icd">/api/icd</a></div></div>
    <div class="row"><div class="label">시퀀스 다이어그램</div>
      <div><a href="http://127.0.0.1:8096/api/sequence-diagram?lang=ko" target="_blank">8096/api/sequence-diagram</a></div></div>

    <div class="links">
      <a href="/api/v1/process/mission/start" onclick="event.preventDefault(); fetch(this.href,{method:'POST'}).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">▶ Start mission</a>
      <a href="/api/v1/process/vehicle/start" onclick="event.preventDefault(); fetch(this.href,{method:'POST'}).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">▶ Start vehicle</a>
      <a href="/api/v1/process/visual/start" onclick="event.preventDefault(); fetch(this.href,{method:'POST'}).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">▶ Start visual</a>
    </div>
  </div>
</body>
</html>
"""


__all__ = ["create_app"]
