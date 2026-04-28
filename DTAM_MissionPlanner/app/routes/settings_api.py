"""GUI 설정 저장/조회 (`/api/settings`)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import server

router = APIRouter(prefix="/api/settings")


@router.get("")
async def get_settings() -> JSONResponse:
    return JSONResponse(server.settings)


@router.put("")
async def update_settings(request: Request) -> JSONResponse:
    body = await request.json()
    reconfigure_dtam = False
    for key in (
        "dtam_target_ip", "dtam_ws_port",
        "server_http_host", "server_http_port",
        "default_speed_mps", "default_altitude_m", "auto_plan_max_aircraft",
    ):
        if key in body:
            if key.startswith("dtam_"):
                reconfigure_dtam = True
            server.settings[key] = body[key]
    if reconfigure_dtam and server.mission_service is not None:
        server.mission_service.reconfigure(
            target_ip=str(server.settings["dtam_target_ip"]),
            ws_port=int(server.settings["dtam_ws_port"]),
        )
    return JSONResponse(server.settings)
