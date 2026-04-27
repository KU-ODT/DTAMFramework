from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.services import dtam_sdk_service

router = APIRouter(tags=["📊 모듈 관리"])

@router.get("")
async def list_modules() -> dict[str, Any]:
    """Get real-time module status from the State Server."""
    snapshot = dtam_sdk_service.get_registry_snapshot()
    # 필요한 정보만 필터링하여 반환
    modules = snapshot.get("registry", {}).get("modules", [])
    return {"modules": modules}

@router.post("/{role}/start")
async def start_module(role: str) -> dict[str, Any]:
    """Request Core Server to start a module process."""
    result = dtam_sdk_service.control_module_process(role, "start")
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to start module"))
    return result

@router.post("/{role}/stop")
async def stop_module(role: str) -> dict[str, Any]:
    """Request Core Server to stop a module process."""
    result = dtam_sdk_service.control_module_process(role, "stop")
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to stop module"))
    return result
