"""FastAPI application entrypoint for the DTAM dashboard."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Allow direct execution with:
# python backend/app/main.py
if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

framework_root = Path(__file__).resolve().parents[3]
dtam_sdk_root = framework_root / "DTAM_SDK"
if str(dtam_sdk_root) not in sys.path:
    sys.path.insert(0, str(dtam_sdk_root))

from app.routes_init_setup import api_router
from app.config import settings
from app.comm import (
    start_module_status_heartbeat,
    stop_module_status_heartbeat,
)
from app.routes.web import web_router
from dtam_client.ports import find_available_tcp_port


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_directories()
    start_module_status_heartbeat()
    try:
        yield
    finally:
        stop_module_status_heartbeat()


app = FastAPI(
    title="DTAM GUI",
    summary="Flight operations dashboard scaffold for DTAM control workflows.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(web_router)
app.include_router(api_router, prefix="/api/v1")

app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
app.mount("/resource", StaticFiles(directory=settings.resource_dir), name="resource")


def run() -> None:
    import uvicorn

    host = "127.0.0.1"
    requested_port = 8000
    port = find_available_tcp_port(host, requested_port)
    if port != requested_port:
        print(f"[DTAMOperationsConsole] port {requested_port} is busy; using {port}.")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
