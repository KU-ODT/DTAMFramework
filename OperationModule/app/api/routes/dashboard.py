"""API route for loading the dashboard module list."""

from fastapi import APIRouter

from app.schemas.module import ModuleCard
from app.services.dashboard_service import list_modules

router = APIRouter()


@router.get("/modules", response_model=list[ModuleCard])
async def get_modules() -> list[ModuleCard]:
    return list_modules()
