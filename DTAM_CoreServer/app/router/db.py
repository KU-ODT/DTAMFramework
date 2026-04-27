"""데이터베이스 라우터.

- GET /api/db/stats               — DB 통계
- GET /api/db/messages/{mid}/latest — 최신 메시지 조회
- POST /api/db/open-folder        — DB 폴더 열기
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/db", tags=["💾 데이터베이스"])
logger = logging.getLogger(__name__)


@router.get(
    "/stats",
    summary="DB 통계",
    description="현재 세션의 DB 저장 통계를 반환합니다.",
)
async def api_db_stats(request: Request) -> JSONResponse:
    hub = request.app.state.hub
    return JSONResponse(hub.db.stats())


@router.get(
    "/messages/{mid}/latest",
    summary="최신 메시지 조회",
    description="특정 메시지 ID의 가장 최근 저장된 payload를 조회합니다.",
)
async def api_db_latest_message(
    mid: str,
    request: Request,
    field: Optional[str] = None,
    value: Optional[str] = None,
) -> JSONResponse:
    hub = request.app.state.hub
    event = hub.db.find_latest_event(mid, field=field, value=value)
    if event is None:
        return JSONResponse(
            {"ok": False, "mid": mid, "error": "message payload not found"},
            status_code=404,
        )
    return JSONResponse({"ok": True, **event})


@router.post(
    "/open-folder",
    summary="DB 폴더 열기",
    description="현재 세션의 DB 저장 폴더를 OS 탐색기에서 엽니다.",
)
async def api_db_open_folder(request: Request) -> JSONResponse:
    hub = request.app.state.hub
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
