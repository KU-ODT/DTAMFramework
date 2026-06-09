"""FastAPI dependency providers.

라우트가 ``Depends(get_X)`` 로 의존성을 주입받기 위한 getters. 모두
``app.state`` 모듈의 단일 ``state`` 컨테이너에서 읽는다 — 모듈 레벨
``global`` 키워드 없이 단일 소스에서 검증된 의존성을 라우트에 공급.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException

from .services.mission_service import MissionService
from .services.route_planner import RoutePlanner
from .state import state


def get_settings() -> Dict[str, Any]:
    return state.settings


def get_mbtiles() -> Any:
    if state.mbtiles is None:
        raise HTTPException(status_code=503, detail="MBTiles not loaded")
    return state.mbtiles


def get_route_planner() -> RoutePlanner:
    if state.route_planner is None:
        raise HTTPException(status_code=503, detail="Route planner not loaded")
    return state.route_planner


def get_dem_provider() -> Any:
    if state.dem_provider is None:
        raise HTTPException(status_code=503, detail="DEM provider not loaded")
    return state.dem_provider


def get_mission_service() -> MissionService:
    if state.mission_service is None:
        raise HTTPException(status_code=503, detail="MissionService not ready")
    return state.mission_service


__all__ = [
    "get_settings",
    "get_mbtiles",
    "get_route_planner",
    "get_dem_provider",
    "get_mission_service",
]
