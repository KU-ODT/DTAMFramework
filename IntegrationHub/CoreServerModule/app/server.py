"""DTAM Core Server FastAPI factory.

CoreServer provides ICD/phase REST APIs and module process start/stop controls.
The data plane (WebSocket traffic, DB, sequence diagram, and live monitor UI) is hosted by StateServerModule on port 8096.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .model.config import FRAMEWORK_ROOT, ServerConfig

logger = logging.getLogger(__name__)

SIMULATION_STATE_URL = "http://127.0.0.1:8096/"


def _creation_flags() -> int:
    if sys.platform != "win32":
        return 0
    if str(os.environ.get("DTAM_SHOW_SERVER_WINDOWS") or "").strip().lower() in {"1", "true", "yes", "on"}:
        return int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _state_server_ready(timeout_s: float = 0.4) -> bool:
    try:
        with urlopen(f"{SIMULATION_STATE_URL}api/state", timeout=timeout_s) as response:
            return 200 <= int(response.status) < 500
    except (OSError, URLError, TimeoutError):
        return False


def _build_tags_metadata():
    """OpenAPI tag metadata for the control plane."""
    return [
        {"name": "Process Management", "description": "Start and stop MissionModule, VehicleModule, and VisualizationModule."},
        {"name": "ICD Docs", "description": "ICD markdown documents and phase metadata."},
        {"name": "Server Status", "description": "Static control-plane metadata."},
    ]


def create_app(config: ServerConfig) -> FastAPI:
    # Registration handling
    state_process_holder: dict = {}

    from .routes.process import _process_heartbeat_loop

    @asynccontextmanager
    async def _lifespan(_: FastAPI):
        # Startup
        # Registration handling
        asyncio.create_task(_process_heartbeat_loop())
        state_script = FRAMEWORK_ROOT / "IntegrationHub" / "StateServerModule" / "SS_main.py"
        if _state_server_ready():
            state_process_holder["external"] = True
            logger.info("Simulation State Server already running at %s", SIMULATION_STATE_URL)
        else:
            try:
                state_process_holder["proc"] = subprocess.Popen(
                    [sys.executable, str(state_script)],
                    creationflags=_creation_flags(),
                )
                for _ in range(40):
                    proc = state_process_holder.get("proc")
                    if proc is not None and proc.poll() is not None:
                        logger.error("Simulation State Server exited early with code %s", proc.returncode)
                        break
                    if _state_server_ready():
                        logger.info("Started Simulation State Server (SS_main.py) in background.")
                        break
                    await asyncio.sleep(0.2)
                else:
                    logger.error("Simulation State Server did not become ready at %s", SIMULATION_STATE_URL)
            except Exception as e:
                logger.error(f"Failed to start State Server: {e}")

        try:
            yield
        finally:
            # Shutdown
            proc = state_process_holder.get("proc")
            if proc and not state_process_holder.get("external"):
                logger.info("Stopping Simulation State Server...")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()

    app = FastAPI(
        title="DTAM Core Server (control plane)",
        version="2.0.0",
        description=(
            "## DTAM Core Server\n\n"
            "Cloud/control-plane service for ICD documents, module process lifecycle, "
            "and spawning the StateServerModule data plane.\n\n"
            "- CoreServer: REST control APIs on port 8095.\n"
            "- StateServerModule: WebSocket/DB/live monitor data plane on port 8096.\n"
        ),
        openapi_tags=_build_tags_metadata(),
        lifespan=_lifespan,
    )

    # Registration handling
    from .routes.icd import router as icd_router
    from .routes.process import router as process_router

    app.include_router(icd_router)
    app.include_router(process_router, prefix="/api/v1/process")

    # Registration handling
    # Registration handling
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index() -> HTMLResponse:
        return HTMLResponse(content=_ADMIN_INDEX_HTML)

    return app


_ADMIN_INDEX_HTML = """<!DOCTYPE html>
<html lang="ko" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <title>IntegrationHub CoreServerModule</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, sans-serif; background:#0e1116; color:#e6e9ef; margin:0; padding:40px; }
    .card { max-width:720px; margin:auto; background:#171b22; border:1px solid #2a313c; border-radius:12px; padding:28px 32px; }
    h1 { font-size:24px; margin:0 0 8px 0; }
    .sub { color:#8b95a3; margin-bottom:24px; }
    .row { display:flex; gap:12px; margin-bottom:12px; align-items:center; }
    .label { width:160px; color:#8b95a3; }
    a { color:#7aa2f7; }
    .pill { display:inline-block; padding:2px 8px; border-radius:999px; background:#1e2530; color:#7aa2f7; font-size:12px; }
    .links { margin-top:18px; }
    .links a { display:inline-block; margin-right:18px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>IntegrationHub <span class="pill">CoreServerModule</span></h1>
    <div class="sub">ICD documents, module process lifecycle, and StateServerModule launch control.</div>
    <div class="row"><div class="label">Live Monitor</div><div><a href="http://127.0.0.1:8096/" target="_blank">http://127.0.0.1:8096/</a></div></div>
    <div class="row"><div class="label">Swagger Core</div><div><a href="/docs">/docs</a></div></div>
    <div class="row"><div class="label">Swagger State</div><div><a href="http://127.0.0.1:8096/docs" target="_blank">8096/docs</a></div></div>
    <div class="row"><div class="label">ICD List</div><div><a href="/api/icd">/api/icd</a></div></div>
    <div class="row"><div class="label">Sequence</div><div><a href="http://127.0.0.1:8096/docs/sequence" target="_blank">8096/docs/sequence</a></div></div>
    <div class="links">
      <a href="/api/v1/process/mission/start" onclick="event.preventDefault(); fetch(this.href,{method:'POST'}).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">Start MissionModule</a>
      <a href="/api/v1/process/vehicle/start" onclick="event.preventDefault(); fetch(this.href,{method:'POST'}).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">Start VehicleModule</a>
      <a href="/api/v1/process/visual/start" onclick="event.preventDefault(); fetch(this.href,{method:'POST'}).then(r=>r.json()).then(d=>alert(JSON.stringify(d)))">Start VisualizationModule</a>
    </div>
  </div>
</body>
</html>
"""


__all__ = ["create_app"]
