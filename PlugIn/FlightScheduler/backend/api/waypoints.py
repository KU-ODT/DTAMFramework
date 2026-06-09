from __future__ import annotations

from fastapi import APIRouter

from ..services.waypoint_loader import load_waypoints

router = APIRouter()


@router.get("/waypoints")
def list_waypoints() -> dict:
    return {"items": load_waypoints()}
