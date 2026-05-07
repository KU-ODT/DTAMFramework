"""API routes for simulation module overview and operational environment data."""

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.schemas.module import ModuleOverview
from backend.app.services.dashboard_service import get_module_overview
from backend.app.services.mission_planner_client import compute_route_via_mission_planner
from backend.app.services.operational_environment import (
    OperationalEnvironmentError,
    load_operational_environment,
    reset_operational_environment_files,
    update_corridor,
    update_vertiport,
)
from backend.app.services.vehicle_status_service import vehicle_status_snapshot

router = APIRouter()


@router.get("/overview", response_model=ModuleOverview)
async def get_simulation_overview() -> ModuleOverview:
    return get_module_overview("simulation")


@router.get("/operational-environment")
async def get_operational_environment() -> dict[str, Any]:
    return load_operational_environment()


@router.get("/vehicle-status")
async def get_vehicle_status() -> dict[str, Any]:
    return vehicle_status_snapshot()


@router.post("/mission-route")
async def post_mission_route(payload: dict[str, Any]) -> dict[str, Any]:
    return compute_route_via_mission_planner(payload)


@router.post("/operational-environment/reset")
async def reset_operational_environment() -> dict[str, Any]:
    reset_operational_environment_files()
    return load_operational_environment()


@router.post("/operational-environment/vertiports")
async def post_operational_environment_vertiports(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return update_vertiport(payload)
    except OperationalEnvironmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/operational-environment/corridors")
async def post_operational_environment_corridors(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return update_corridor(payload)
    except OperationalEnvironmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
