"""API route for loading data module overview data."""

from fastapi import APIRouter

from backend.app.schemas.module import ModuleOverview
from backend.app.services.dashboard_service import get_module_overview
from backend.app.services.module_process_service import start_module_and_open_gui

router = APIRouter()


@router.get("/overview", response_model=ModuleOverview)
async def get_data_overview() -> ModuleOverview:
    return get_module_overview("data")


@router.post("/open-console")
async def open_data_console() -> dict:
    return start_module_and_open_gui("server")
