"""ICD 3001 export / save / open-folder 라우트."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import server

router = APIRouter(prefix="/api/mission/icd")


@router.post("/export")
async def export_mission_icd(request: Request) -> JSONResponse:
    body = await request.json()
    try:
        if server._looks_like_icd_record(body) or server._looks_like_icd_record_list(body):
            result = server._build_existing_icd_export_bundle(body)
        else:
            result = server._build_mission_icd_bundle(body)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/save")
async def save_mission_icd(request: Request) -> JSONResponse:
    if server.mission_service is None:
        return JSONResponse({"error": "DTAM sender not ready"}, status_code=500)
    body = await request.json()
    try:
        if server._looks_like_icd_record(body) or server._looks_like_icd_record_list(body):
            result = server._build_existing_icd_export_bundle(body)
        else:
            result = server._build_mission_icd_bundle(body)
        if not result.get("validation", {}).get("valid", False):
            return JSONResponse(result, status_code=400)
        records = server._extract_records_from_export(result)
        if not records:
            return JSONResponse({"error": "No ICD records to save"}, status_code=400)
        send_result = server.mission_service.send_scheduled_flights(records)
        result["saved_by"] = "DTAM_SimulationState"
        result["local_save"] = False
        result["send_result"] = send_result
        status_code = 200 if send_result.get("ok") else 502
        return JSONResponse(result, status_code=status_code)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/open-folder")
async def open_mission_icd_folder() -> JSONResponse:
    try:
        stats = server._server_get_json("/api/db/stats")
        return JSONResponse({
            "ok": True,
            "folder_path": stats.get("session_dir"),
            "server_db": stats,
            "open_folder_url": f"{server._server_http_base()}/api/db/open-folder",
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
