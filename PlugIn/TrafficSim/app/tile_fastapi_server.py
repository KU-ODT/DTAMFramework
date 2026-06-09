from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
import uvicorn

from app.config import (
    APP_TITLE,
    DEM_DIR,
    DEM_MAX_ZOOM,
    DEM_TILE_SIZE,
    MBTILES_PATH,
    TILE_SERVER_HOST,
    TILE_SERVER_PORT,
)
from app.dem import load_dem_provider
from app.mbtiles import MBTiles


@dataclass
class TileContext:
    mbtiles: MBTiles
    dem_provider: Optional[object]


def _normalize_format(tile_format: str) -> str:
    fmt = (tile_format or "png").lower()
    if fmt == "jpeg":
        return "jpg"
    return fmt


def _content_type(tile_format: str) -> str:
    fmt = _normalize_format(tile_format)
    if fmt in ("jpg", "jpeg"):
        return "image/jpeg"
    if fmt == "png":
        return "image/png"
    if fmt == "webp":
        return "image/webp"
    if fmt == "pbf":
        return "application/vnd.mapbox-vector-tile"
    return "application/octet-stream"


def _format_bounds(bounds: Optional[tuple[float, float, float, float]]):
    if bounds is None:
        return None
    min_lon, min_lat, max_lon, max_lat = bounds
    return [[min_lon, min_lat], [max_lon, max_lat]]


def _build_context() -> TileContext:
    mbtiles = MBTiles(MBTILES_PATH)
    dem_provider = None
    if DEM_DIR.exists():
        candidate = load_dem_provider(DEM_DIR, tile_size=DEM_TILE_SIZE, max_zoom=DEM_MAX_ZOOM)
        if candidate.available:
            dem_provider = candidate
    return TileContext(mbtiles=mbtiles, dem_provider=dem_provider)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = _build_context()
    app.state.ctx = ctx
    try:
        yield
    finally:
        ctx.mbtiles.close()


def create_app() -> FastAPI:
    app = FastAPI(title=f"{APP_TITLE} Tiles", lifespan=lifespan)

    @app.get("/tiles/metadata")
    async def tile_metadata():
        ctx: TileContext = app.state.ctx
        info = ctx.mbtiles.info
        lat, lon, zoom = info.start_view()
        return {
            "min_zoom": info.min_zoom,
            "max_zoom": info.max_zoom,
            "tile_format": info.tile_format,
            "scheme": info.scheme,
            "bounds": _format_bounds(info.bounds),
            "center": info.center,
            "start_view": {"lat": lat, "lon": lon, "zoom": zoom},
            "dem_available": ctx.dem_provider is not None,
            "dem_tile_size": DEM_TILE_SIZE,
            "dem_max_zoom": DEM_MAX_ZOOM,
        }

    @app.get("/tiles/{z:int}/{x:int}/{y:int}.{ext}")
    async def tiles(z: int, x: int, y: int, ext: str) -> Response:
        ctx: TileContext = app.state.ctx
        data = ctx.mbtiles.get_tile(z, x, y)
        if data is None:
            raise HTTPException(status_code=404, detail="Tile not found")
        content_type = _content_type(ctx.mbtiles.info.tile_format)
        headers = {}
        if ctx.mbtiles.info.tile_format == "pbf" and data[:2] == b"\x1f\x8b":
            headers["Content-Encoding"] = "gzip"
        return Response(content=data, media_type=content_type, headers=headers)

    @app.get("/dem/{z:int}/{x:int}/{y:int}.{ext}")
    async def dem(z: int, x: int, y: int, ext: str) -> Response:
        ctx: TileContext = app.state.ctx
        if ctx.dem_provider is None:
            raise HTTPException(status_code=404, detail="DEM unavailable")
        data = ctx.dem_provider.get_tile(z, x, y)
        if data is None:
            raise HTTPException(status_code=404, detail="DEM tile not found")
        return Response(content=data, media_type="image/png")

    return app


app = create_app()


def main() -> int:
    url = f"http://{TILE_SERVER_HOST}:{TILE_SERVER_PORT}/"
    print(f"{APP_TITLE} tile server running at {url}")
    uvicorn.run(app, host=TILE_SERVER_HOST, port=TILE_SERVER_PORT, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
