"""DTAM Server FastAPI 앱 팩토리.

6계층 구조:
  model/    — 데이터 모델, 메시지 정의
  database/ — 파일 DB
  schema/   — Pydantic 요청/응답 모델
  service/  — 비즈니스 로직 (Hub, Registry)
  router/   — FastAPI 라우터 (REST, WebSocket)
  middleware/ — 미들웨어 (향후 확장)
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Set

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from .model.config import FRAMEWORK_ROOT, WEB_DIR, ServerConfig
from .model.message import PHASE_INFO, phase_tag

logger = logging.getLogger(__name__)

SEQUENCE_DIAGRAM_PATH = WEB_DIR / "data" / "sequence_diagram.json"


def _build_tags_metadata():
    """Phase 기반 + 기능별 Swagger UI 태그 메타데이터."""
    tags = []
    for phase_num in sorted(PHASE_INFO.keys()):
        info = PHASE_INFO[phase_num]
        tags.append({
            "name": phase_tag(phase_num),
            "description": f"**{info['name_en']}** — {info['description']}",
        })
    tags.extend([
        {"name": "📋 ICD 문서", "description": "ICD 마크다운 문서 및 Phase 정보 조회"},
        {"name": "📊 서버 상태", "description": "서버, 모듈 상태 스냅샷 및 모듈 endpoint 관리"},
        {"name": "💾 데이터베이스", "description": "DB 통계, 메시지 조회, 폴더 열기"},
        {"name": "📹 카메라", "description": "MJPEG 카메라 스트림 및 활성 카메라 목록"},
        {"name": "📡 WebSocket 문서", "description": "WebSocket 프로토콜 문서 (Swagger에서 WS는 직접 테스트 불가)"},
    ])
    return tags


def create_app(config: ServerConfig) -> FastAPI:
    app = FastAPI(
        title="DTAM Server",
        version="2.0.0",
        description=(
            "## DTAM 시뮬레이션 서버 API\n\n"
            "Digital Twin-based Air Mobility 시뮬레이션 서버입니다.\n\n"
            "### 통신 방식\n"
            "- **REST API** — 이 문서의 모든 엔드포인트\n"
            "- **WebSocket `/ws/dtam`** — 모듈 통신 ([문서 보기](/docs/websocket))\n"
            "- **WebSocket `/ws/events`** — GUI 실시간 이벤트\n"
            "- **MJPEG `/stream/camera/{id}`** — 카메라 영상 스트림\n\n"
            "### Phase 기반 메시지 흐름\n"
            "각 메시지는 시퀀스 다이어그램의 Phase에 따라 그룹화됩니다.\n"
            "`POST /api/msg/{mid}` 엔드포인트로 메시지를 전송할 수 있습니다.\n"
        ),
        openapi_tags=_build_tags_metadata(),
    )

    # ── 라우터 등록 ──────────────────────────────────────────
    from .router.icd import router as icd_router
    from .router.sequence import router as sequence_router
    from .router.process import router as process_router, _process_heartbeat_loop

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
                [sys.executable, str(state_script), "--udp-port", "17000"],
                # stdout=subprocess.DEVNULL,
                # stderr=subprocess.DEVNULL,
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

    # ── 정적 파일 ────────────────────────────────────────────
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index() -> HTMLResponse:
        return HTMLResponse(content=(WEB_DIR / "index.html").read_text(encoding="utf-8"))

    if (WEB_DIR / "css").is_dir():
        app.mount("/css", StaticFiles(directory=str(WEB_DIR / "css")), name="css")
    if (WEB_DIR / "js").is_dir():
        app.mount("/js", StaticFiles(directory=str(WEB_DIR / "js")), name="js")

    @app.get("/api/sequence-diagram", include_in_schema=False)
    async def get_sequence_diagram(lang: str = "ko") -> Response:
        lang_suffix = "_en" if lang.lower().startswith("e") else "_ko"
        path = SEQUENCE_DIAGRAM_PATH.parent / f"sequence_diagram{lang_suffix}.json"
        if not path.is_file():
            path = SEQUENCE_DIAGRAM_PATH  # fallback
        if not path.is_file():
            return Response(content=json.dumps({"actors": [], "messages": []}), media_type="application/json")
        return Response(content=path.read_text(encoding="utf-8"), media_type="application/json")

    return app


__all__ = ["create_app"]
