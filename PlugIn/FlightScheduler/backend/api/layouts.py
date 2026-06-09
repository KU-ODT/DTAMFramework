from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from ..services import layout_library

router = APIRouter(prefix="/layouts")


@router.get("/_info")
def layouts_info() -> dict:
    """Where layout files live on disk — surfaced so the UI can tell the user
    exactly where their saves land."""
    return {"directory": str(layout_library.LAYOUT_DIR.resolve())}


@router.get("")
def list_layouts() -> dict:
    return {"items": layout_library.list_layouts()}


@router.get("/{name}")
def get_layout(name: str) -> dict:
    try:
        return layout_library.get_layout(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{name}")
def put_layout(name: str, layout: dict = Body(...)) -> dict:
    try:
        return layout_library.save_layout(name, layout)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{name}")
def delete_layout(name: str) -> dict:
    try:
        layout_library.delete_layout(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": name}
