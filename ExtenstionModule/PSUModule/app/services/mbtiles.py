"""Minimal MBTiles reader used by the PSU map tile endpoint.

This is intentionally small and mirrors the MissionModule tile-serving pattern:
- read metadata once
- convert XYZ Y to TMS Y when needed
- return raw tile bytes so FastAPI can set the proper response headers
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class MBTilesInfo:
    min_zoom: int
    max_zoom: int
    tile_format: str
    scheme: str
    bounds: Optional[tuple[float, float, float, float]]
    center: Optional[tuple[float, float, int]]
    name: Optional[str]

    def start_view(self) -> tuple[float, float, int]:
        """Return a MapLibre-friendly start view as lat, lon, zoom."""
        if self.center:
            lon, lat, zoom = self.center
            return lat, lon, zoom
        if self.bounds:
            min_lon, min_lat, max_lon, max_lat = self.bounds
            return (min_lat + max_lat) / 2.0, (min_lon + max_lon) / 2.0, max(self.min_zoom, min(self.max_zoom, 6))
        return 37.5665, 126.978, max(self.min_zoom, min(self.max_zoom, 11))


class MBTiles:
    """Thread-safe reader for a single MBTiles SQLite file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.info = self._load_metadata()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def get_tile(self, z: int, x: int, y: int) -> Optional[bytes]:
        tile_y = int(y)
        if self.info.scheme == "tms":
            tile_y = (1 << int(z)) - 1 - int(y)
        with self._lock:
            row = self._conn.execute(
                """
                SELECT tile_data
                FROM tiles
                WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?
                """,
                (int(z), int(x), tile_y),
            ).fetchone()
        if row is None:
            return None
        return row["tile_data"]

    def metadata_payload(self) -> dict[str, object]:
        lat, lon, zoom = self.info.start_view()
        return {
            "path": str(self.path),
            "name": self.info.name,
            "minZoom": self.info.min_zoom,
            "maxZoom": self.info.max_zoom,
            "tileFormat": self.info.tile_format,
            "scheme": self.info.scheme,
            "bounds": self.info.bounds,
            "center": [lon, lat],
            "zoom": zoom,
        }

    def _load_metadata(self) -> MBTilesInfo:
        meta: dict[str, str] = {}
        with self._lock:
            rows = self._conn.execute("SELECT name, value FROM metadata").fetchall()
        for row in rows:
            meta[str(row["name"])] = str(row["value"])

        min_zoom = _parse_int(meta.get("minzoom"))
        max_zoom = _parse_int(meta.get("maxzoom"))
        if min_zoom is None or max_zoom is None:
            inferred_min, inferred_max = self._infer_zoom_range()
            min_zoom = inferred_min if min_zoom is None else min_zoom
            max_zoom = inferred_max if max_zoom is None else max_zoom

        return MBTilesInfo(
            min_zoom=min_zoom or 0,
            max_zoom=max_zoom or 14,
            tile_format=(meta.get("format") or meta.get("tile_format") or "pbf").lower(),
            scheme=(meta.get("scheme") or "tms").lower(),
            bounds=_parse_bounds(meta.get("bounds")),
            center=_parse_center(meta.get("center")),
            name=meta.get("name"),
        )

    def _infer_zoom_range(self) -> tuple[int, int]:
        with self._lock:
            row = self._conn.execute("SELECT MIN(zoom_level) AS min_zoom, MAX(zoom_level) AS max_zoom FROM tiles").fetchone()
        if row is None:
            return 0, 14
        return int(row["min_zoom"] or 0), int(row["max_zoom"] or 14)


def _parse_int(value: str | None) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except ValueError:
        return None


def _parse_bounds(value: str | None) -> Optional[tuple[float, float, float, float]]:
    if not value:
        return None
    try:
        parts = [float(part.strip()) for part in str(value).split(",")]
    except ValueError:
        return None
    if len(parts) != 4:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def _parse_center(value: str | None) -> Optional[tuple[float, float, int]]:
    if not value:
        return None
    raw = str(value).strip()
    try:
        if raw.startswith("["):
            parts = json.loads(raw)
        else:
            parts = [part.strip() for part in raw.split(",")]
        if len(parts) < 2:
            return None
        lon = float(parts[0])
        lat = float(parts[1])
        zoom = int(float(parts[2])) if len(parts) >= 3 else 11
        return lon, lat, zoom
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
