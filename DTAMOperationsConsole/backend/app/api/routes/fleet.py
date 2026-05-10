"""API route for loading fleet module overview data."""

from fastapi import APIRouter

from backend.app.schemas.module import ModuleOverview
from backend.app.services.dashboard_service import get_module_overview

router = APIRouter()


@router.get("/overview", response_model=ModuleOverview)
async def get_fleet_overview() -> ModuleOverview:
    return get_module_overview("fleet")
