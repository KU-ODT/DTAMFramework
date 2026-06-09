"""상태 조회 라우터.

- GET /api/state       — 전체 상태 스냅샷
- GET /api/modules     — 모듈 레지스트리
- PATCH /api/modules/{role} — 모듈 endpoint 수정
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["📊 서버 상태"])


@router.get(
    "/state",
    summary="전체 상태 스냅샷",
    description="서버, 모듈, 트래픽, DB 세션 등 전체 상태를 반환합니다.",
)
async def api_state(request: Request) -> JSONResponse:
    hub = request.app.state.hub
    snap = hub.snapshot()
    # DB 세션 정보를 함께 응답에 포함시켜야 모니터 UI 가 DB SESSION 을 표시.
    db = getattr(request.app.state, "db", None)
    if db is not None:
        try:
            snap["db"] = db.stats()
        except Exception:
            snap["db"] = {"session_id": "(error)", "session_dir": ""}
    return JSONResponse(snap)


@router.get(
    "/modules",
    summary="모듈 레지스트리",
    description="등록된 모든 모듈의 상태를 반환합니다.",
)
async def api_modules(request: Request) -> JSONResponse:
    hub = request.app.state.hub
    return JSONResponse(hub.snapshot()["registry"])


@router.patch(
    "/modules/{role}",
    summary="모듈 expected_source 수정",
    description="특정 모듈의 expected_source(서버에서 source 매칭에 쓰는 키)를 수정합니다.",
)
async def api_module_patch(role: str, request: Request) -> JSONResponse:
    hub = request.app.state.hub
    body = await request.json()
    expected_source = body.get("expected_source")
    info = hub.update_module_endpoint(
        role,
        expected_source=str(expected_source) if expected_source is not None else None,
    )
    if info is None:
        return JSONResponse({"error": f"unknown role {role}"}, status_code=404)
    return JSONResponse(info)
@router.post(
    "/heartbeat",
    summary="하트비트 강제 주입",
    description="특정 소스(source)로부터의 하트비트를 강제로 등록합니다.",
)
async def api_heartbeat(request: Request) -> JSONResponse:
    hub = request.app.state.hub
    body = await request.json()
    source = body.get("source", "unknown")
    role = hub.registry.heartbeat({"source": source})
    return JSONResponse({"ok": True, "role": role, "source": source})
