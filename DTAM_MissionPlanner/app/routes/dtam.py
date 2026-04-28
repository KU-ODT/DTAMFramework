"""DTAM 3001 송신·상태 라우트 (`/api/dtam/status`, `/api/dtam/config`, `/api/dtam/send`)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import server

router = APIRouter(prefix="/api/dtam")


@router.get("/status")
async def get_dtam_status() -> JSONResponse:
    return JSONResponse(server._dtam_status_payload())


@router.post("/config")
async def update_dtam_config(request: Request) -> JSONResponse:
    body = await request.json()
    try:
        target_ip = body.get("target_ip") or body.get("targetIp")
        ws_port = server._coerce_int(body.get("ws_port") or body.get("wsPort"))
        if target_ip:
            server.settings["dtam_target_ip"] = str(target_ip)
        if ws_port is not None:
            server.settings["dtam_ws_port"] = int(ws_port)
        if server.dtam_sender is not None:
            server.dtam_sender.reconfigure(
                target_ip=str(server.settings["dtam_target_ip"]),
                ws_port=int(server.settings["dtam_ws_port"]),
            )
        return JSONResponse(server._dtam_status_payload())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/send")
async def send_to_dtam(request: Request) -> JSONResponse:
    """Mission payload (ICD record / list / mission draft) 를 받아 3001 로 송신."""
    if server.dtam_sender is None:
        return JSONResponse({"error": "DTAM sender not ready"}, status_code=500)
    body = await request.json()
    try:
        if server._looks_like_icd_record(body) or server._looks_like_icd_record_list(body):
            export = server._build_existing_icd_export_bundle(body)
        else:
            export = server._build_mission_icd_bundle(body)
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

    records = server._extract_records_from_export(export)
    if not records:
        return JSONResponse({"error": "No ICD records to send"}, status_code=400)

    send_result = server.dtam_sender.send_scheduled_flights(records)
    response = {
        "ok": send_result["ok"],
        "target": f"ws://{server.settings['dtam_target_ip']}:{int(server.settings['dtam_ws_port'])}/ws/dtam",
        "count": send_result["count"],
        "results": send_result["results"],
        "fleet": export.get("fleet", []),
        "mission_export": export,
    }
    status_code = 200 if send_result["ok"] else 502
    return JSONResponse(response, status_code=status_code)
