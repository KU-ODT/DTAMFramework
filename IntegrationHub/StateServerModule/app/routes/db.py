"""파일 DB 관련 REST 라우터.

라이브 모니터 페이지가 ``/api/db/stats`` 와 ``/api/db/open-folder``
를 호출합니다. file_db 인스턴스는 ``app.state.db`` 에 주입됩니다.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/db", tags=["💾 데이터베이스"])


@router.get(
    "/stats",
    summary="DB 통계",
    description="현재 세션의 파일 DB 통계 (메시지별 누적 카운트, 마지막 쓰기 시각).",
)
async def db_stats(request: Request) -> JSONResponse:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return JSONResponse({"error": "db not initialised"}, status_code=503)
    return JSONResponse(db.stats())


@router.post(
    "/open-folder",
    summary="DB 폴더 열기",
    description="OS의 파일 탐색기로 현재 세션 DB 폴더를 엽니다.",
)
async def open_db_folder(request: Request) -> JSONResponse:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return JSONResponse({"error": "db not initialised"}, status_code=503)
    folder = Path(db.session_dir).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    try:
        if hasattr(os, "startfile"):
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "folder_path": str(folder)})


@router.get(
    "/messages/{mid}/latest",
    summary="메시지 최신 페이로드",
    description="특정 메시지 ID의 최근 저장 페이로드 1건. ``field``+``value`` 로 필터링 가능.",
)
async def db_latest_message(
    request: Request,
    mid: str,
    field: str | None = None,
    value: str | None = None,
) -> JSONResponse:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return JSONResponse({"error": "db not initialised"}, status_code=503)
    event = db.find_latest_event(mid, field=field, value=value)
    if event is None:
        return JSONResponse(
            {"ok": False, "mid": mid, "error": "message payload not found"},
            status_code=404,
        )
    return JSONResponse({"ok": True, **event})
