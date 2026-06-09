"""API route for loading operations module overview data."""

from fastapi import APIRouter

from app.schemas.module import ModuleOverview
from app.services.dashboard_service import get_module_overview

router = APIRouter()


@router.get("/overview", response_model=ModuleOverview)
async def get_operations_overview() -> ModuleOverview:
    return get_module_overview("operations")
