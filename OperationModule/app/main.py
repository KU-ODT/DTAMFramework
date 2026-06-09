"""FastAPI application entrypoint for the DTAM dashboard."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Allow direct execution with:
# python app/main.py
if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

framework_root = Path(__file__).resolve().parents[2]
dtam_sdk_root = framework_root / "DTAMSDK"
if str(dtam_sdk_root) not in sys.path:
    sys.path.insert(0, str(dtam_sdk_root))

from app.api.router import api_router
from app.api.routes.legacy_msg import router as legacy_msg_router
from app.core.settings import settings
from app.services.dtam_sdk_service import (
    start_module_status_heartbeat,
    stop_module_status_heartbeat,
)
from app.services.monitoring_service import MonitoringService
from app.services.module_process_service import shutdown_modules_for_console_exit
from app.services.operational_environment import ensure_operational_environment_files
from app.services.plugin_process_service import shutdown_plugins_for_console_exit
from app.services.vehicle_status_service import (
    start_vehicle_status_listener,
    stop_vehicle_status_listener,
)
from app.web.router import web_router
from dtam_client.ports import find_available_tcp_port


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_directories()
    ensure_operational_environment_files()
    start_module_status_heartbeat()
    start_vehicle_status_listener()
    monitoring_service = MonitoringService()
    app.state.monitoring_service = monitoring_service
    try:
        yield
    finally:
        monitoring_service.close()
        stop_vehicle_status_listener()
        stop_module_status_heartbeat()
        shutdown_plugins_for_console_exit()
        shutdown_modules_for_console_exit()


app = FastAPI(
    title="DTAM GUI",
    summary="Flight operations dashboard scaffold for DTAM control workflows.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(web_router)
app.include_router(api_router, prefix="/api/v1")
app.include_router(legacy_msg_router)

app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
app.mount("/resource", StaticFiles(directory=settings.resource_dir), name="resource")
app.mount("/resources", StaticFiles(directory=settings.resource_dir), name="resources")


def run() -> None:
    import uvicorn

    host = "127.0.0.1"
    requested_port = 8000
    port = find_available_tcp_port(host, requested_port)
    if port != requested_port:
        print(f"[OperationModule] port {requested_port} is busy; using {port}.")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()
