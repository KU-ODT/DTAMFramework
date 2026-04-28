"""API route for loading simulation module overview data."""

from fastapi import APIRouter

from app.schemas.module import ModuleOverview
from app.services.dashboard_service import get_module_overview

router = APIRouter()


@router.get("/overview", response_model=ModuleOverview)
async def get_simulation_overview() -> ModuleOverview:
    return get_module_overview("simulation")
