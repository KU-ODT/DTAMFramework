"""DTAM WebSocket 링크 상태 라우트 (`/api/v1/dtam/status`, `/api/v1/dtam/config`).

OpsConsole 의 ``MonitoringService`` 가 forwarding 받는 5개 mid (0001 / 0002 /
2002 / 4001 / 4101) 의 rx 통계와 WS 링크 상태를 노출. Mission Planner 의
``/api/dtam/status`` 와 셰입 동일 — 5개 모듈 모두 동일한 운영 시야 제공.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from app.deps import get_monitoring_service
from app.services.monitoring_service import MonitoringService

router = APIRouter()


@router.get("/status", summary="DTAM WebSocket 링크 상태 + rx 통계")
def get_dtam_status(
    svc: MonitoringService = Depends(get_monitoring_service),
) -> JSONResponse:
    return JSONResponse(svc.describe())


@router.post("/config", summary="DTAM WebSocket endpoint 재설정")
def update_dtam_config(
    body: Dict[str, Any] = Body(default_factory=dict),
    svc: MonitoringService = Depends(get_monitoring_service),
) -> JSONResponse:
    target_ip = body.get("target_ip") or body.get("targetIp")
    ws_port_raw = body.get("ws_port") or body.get("wsPort")
    ws_port = int(ws_port_raw) if ws_port_raw not in (None, "") else None
    desc = svc.reconfigure(
        target_ip=str(target_ip) if target_ip else None,
        ws_port=ws_port,
    )
    return JSONResponse(desc)
