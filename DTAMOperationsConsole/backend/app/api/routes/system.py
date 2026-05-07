"""API route for loading system module overview data."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from backend.app.schemas.module import ModuleOverview
from backend.app.services.dashboard_service import get_module_overview
from backend.app.services.dtam_execution_service import prepare_dtam_execution
from backend.app.services.module_process_service import (
    list_module_status,
    open_module_gui,
    start_all_modules,
    start_module,
    stop_all_modules,
    stop_module,
)

router = APIRouter()


@router.get("/overview", response_model=ModuleOverview)
async def get_system_overview() -> ModuleOverview:
    return get_module_overview("system")


@router.get("/time")
async def get_server_time() -> dict[str, str]:
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    return {
        "timezone": "Asia/Seoul",
        "iso": now.isoformat(),
        "display": now.strftime("%Y-%m-%d %H:%M:%S KST"),
    }


@router.get("/modules")
async def get_dtam_modules() -> dict:
    return list_module_status()


@router.post("/modules/run")
async def run_dtam_modules() -> dict:
    return start_all_modules()


@router.post("/modules/start")
async def start_dtam_modules() -> dict:
    return start_all_modules()


@router.post("/dtam/prepare-execution")
async def prepare_dtam_execution_route(payload: dict) -> dict:
    return prepare_dtam_execution(payload)


@router.post("/modules/stop")
async def stop_dtam_modules() -> dict:
    return stop_all_modules()


@router.post("/modules/{module_id}/run")
async def run_dtam_module(module_id: str) -> dict:
    return start_module(module_id)


@router.post("/modules/{module_id}/stop")
async def stop_dtam_module(module_id: str) -> dict:
    return stop_module(module_id)


@router.post("/modules/{module_id}/open-gui")
async def open_dtam_module_gui(module_id: str) -> dict:
    return open_module_gui(module_id)
