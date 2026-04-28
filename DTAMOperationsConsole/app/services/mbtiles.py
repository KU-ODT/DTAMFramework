"""Small MBTiles reader for serving MapLibre tiles from local resources."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import threading


@dataclass(frozen=True)
class MBTilesInfo:
    min_zoom: int
    max_zoom: int
    tile_format: str
    scheme: str
    bounds: tuple[float, float, float, float] | None
    center: tuple[float, float, int] | None
    name: str | None

    def start_view(self) -> tuple[float, float, int]:
        if self.center is not None:
            lon, lat, zoom = self.center
            return lat, lon, zoom
        if self.bounds is not None:
            min_lon, min_lat, max_lon, max_lat = self.bounds
            return (min_lat + max_lat) / 2, (min_lon + max_lon) / 2, min(max(self.min_zoom, 6), self.max_zoom)
        return 35.50521, 128.3287, min(max(self.min_zoom, 7), self.max_zoom)


class MBTiles:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._local = threading.local()
        self._connections: list[sqlite3.Connection] = []
        self._connections_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._tile_cache: OrderedDict[tuple[int, int, int], bytes] = OrderedDict()
        self._tile_cache_size = 768
        self.info = self._load_metadata()

    def close(self) -> None:
        with self._connections_lock:
            connections = list(self._connections)
            self._connections.clear()
        for connection in connections:
            connection.close()

    def get_tile(self, z: int, x: int, y: int) -> bytes | None:
        tile_y = y
        if self.info.scheme == "tms":
            tile_y = (1 << z) - 1 - y

        key = (z, x, tile_y)
        with self._cache_lock:
            cached = self._tile_cache.get(key)
            if cached is not None:
                self._tile_cache.move_to_end(key)
                return cached

        row = self._get_conn().execute(
            """
            SELECT tile_data
            FROM tiles
            WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?
            """,
            (z, x, tile_y),
        ).fetchone()
        if row is None:
            return None

        data = row["tile_data"]
        if isinstance(data, memoryview):
            data = data.tobytes()
        if not isinstance(data, bytes):
            return None

        with self._cache_lock:
            self._tile_cache[key] = data
            self._tile_cache.move_to_end(key)
            if len(self._tile_cache) > self._tile_cache_size:
                self._tile_cache.popitem(last=False)
        return data

    def _load_metadata(self) -> MBTilesInfo:
        with self._open_conn() as connection:
            rows = connection.execute("SELECT name, value FROM metadata").fetchall()
        metadata = {row["name"]: row["value"] for row in rows}

        min_zoom = _parse_int(metadata.get("minzoom"))
        max_zoom = _parse_int(metadata.get("maxzoom"))
        if min_zoom is None or max_zoom is None:
            inferred_min, inferred_max = self._infer_zoom_range()
            min_zoom = inferred_min if min_zoom is None else min_zoom
            max_zoom = inferred_max if max_zoom is None else max_zoom

        return MBTilesInfo(
            min_zoom=min_zoom or 0,
            max_zoom=max_zoom or 0,
            tile_format=(metadata.get("format") or "png").lower(),
            scheme=(metadata.get("scheme") or "tms").lower(),
            bounds=_parse_bounds(metadata.get("bounds")),
            center=_parse_center(metadata.get("center")),
            name=metadata.get("name"),
        )

    def _infer_zoom_range(self) -> tuple[int, int]:
        with self._open_conn() as connection:
            row = connection.execute("SELECT MIN(zoom_level) AS minz, MAX(zoom_level) AS maxz FROM tiles").fetchone()
        min_zoom = row["minz"] if row and row["minz"] is not None else 0
        max_zoom = row["maxz"] if row and row["maxz"] is not None else 0
        return int(min_zoom), int(max_zoom)

    def _open_conn(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _get_conn(self) -> sqlite3.Connection:
        connection = getattr(self._local, "conn", None)
        if connection is None:
            connection = self._open_conn()
            self._local.conn = connection
            with self._connections_lock:
                self._connections.append(connection)
        return connection


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _parse_bounds(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 4:
        return None
    numbers = [_parse_float(part) for part in parts]
    if any(number is None for number in numbers):
        return None
    min_lon, min_lat, max_lon, max_lat = numbers
    return float(min_lon), float(min_lat), float(max_lon), float(max_lat)


def _parse_center(value: str | None) -> tuple[float, float, int] | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 3:
        return None
    lon = _parse_float(parts[0])
    lat = _parse_float(parts[1])
    zoom = _parse_int(parts[2])
    if lon is None or lat is None or zoom is None:
        return None
    return float(lon), float(lat), int(zoom)
