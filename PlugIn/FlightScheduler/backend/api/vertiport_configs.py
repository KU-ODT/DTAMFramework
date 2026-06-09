from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from ..services import vertiport_config_store

router = APIRouter(prefix="/vertiport-configs")


@router.get("")
def list_configs() -> dict:
    return {"items": vertiport_config_store.list_configs()}


@router.get("/{vertiport_id}")
def get_config(vertiport_id: str) -> dict:
    config = vertiport_config_store.get_config(vertiport_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"No config for {vertiport_id}")
    return config


@router.put("/{vertiport_id}")
def put_config(vertiport_id: str, payload: dict = Body(...)) -> dict:
    try:
        return vertiport_config_store.put_config(vertiport_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{vertiport_id}")
def delete_config(vertiport_id: str) -> dict:
    vertiport_config_store.delete_config(vertiport_id)
    return {"deleted": vertiport_id}
