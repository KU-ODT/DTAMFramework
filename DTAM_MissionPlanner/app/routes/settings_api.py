"""GUI 설정 저장/조회 (`/api/settings`)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..state import state

router = APIRouter(prefix="/api/settings")


@router.get("")
async def get_settings() -> JSONResponse:
    return JSONResponse(state.settings)


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
            state.settings[key] = body[key]
    if reconfigure_dtam and state.mission_service is not None:
        state.mission_service.reconfigure(
            target_ip=str(state.settings["dtam_target_ip"]),
            ws_port=int(state.settings["dtam_ws_port"]),
        )
    return JSONResponse(state.settings)
