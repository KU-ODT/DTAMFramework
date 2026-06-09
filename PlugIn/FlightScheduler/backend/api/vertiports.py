from __future__ import annotations

from fastapi import APIRouter

from ..services.vertiport_loader import load_vertiports

router = APIRouter()


@router.get("/vertiports")
def list_vertiports() -> dict:
    return {"items": load_vertiports()}
