"""Live aircraft traffic API for the simulation workspace."""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.services.commercial_traffic import get_commercial_traffic

router = APIRouter()


@router.get("/commercial")
async def commercial_traffic(region: str = Query(default="korea", pattern="^[a-zA-Z0-9_-]{1,32}$")):
    return get_commercial_traffic(region=region)
