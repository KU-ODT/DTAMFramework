from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query, Response

from ..services import simulation_service

router = APIRouter(prefix="/simulations")


@router.post("")
def create_simulation(payload: dict = Body(...)) -> dict:
    try:
        return simulation_service.create_simulation(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{simulation_id}")
def get_simulation(simulation_id: str) -> dict:
    try:
        return simulation_service.get_simulation(simulation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{simulation_id}/flights")
def get_flights(
    simulation_id: str,
    origin: str | None = Query(None),
    destination: str | None = Query(None),
    aircraftId: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, gt=0, le=2000),
) -> dict:
    try:
        return simulation_service.get_flight_page(
            simulation_id,
            origin=origin,
            destination=destination,
            aircraft_id=aircraftId,
            offset=offset,
            limit=limit,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{simulation_id}/vertiports/{vertiport_id}")
def get_vertiport_detail(simulation_id: str, vertiport_id: str) -> dict:
    try:
        return simulation_service.get_vertiport_detail(simulation_id, vertiport_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{simulation_id}/snapshot")
def get_snapshot(
    simulation_id: str,
    timeSeconds: float = Query(0, ge=0),
    vertiportId: str | None = Query(None),
) -> dict:
    try:
        return simulation_service.get_snapshot(
            simulation_id,
            time_seconds=timeSeconds,
            vertiport_id=vertiportId,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{simulation_id}/flights.csv")
def export_flights_csv(simulation_id: str) -> Response:
    try:
        data = simulation_service.export_flights_csv(simulation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    headers = {"Content-Disposition": f'attachment; filename="flights_{simulation_id}.csv"'}
    return Response(content=data, media_type="text/csv; charset=utf-8", headers=headers)
