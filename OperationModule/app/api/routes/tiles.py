"""Map tile API for the Simulation workspace."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.core.settings import settings
from app.services.mbtiles import MBTiles

router = APIRouter()

MBTILES_FILENAME = "korea.mbtiles"
OSM_PBF_FILENAME = "south-korea-260108.osm.pbf"


def _resolve_resource(filename: str) -> Path:
    local_path = settings.resource_dir / filename
    if local_path.exists():
        return local_path

    reference_path = settings.project_root.parent / "reference" / "uatm_sample" / "resources" / filename
    if reference_path.exists():
        return reference_path

    return local_path


@lru_cache(maxsize=1)
def _get_mbtiles() -> MBTiles:
    path = _resolve_resource(MBTILES_FILENAME)
    if not path.exists():
        raise FileNotFoundError(f"{MBTILES_FILENAME} not found")
    return MBTiles(path)


def _normalize_format(tile_format: str) -> str:
    fmt = (tile_format or "png").lower()
    return "jpg" if fmt == "jpeg" else fmt


def _content_type(tile_format: str) -> str:
    fmt = _normalize_format(tile_format)
    if fmt in {"jpg", "jpeg"}:
        return "image/jpeg"
    if fmt == "png":
        return "image/png"
    if fmt == "webp":
        return "image/webp"
    if fmt == "pbf":
        return "application/vnd.mapbox-vector-tile"
    return "application/octet-stream"


def _format_bounds(bounds: tuple[float, float, float, float] | None) -> list[list[float]] | None:
    if bounds is None:
        return None
    min_lon, min_lat, max_lon, max_lat = bounds
    return [[min_lon, min_lat], [max_lon, max_lat]]


@router.get("/metadata")
async def tile_metadata():
    try:
        mbtiles = _get_mbtiles()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    info = mbtiles.info
    lat, lon, zoom = info.start_view()
    osm_source = _resolve_resource(OSM_PBF_FILENAME)
    return {
        "name": info.name,
        "min_zoom": info.min_zoom,
        "max_zoom": info.max_zoom,
        "tile_format": info.tile_format,
        "scheme": info.scheme,
        "bounds": _format_bounds(info.bounds),
        "center": info.center,
        "start_view": {"lat": lat, "lon": lon, "zoom": zoom},
        "tile_url": f"/api/v1/tiles/{{z}}/{{x}}/{{y}}.{_normalize_format(info.tile_format)}",
        "source_osm_pbf": {"filename": OSM_PBF_FILENAME, "available": osm_source.exists()},
    }


@router.get("/{z:int}/{x:int}/{y:int}.{ext}")
async def read_tile(z: int, x: int, y: int, ext: str) -> Response:
    try:
        mbtiles = _get_mbtiles()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    data = mbtiles.get_tile(z, x, y)
    headers = {"Cache-Control": "public, max-age=86400, immutable"}
    if data is None:
        return Response(content=b"", status_code=204, media_type=_content_type(mbtiles.info.tile_format), headers=headers)

    if mbtiles.info.tile_format == "pbf" and data[:2] == b"\x1f\x8b":
        headers["Content-Encoding"] = "gzip"

    return Response(content=data, media_type=_content_type(mbtiles.info.tile_format), headers=headers)
