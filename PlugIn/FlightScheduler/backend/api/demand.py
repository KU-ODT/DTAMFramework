from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query, Response

from ..services import demand_service

router = APIRouter(prefix="/demand")


@router.post("/scenarios")
def create_scenario(payload: dict = Body(...)) -> dict:
    try:
        return demand_service.create_scenario(payload)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> dict:
    try:
        return demand_service.get_scenario(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}/passengers")
def get_passenger_page(
    scenario_id: str,
    origin: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, gt=0, le=2000),
) -> dict:
    try:
        return demand_service.get_passenger_page(
            scenario_id, origin=origin, offset=offset, limit=limit
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}/arrival-hours")
def get_arrival_hours(scenario_id: str, origin: str | None = Query(None)) -> dict:
    try:
        return demand_service.get_arrival_hours(scenario_id, origin=origin)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}/od-hours")
def get_od_hours(scenario_id: str) -> dict:
    try:
        return demand_service.get_od_hours(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}/passengers.csv")
def export_passengers_csv(scenario_id: str, origin: str | None = Query(None)) -> Response:
    try:
        data = demand_service.export_passengers_csv(scenario_id, origin=origin)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    headers = {"Content-Disposition": f'attachment; filename="passengers_{scenario_id}.csv"'}
    return Response(content=data, media_type="text/csv; charset=utf-8", headers=headers)
