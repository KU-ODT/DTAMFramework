"""MBTiles 벡터 타일 + DEM 타일 서빙."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from .. import server   # 공유 싱글턴 (mbtiles, dem_provider) 접근

router = APIRouter()


@router.get("/tiles/{z}/{x}/{y}.pbf")
async def get_tile(z: int, x: int, y: int) -> Response:
    if server.mbtiles is None:
        return Response(status_code=404)
    data = server.mbtiles.get_tile(z, x, y)
    if data is None:
        return Response(status_code=204)
    headers = {
        "Content-Type": "application/vnd.mapbox-vector-tile",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "public, max-age=86400",
    }
    if len(data) >= 2 and data[0] == 0x1f and data[1] == 0x8b:
        headers["Content-Encoding"] = "gzip"
    return Response(content=data, headers=headers)


@router.get("/dem/{z}/{x}/{y}.png")
async def get_dem_tile(z: int, x: int, y: int) -> Response:
    if server.dem_provider is None or not server.dem_provider.available:
        return Response(status_code=404)
    data = server.dem_provider.get_tile(z, x, y)
    if data is None:
        return Response(status_code=204)
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )
