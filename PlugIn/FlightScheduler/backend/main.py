from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import analysis, demand, layouts, route, simulations, tiles, vertiport_configs, vertiports, waypoints
from backend.config import FRONTEND_DIR, MBTILES_PATH

app = FastAPI(title="Flight Scheduler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers are grouped by UI domain. Keep static frontend mounting last so
# /api and /tiles routes are never swallowed by the catch-all file server.
app.include_router(tiles.router)
app.include_router(vertiports.router, prefix="/api")
app.include_router(waypoints.router, prefix="/api")
app.include_router(demand.router, prefix="/api")
app.include_router(layouts.router, prefix="/api")
app.include_router(vertiport_configs.router, prefix="/api")
app.include_router(route.router, prefix="/api")
app.include_router(simulations.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "mbtilesPath": str(MBTILES_PATH),
        "mbtilesAvailable": MBTILES_PATH.is_file(),
    }


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import os

    import uvicorn

    project_root = str(Path(__file__).resolve().parent.parent)
    os.environ["PYTHONPATH"] = project_root + os.pathsep + os.environ.get("PYTHONPATH", "")
    os.chdir(project_root)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8123, reload=True)
