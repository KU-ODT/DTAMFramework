"""API route for loading system module overview data."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from app.schemas.module import ModuleOverview
from app.services.dashboard_service import get_module_overview

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
