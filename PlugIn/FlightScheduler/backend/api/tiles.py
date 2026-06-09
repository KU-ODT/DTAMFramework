from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from ..config import MBTILES_PATH
from ..services.mbtiles import MBTilesReader, is_gzipped

router = APIRouter()
_reader = MBTilesReader(MBTILES_PATH)


@router.get("/tiles/status")
def tile_status() -> dict:
    return {
        "mbtilesPath": str(MBTILES_PATH),
        "available": _reader.exists(),
    }


@router.get("/tiles/metadata")
def tile_metadata() -> dict:
    if not _reader.exists():
        raise HTTPException(
            status_code=404,
            detail=f"MBTiles file not found at {MBTILES_PATH}. "
            "Drop a .mbtiles file there or set MBTILES_PATH.",
        )
    return _reader.metadata


@router.get("/tiles/{z}/{x}/{y}.pbf")
def get_tile(z: int, x: int, y: int) -> Response:
    if not _reader.exists():
        raise HTTPException(status_code=404, detail="MBTiles file not configured.")
    data = _reader.get_tile(z, x, y)
    if data is None:
        return Response(status_code=204)
    headers = {"Cache-Control": "public, max-age=86400"}
    if is_gzipped(data):
        headers["Content-Encoding"] = "gzip"
    return Response(content=data, media_type="application/x-protobuf", headers=headers)
