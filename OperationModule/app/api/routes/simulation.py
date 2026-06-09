"""API routes for simulation module overview and operational environment data."""

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Body, HTTPException

from app.schemas.module import ModuleOverview
from app.services.dashboard_service import get_module_overview
from app.services.mission_planner_client import compute_route_via_mission_planner
from app.services.module_process_service import STATE_HOST, STATE_PORT
from app.services.operational_environment import (
    OperationalEnvironmentError,
    load_operational_environment,
    reset_operational_environment_files,
    update_corridor,
    update_vertiport,
)
from app.services.vehicle_status_service import clear_collision_response, vehicle_status_snapshot

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


@router.post("/collision/clear")
async def post_collision_clear(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    vehicle_id = str(
        payload.get("aircraftId")
        or payload.get("vehicleId")
        or payload.get("vehicle_id")
        or ""
    ).strip()
    all_flag = bool(payload.get("all") or payload.get("clearAll"))
    clear_history = bool(payload.get("clearHistory") or payload.get("clear_history"))
    try:
        return clear_collision_response("" if all_flag else vehicle_id, clear_history=clear_history)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/collision/{vehicle_id}/clear")
async def post_collision_clear_vehicle(vehicle_id: str) -> dict[str, Any]:
    try:
        return clear_collision_response(str(vehicle_id or "").strip())
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/mission-route")
async def post_mission_route(payload: dict[str, Any]) -> dict[str, Any]:
    return compute_route_via_mission_planner(payload)


@router.get("/latest-mission-plans")
async def get_latest_mission_plans() -> dict[str, Any]:
    """Return the latest SimModeSetup mission plans cached by StateServer."""

    url = f"http://{STATE_HOST}:{STATE_PORT}/api/db/messages/1001/latest"
    request = UrlRequest(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=2.5) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
    except HTTPError as exc:
        return {"ok": False, "missions": [], "error": f"StateServer {exc.code}"}
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "missions": [], "error": str(exc)}

    payload = data.get("payload") if isinstance(data, dict) and isinstance(data.get("payload"), dict) else {}
    mission_planning = (
        payload.get("singleFlight", {})
        .get("missionPlanning", {})
        if isinstance(payload.get("singleFlight"), dict)
        else {}
    )
    missions = mission_planning.get("missions") if isinstance(mission_planning, dict) else []
    return {
        "ok": True,
        "source": "SimModeSetup",
        "path": data.get("path"),
        "modifiedAt": data.get("modified_at"),
        "activeMissionId": mission_planning.get("activeMissionId") if isinstance(mission_planning, dict) else "",
        "missions": missions if isinstance(missions, list) else [],
    }


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
