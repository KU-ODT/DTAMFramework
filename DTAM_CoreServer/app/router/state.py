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
    description="서버, 모듈, 트래픽 등 전체 상태를 반환합니다.",
)
async def api_state(request: Request) -> JSONResponse:
    hub = request.app.state.hub
    return JSONResponse(hub.snapshot())


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
    summary="모듈 endpoint 수정",
    description="특정 모듈의 IP, 포트, expected_source를 수정합니다.",
)
async def api_module_patch(role: str, request: Request) -> JSONResponse:
    hub = request.app.state.hub
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
