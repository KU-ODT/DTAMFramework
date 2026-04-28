"""DTAM 3001 송신·상태 라우트 (`/api/dtam/status`, `/api/dtam/config`, `/api/dtam/send`)."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..deps import get_mission_service
from ..services.mission_service import MissionService
from ..state import state

router = APIRouter(prefix="/api/dtam")


@router.get("/status")
async def get_dtam_status() -> JSONResponse:
    if state.mission_service is None:
        return JSONResponse({
            "ready": False,
            "target_ip": state.settings.get("dtam_target_ip"),
            "ws_port": state.settings.get("dtam_ws_port"),
            "last_error": "service not initialised",
        })
    return JSONResponse(state.mission_service.describe())


@router.post("/config")
async def update_dtam_config(request: Request) -> JSONResponse:
    body = await request.json()
    try:
        target_ip = body.get("target_ip") or body.get("targetIp")
        ws_port_raw = body.get("ws_port") or body.get("wsPort")
        ws_port = int(ws_port_raw) if ws_port_raw not in (None, "") else None
        if target_ip:
            state.settings["dtam_target_ip"] = str(target_ip)
        if ws_port is not None:
            state.settings["dtam_ws_port"] = int(ws_port)
        if state.mission_service is not None:
            state.mission_service.reconfigure(
                target_ip=str(state.settings["dtam_target_ip"]),
                ws_port=int(state.settings["dtam_ws_port"]),
            )
            return JSONResponse(state.mission_service.describe())
        return JSONResponse({"ready": False, "last_error": "service not initialised"})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/send")
async def send_to_dtam(
    request: Request,
    svc: MissionService = Depends(get_mission_service),
) -> JSONResponse:
    """Mission payload (ICD record / list / mission draft) 를 받아 3001 로 송신."""
    body = await request.json()
    try:
        if svc.looks_like_icd_record(body) or svc.looks_like_icd_record_list(body):
            export = svc.build_existing_icd_export_bundle(body)
        else:
            export = svc.build_mission_icd_bundle(body)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    validation = export.get("validation", {}) or {}
    if not validation.get("valid", False):
        return JSONResponse({
            "ok": False,
            "error": "Validation failed",
            "validation": validation,
            "warnings": export.get("warnings", []),
            "fleet": export.get("fleet", []),
        }, status_code=400)

    records = svc.extract_records_from_export(export)
    if not records:
        return JSONResponse({"error": "No ICD records to send"}, status_code=400)

    send_result = svc.send_scheduled_flights(records)
    response: Dict[str, Any] = {
        "ok": send_result["ok"],
        "target": f"ws://{state.settings['dtam_target_ip']}:{int(state.settings['dtam_ws_port'])}/ws/dtam",
        "count": send_result["count"],
        "results": send_result["results"],
        "fleet": export.get("fleet", []),
        "mission_export": export,
    }
    status_code = 200 if send_result["ok"] else 502
    return JSONResponse(response, status_code=status_code)
