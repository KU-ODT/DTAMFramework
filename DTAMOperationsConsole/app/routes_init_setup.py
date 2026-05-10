"""Main API router that combines all feature route modules."""

from fastapi import APIRouter

from app.routes import airspace, dashboard, data, dtam, environment, fleet, health, icd, mission, modules, operations, simulation, system, tiles, traffic

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(icd.router, prefix="/icd", tags=["icd"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["simulation"])
api_router.include_router(mission.router, prefix="/mission", tags=["mission"])
api_router.include_router(environment.router, prefix="/environment", tags=["environment"])
api_router.include_router(operations.router, prefix="/operations", tags=["operations"])
api_router.include_router(fleet.router, prefix="/fleet", tags=["fleet"])
api_router.include_router(airspace.router, prefix="/airspace", tags=["airspace"])
api_router.include_router(data.router, prefix="/data", tags=["data"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(tiles.router, prefix="/tiles", tags=["tiles"])
api_router.include_router(traffic.router, prefix="/traffic", tags=["traffic"])
api_router.include_router(modules.router, prefix="/system/modules", tags=["system-modules"])
api_router.include_router(dtam.router, prefix="/dtam", tags=["dtam"])
