"""경로 계산 라우트 (`/api/route`, `/api/route/via`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from .. import server
from ..deps import get_route_planner
from ..services.route_planner import RoutePlanner

router = APIRouter(prefix="/api/route")


@router.post("")
async def compute_route(
    request: Request,
    rp: RoutePlanner = Depends(get_route_planner),
) -> JSONResponse:
    body = await request.json()
    start = body.get("start")
    end = body.get("end")
    include_arcs = body.get("include_arcs", True)
    if not start or not end:
        return JSONResponse({"error": "start and end required"}, status_code=400)
    try:
        result = rp.find_route(start, end, include_turn_arcs=include_arcs)
        return JSONResponse(server._route_payload_response(start, end, result))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/via")
async def compute_route_via(
    request: Request,
    rp: RoutePlanner = Depends(get_route_planner),
) -> JSONResponse:
    body = await request.json()
    start = body.get("start")
    end = body.get("end")
    via = body.get("via", [])
    include_arcs = body.get("include_arcs", True)
    if not start or not end:
        return JSONResponse({"error": "start and end required"}, status_code=400)
    try:
        result = rp.find_route_via(start, end, via, include_turn_arcs=include_arcs)
        return JSONResponse(server._route_payload_response(start, end, result))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
