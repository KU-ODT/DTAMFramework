from __future__ import annotations

import json
import mimetypes
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
import uvicorn

from app.config import APP_TITLE, DATA_DIR, SERVER_HOST, SERVER_PORT
from app.datafile_service import DatafileService
from app.pathplanner import RoutePlanner
from app.web_server import (
    SimulationApi,
    _ensure_data_dir,
    _ensure_utf8_content_type,
    _open_browser,
    _safe_join,
)


@dataclass
class ServerContext:
    data_dir: Path
    api: SimulationApi
    datafiles: DatafileService


def _build_context() -> ServerContext:
    _ensure_data_dir()
    planner = RoutePlanner.from_csv(
        DATA_DIR / "default" / "vertiport_default.csv",
        DATA_DIR / "default" / "corridor_default.csv",
    )
    api = SimulationApi(
        planner,
        DATA_DIR / "default" / "vertiport_default.csv",
        DATA_DIR / "default" / "corridor_default.csv",
        DATA_DIR / "default" / "basestation_default.csv",
    )
    datafiles = DatafileService(DATA_DIR, api)
    return ServerContext(
        data_dir=DATA_DIR,
        api=api,
        datafiles=datafiles,
    )


async def _read_payload(request: Request) -> Dict[str, Any]:
    body = await request.body()
    if not body:
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON")
    return payload


def _json_result(payload: Dict[str, Any]) -> JSONResponse:
    status = 200 if payload.get("ok") else 400
    return JSONResponse(payload, status_code=status)


def _normalize_data_url(value: str) -> str:
    if value.startswith("/data/"):
        return f"api/data/{value[len('/data/') :]}"
    if value.startswith("data/"):
        return f"api/data/{value[len('data/') :]}"
    if value.startswith("/api/data/"):
        return value[len("/") :]
    return value


def _guess_content_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path)
    return _ensure_utf8_content_type(mime or "application/octet-stream")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = _build_context()
    app.state.ctx = ctx
    ctx.api.start_loop()
    try:
        yield
    finally:
        ctx.api.stop_loop()


def create_app() -> FastAPI:
    app = FastAPI(title=APP_TITLE, lifespan=lifespan)

    @app.get("/api/state")
    async def api_state(request: Request, positions_rev: Optional[int] = None) -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        if positions_rev is not None and positions_rev < 0:
            positions_rev = None
        return ctx.api.get_state(positions_rev=positions_rev)

    @app.get("/api/history")
    async def api_history(request: Request, name: str = "") -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        points = ctx.api.get_history(name)
        return {"name": name, "points": points}

    @app.get("/api/logs.zip")
    async def api_logs(request: Request, lang: str = "en") -> Response:
        ctx: ServerContext = request.app.state.ctx
        vertiport_path = ctx.datafiles.resolve_datafile_path(request.query_params.get("vertiport"))
        corridor_path = ctx.datafiles.resolve_datafile_path(request.query_params.get("corridor"))
        basestation_path = ctx.datafiles.resolve_datafile_path(request.query_params.get("basestation"))
        lang = (lang or "en").lower()
        if lang not in ("en", "ko"):
            lang = "en"
        result = ctx.api.get_logs_zip(
            lang,
            vertiport_path=vertiport_path,
            corridor_path=corridor_path,
            basestation_path=basestation_path,
        )
        if not result:
            raise HTTPException(status_code=404, detail="No log session available")
        data, filename = result
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        }
        return Response(content=data, media_type="application/zip", headers=headers)

    @app.post("/api/control")
    async def api_control(request: Request) -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        ctx.api.handle_control(payload)
        return {"ok": True}

    @app.post("/api/selection")
    async def api_selection(request: Request) -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        ctx.api.set_selection(payload)
        return {"ok": True}

    @app.post("/api/traffic")
    async def api_traffic(request: Request) -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        ctx.api.set_traffic(payload)
        return {"ok": True}

    @app.post("/api/rules")
    async def api_rules(request: Request) -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        rules = ctx.api.set_rules(payload)
        return {"ok": True, "rules": rules}

    @app.post("/api/wind")
    async def api_wind(request: Request) -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        wind_state = ctx.api.set_wind(payload)
        return {"ok": True, "wind": wind_state}

    @app.post("/api/sim/start")
    async def api_sim_start(request: Request) -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        ctx.api.start_simulation(payload)
        return {"ok": True}

    @app.post("/api/sim/pause")
    async def api_sim_pause(request: Request) -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        await _read_payload(request)
        ctx.api.pause_simulation()
        return {"ok": True}

    @app.post("/api/sim/stop")
    async def api_sim_stop(request: Request) -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        await _read_payload(request)
        ctx.api.stop_simulation()
        return {"ok": True}

    @app.post("/api/sim/fast")
    async def api_sim_fast(request: Request) -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        await _read_payload(request)
        ctx.api.fast_simulation()
        return {"ok": True}

    @app.post("/api/sim/speed")
    async def api_sim_speed(request: Request) -> Dict[str, Any]:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        speed_value = ctx.api.set_simulation_speed(payload)
        return {"ok": True, "speed": speed_value}

    @app.post("/api/datafiles/clone")
    async def api_datafiles_clone(request: Request) -> JSONResponse:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        result = ctx.datafiles.clone_datafile(payload)
        if result.get("ok") and isinstance(result.get("url"), str):
            result["url"] = _normalize_data_url(result["url"])
        return _json_result(result)

    @app.post("/api/datafiles/append")
    async def api_datafiles_append(request: Request) -> JSONResponse:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        result = ctx.datafiles.append_datafile(payload)
        if result.get("ok") and isinstance(result.get("url"), str):
            result["url"] = _normalize_data_url(result["url"])
        return _json_result(result)

    @app.post("/api/datafiles/update")
    async def api_datafiles_update(request: Request) -> JSONResponse:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        result = ctx.datafiles.update_datafile(payload)
        if result.get("ok") and isinstance(result.get("url"), str):
            result["url"] = _normalize_data_url(result["url"])
        return _json_result(result)

    @app.post("/api/datafiles/delete")
    async def api_datafiles_delete(request: Request) -> JSONResponse:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        result = ctx.datafiles.delete_datafile(payload)
        return _json_result(result)

    @app.post("/api/datafiles/apply")
    async def api_datafiles_apply(request: Request) -> JSONResponse:
        ctx: ServerContext = request.app.state.ctx
        payload = await _read_payload(request)
        result = ctx.datafiles.apply_datafiles(payload)
        return _json_result(result)

    @app.get("/api/data/{path:path}")
    async def api_data(request: Request, path: str) -> Response:
        ctx: ServerContext = request.app.state.ctx
        file_path = _safe_join(ctx.data_dir, path)
        if file_path is None or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return Response(content=file_path.read_bytes(), media_type=_guess_content_type(file_path))

    return app


app = create_app()


def main() -> int:
    url = f"http://{SERVER_HOST}:{SERVER_PORT}/"
    print(f"{APP_TITLE} API server running at {url}")
    _open_browser(url)
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
