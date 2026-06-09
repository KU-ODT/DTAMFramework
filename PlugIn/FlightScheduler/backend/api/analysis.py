from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from backend.services import analysis_export


router = APIRouter(prefix="/analysis")


@router.post("/exports")
def save_analysis_export(payload: dict = Body(...)) -> dict:
    """Persist the analysis tab result payload as timestamped CSV files."""
    try:
        return analysis_export.save_analysis_export(payload)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
