"""지도/리소스 정보 조회 라우트 (config, vertiports, waypoints, elevation, buildings)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..config import (
    DEFAULT_CENTER_LAT,
    DEFAULT_CENTER_LON,
    DEFAULT_START_ZOOM,
    DEM_MAX_ZOOM,
    DEM_TILE_SIZE,
)
from .. import server

router = APIRouter()


@router.get("/api/config")
async def get_config() -> JSONResponse:
    info = server.mbtiles.info if server.mbtiles else None
    bounds = list(info.bounds) if info and info.bounds else None
    return JSONResponse({
        "center": [DEFAULT_CENTER_LON, DEFAULT_CENTER_LAT],
        "zoom": DEFAULT_START_ZOOM,
        "minZoom": info.min_zoom if info else 0,
        "maxZoom": info.max_zoom if info else 14,
        "bounds": bounds,
        "tileUrl": "/tiles/{z}/{x}/{y}.pbf",
        "demUrl": "/dem/{z}/{x}/{y}.png",
        "dem": {
            "enabled": bool(server.dem_provider and server.dem_provider.available),
            "tileUrl": "/dem/{z}/{x}/{y}.png",
            "tileSize": DEM_TILE_SIZE,
            "maxZoom": DEM_MAX_ZOOM,
            "encoding": "terrarium",
            "exaggeration": 1.15,
            "pitchThreshold": 18,
            "terrainZoomThreshold": 9,
            "hillshadeMinZoom": 8,
            "buildingPitchThreshold": 28,
            "buildingZoomThreshold": 13.5,
        },
        "dtam": server._dtam_status_payload(),
    })


@router.get("/api/vertiports")
async def get_vertiports() -> JSONResponse:
    if server.route_planner is None:
        return JSONResponse([])
    result = []
    for port in server.route_planner.ports.values():
        result.append({
            "name": port.name,
            "lat": port.lat,
            "lon": port.lon,
            "ground_m": server._sample_ground_m(port.lon, port.lat),
            "inr_km": port.inr_km,
            "otr_km": port.otr_km,
            "inr_deg": port.inr_deg,
            "otr_deg": port.otr_deg,
            "turn_dir": port.turn_dir,
            "links": list(port.links),
        })
    return JSONResponse(result)


@router.get("/api/waypoints")
async def get_waypoints() -> JSONResponse:
    if server.route_planner is None:
        return JSONResponse([])
    result = []
    for wp in server.route_planner.waypoints.values():
        result.append({
            "name": wp.name,
            "lat": wp.lat,
            "lon": wp.lon,
            "ground_m": server._sample_ground_m(wp.lon, wp.lat),
            "alt_ft": wp.alt_ft,
            "alt_m": wp.alt_ft * 0.3048 if wp.alt_ft else None,
            "links": list(wp.links),
        })
    return JSONResponse(result)


@router.get("/api/elevation")
async def get_elevation(lon: float, lat: float) -> JSONResponse:
    available = bool(server.dem_provider and getattr(server.dem_provider, "available", False))
    ground_m = server._sample_ground_optional_m(lon, lat) if available else None
    return JSONResponse({
        "lon": lon,
        "lat": lat,
        "ground_m": ground_m,
        "available": available,
    })


@router.get("/api/buildings")
async def get_buildings() -> JSONResponse:
    return JSONResponse({
        "type": "FeatureCollection",
        "features": [],
    })
