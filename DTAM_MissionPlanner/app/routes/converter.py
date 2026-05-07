"""좌표 변환 라우트 (`/api/converter/*`)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..domain.converter_tool import (
    DEFAULT_CUSTOM_X_AXIS_HEADING_DEG,
    DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG,
    build_vertiport_spawn_layout,
    convert_target_to_unreal,
    load_airsim_settings_summary,
)
from .. import server
from ..state import state

router = APIRouter(prefix="/api/converter")


@router.get("/settings")
async def get_converter_settings() -> JSONResponse:
    try:
        return JSONResponse(load_airsim_settings_summary(None))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/convert")
async def convert_coordinates(request: Request) -> JSONResponse:
    body = await request.json()
    try:
        target_lat = float(body.get("target_lat"))
        target_lon = float(body.get("target_lon"))
        player_start_lat = float(body.get("player_start_lat"))
        player_start_lon = float(body.get("player_start_lon"))
        player_start_alt_m = float(body.get("player_start_alt_m") or 0.0)
        x_axis_heading_deg = float(body.get("x_axis_heading_deg") or DEFAULT_CUSTOM_X_AXIS_HEADING_DEG)
        y_axis_heading_deg = float(body.get("y_axis_heading_deg") or DEFAULT_CUSTOM_Y_AXIS_HEADING_DEG)
    except (TypeError, ValueError):
        return JSONResponse({"error": "Invalid converter input."}, status_code=400)

    target_ground_m = server._sample_ground_optional_m(target_lon, target_lat)
    player_start_ground_m = server._sample_ground_optional_m(player_start_lon, player_start_lat)

    raw_target_alt = body.get("target_alt_m")
    if raw_target_alt in (None, ""):
        target_alt_m = target_ground_m if target_ground_m is not None else 0.0
    else:
        try:
            target_alt_m = float(raw_target_alt)
        except (TypeError, ValueError):
            return JSONResponse({"error": "Invalid target altitude."}, status_code=400)

    result = convert_target_to_unreal(
        player_start_lat=player_start_lat,
        player_start_lon=player_start_lon,
        player_start_alt_m=player_start_alt_m,
        target_lat=target_lat,
        target_lon=target_lon,
        target_alt_m=target_alt_m,
        x_axis_heading_deg=x_axis_heading_deg,
        y_axis_heading_deg=y_axis_heading_deg,
    )
    return JSONResponse({
        "player_start": {
            "lat": player_start_lat,
            "lon": player_start_lon,
            "alt_m": player_start_alt_m,
            "ground_m": player_start_ground_m,
        },
        "target": {
            "lat": target_lat,
            "lon": target_lon,
            "ground_m": target_ground_m,
            "alt_m": target_alt_m,
        },
        **result,
    })


@router.get("/vertiport-spawns")
async def get_converter_vertiport_spawns(name: str) -> JSONResponse:
    if state.route_planner is None:
        return JSONResponse({"error": "Route planner not loaded."}, status_code=500)
    port = state.route_planner.ports.get(name)
    if port is None:
        return JSONResponse({"error": f"Unknown vertiport: {name}"}, status_code=404)
    try:
        return JSONResponse(
            build_vertiport_spawn_layout(
                vertiport_name=port.name,
                vertiport_lat=port.lat,
                vertiport_lon=port.lon,
                vertiport_ground_m=server._sample_ground_optional_m(port.lon, port.lat),
            )
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
