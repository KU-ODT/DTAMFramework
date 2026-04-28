"""FastAPI app factory — DTAMAirMobility dashboard."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .services.integrated_service import ClockMode, IntegratedAirMobilityService

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
STATIC_DIR = WEB_DIR
TEMPLATE_DIR = WEB_DIR


def _status_to_dict(service: IntegratedAirMobilityService) -> Dict[str, Any]:
    st = service.status()
    return {
        "clock_mode": st.clock_mode,
        "running": st.running,
        "publisher_connected": st.publisher_connected,
        "publisher_error": st.publisher_error,
        "target_ip": service.publisher.target_ip,
        # ws_port + server_url 이 실제 연결 정보. target_port/my_port 는 legacy 표시용.
        "ws_port": service.ws_port,
        "server_url": service.module.server_url,
        "target_port": service.publisher.target_port,   # legacy display
        "my_port": service.publisher.my_port,           # legacy display
        "sim_time_s": st.sim_time_s,
        "sim_time_hms": st.sim_time_hms,
        "rx_3001_count": st.rx_3001_count,
        "rx_0003_count": st.rx_0003_count,
        "rx_2002_count": st.rx_2002_count,
        "rx_3002_count": st.rx_3002_count,
        "rx_3003_count": st.rx_3003_count,
        "last_rx_3001": st.last_rx_3001,
        "last_rx_0003": st.last_rx_0003,
        "last_rx_2002": st.last_rx_2002,
        "last_rx_3002": st.last_rx_3002,
        "last_rx_3003": st.last_rx_3003,
        "last_heartbeat_error": st.last_heartbeat_error,
        "vehicles": [
            {
                "vehicle_id": v.vehicle_id,
                "flight_plan_number": v.flight_plan_number,
                "state": v.state.value,
                "etot_s": v.etot_s,
                "elapsed_s": v.elapsed_s,
                "total_duration_s": v.total_duration_s,
                "last_point": v.last_point,
                "last_error": v.last_error,
            }
            for v in st.vehicles
        ],
    }


def create_app(service: Optional[IntegratedAirMobilityService] = None) -> FastAPI:
    """Create the FastAPI app. `service` 가 None 이면 기본값으로 새로 생성."""
    svc = service or IntegratedAirMobilityService(
        target_ip="127.0.0.1",
        ws_port=8096,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        try:
            svc.close()
        except Exception:
            pass

    app = FastAPI(
        title="DTAMAirMobility",
        summary="Flight plan → 10 Hz trajectory → DTAM 4001 publisher.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.service = svc

    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        # Starlette ≥0.29 은 request 를 첫 인자로 요구. 구버전 호환 위해 fallback.
        try:
            return templates.TemplateResponse(request, "index.html")
        except TypeError:
            return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/api/status")
    async def api_status() -> Dict[str, Any]:
        return _status_to_dict(svc)

    @app.post("/api/publisher")
    async def api_publisher(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        svc.reconfigure_publisher(
            target_ip=body.get("target_ip"),
            target_port=int(body["target_port"]) if body.get("target_port") is not None else None,
            my_port=int(body["my_port"]) if body.get("my_port") is not None else None,
        )
        return _status_to_dict(svc)

    @app.post("/api/plans")
    async def api_add_plan(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        """body 는 비행계획 JSON (단일 object 또는 list)."""
        try:
            ids = svc.add_plans_from_json(body)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid plan: {exc}")
        return {"added": ids, "status": _status_to_dict(svc)}

    @app.post("/api/plans/batch")
    async def api_add_plans_batch(body: List[Dict[str, Any]] = Body(...)) -> Dict[str, Any]:
        """브라우저에서 파일을 읽어 여러 플랜을 한번에 등록."""
        added_all: List[str] = []
        errors: List[str] = []
        for data in body:
            try:
                added_all.extend(svc.add_plans_from_json(data))
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        return {"added": added_all, "errors": errors, "status": _status_to_dict(svc)}

    @app.delete("/api/plans/{vehicle_id}")
    async def api_remove_plan(vehicle_id: str) -> Dict[str, Any]:
        ok = svc.remove_plan(vehicle_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"unknown vehicle: {vehicle_id}")
        return _status_to_dict(svc)

    @app.delete("/api/plans")
    async def api_clear_plans() -> Dict[str, Any]:
        svc.clear_plans()
        return _status_to_dict(svc)

    @app.post("/api/clock/mode")
    async def api_clock_mode(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        mode = body.get("mode")
        try:
            svc.set_clock_mode(ClockMode(str(mode)))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _status_to_dict(svc)

    @app.post("/api/clock/feed")
    async def api_feed_time(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        hms = body.get("hms")
        sec = body.get("seconds")
        try:
            if hms is not None:
                svc.feed_time_hhmmss(str(hms))
            elif sec is not None:
                svc.feed_time_seconds(float(sec))
            else:
                raise ValueError("'hms' or 'seconds' required")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _status_to_dict(svc)

    @app.post("/api/clock/step")
    async def api_step_once(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        hms = body.get("hms")
        sec = body.get("seconds")
        try:
            if hms is not None:
                parts = str(hms).split(":")
                sim_s = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            elif sec is not None:
                sim_s = float(sec)
            else:
                raise ValueError("'hms' or 'seconds' required")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        svc.step_once(float(sim_s))
        return _status_to_dict(svc)

    @app.post("/api/service/start")
    async def api_start(body: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        mode = body.get("mode")
        if mode:
            try:
                svc.set_clock_mode(ClockMode(str(mode)))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        svc.start()
        return _status_to_dict(svc)

    @app.post("/api/service/stop")
    async def api_stop() -> Dict[str, Any]:
        svc.stop()
        return _status_to_dict(svc)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
