from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from ..services.flight_profile import build_mission_profile, DEFAULT_CRUISE_SPEED_MPS
from ..services.route_planner import get_planner

router = APIRouter(prefix="/route")


@router.post("")
def plan_route(payload: dict = Body(...)) -> dict:
    """
    Body:
      { "from": "여의도", "to": "잠실",
        "cruiseSpeedMps": 51.4, "tdpAltM": 120, "ldpAltM": 90,
        "withProfile": true }

    Returns:
      { from, to, path, distanceKm, geometry, missionProfile? }
    """
    start = (payload.get("from") or payload.get("start") or "").strip()
    end = (payload.get("to") or payload.get("end") or "").strip()
    if not start or not end:
        raise HTTPException(status_code=400, detail="Both 'from' and 'to' are required.")

    planner = get_planner()
    try:
        result = planner.find_route(start, end)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = {
        "from": start,
        "to": end,
        "path": list(result.path),
        "distanceKm": round(float(result.distance_km), 4),
        "geometry": [[round(lon, 6), round(lat, 6)] for (lon, lat) in result.points],
    }

    if payload.get("withProfile", True):
        try:
            cruise = float(payload.get("cruiseSpeedMps") or DEFAULT_CRUISE_SPEED_MPS)
        except (TypeError, ValueError):
            cruise = DEFAULT_CRUISE_SPEED_MPS
        try:
            tdp = float(payload.get("tdpAltM") or 120.0)
        except (TypeError, ValueError):
            tdp = 120.0
        try:
            ldp = float(payload.get("ldpAltM") or 90.0)
        except (TypeError, ValueError):
            ldp = 90.0
        response["missionProfile"] = build_mission_profile(
            air_distance_m=float(result.distance_km) * 1000.0,
            cruise_speed_mps=cruise,
            tdp_alt_m=tdp,
            ldp_alt_m=ldp,
        )

    return response


@router.post("/profile")
def standalone_profile(payload: dict = Body(...)) -> dict:
    """Standalone mission profile builder for given air distance (km)."""
    try:
        air_km = float(payload.get("airDistanceKm") or 0)
    except (TypeError, ValueError):
        air_km = 0.0
    if air_km <= 0:
        raise HTTPException(status_code=400, detail="airDistanceKm > 0 required.")
    cruise = float(payload.get("cruiseSpeedMps") or DEFAULT_CRUISE_SPEED_MPS)
    tdp = float(payload.get("tdpAltM") or 120.0)
    ldp = float(payload.get("ldpAltM") or 90.0)
    return build_mission_profile(
        air_distance_m=air_km * 1000.0,
        cruise_speed_mps=cruise,
        tdp_alt_m=tdp,
        ldp_alt_m=ldp,
    )


@router.get("/ports")
def list_ports() -> dict:
    return {"items": get_planner().list_ports()}


@router.get("/waypoints")
def list_waypoints() -> dict:
    return {"items": get_planner().list_waypoints()}
