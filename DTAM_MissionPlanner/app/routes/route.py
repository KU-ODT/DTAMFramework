"""경로 계산 라우트 (`/api/route`, `/api/route/via`)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import server

router = APIRouter(prefix="/api/route")


@router.post("")
async def compute_route(request: Request) -> JSONResponse:
    body = await request.json()
    if server.route_planner is None:
        return JSONResponse({"error": "Route planner not loaded"}, status_code=500)
    start = body.get("start")
    end = body.get("end")
    include_arcs = body.get("include_arcs", True)
    if not start or not end:
        return JSONResponse({"error": "start and end required"}, status_code=400)
    try:
        result = server.route_planner.find_route(start, end, include_turn_arcs=include_arcs)
        return JSONResponse(server._route_payload_response(start, end, result))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@router.post("/via")
async def compute_route_via(request: Request) -> JSONResponse:
    body = await request.json()
    if server.route_planner is None:
        return JSONResponse({"error": "Route planner not loaded"}, status_code=500)
    start = body.get("start")
    end = body.get("end")
    via = body.get("via", [])
    include_arcs = body.get("include_arcs", True)
    if not start or not end:
        return JSONResponse({"error": "start and end required"}, status_code=400)
    try:
        result = server.route_planner.find_route_via(
            start, end, via, include_turn_arcs=include_arcs
        )
        return JSONResponse(server._route_payload_response(start, end, result))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
