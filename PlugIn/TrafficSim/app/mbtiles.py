from __future__ import annotations

from dataclasses import dataclass
from collections import OrderedDict
from pathlib import Path
import sqlite3
import threading
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
        if self.center:
            lon, lat, zoom = self.center
            return lat, lon, zoom
        if self.bounds:
            min_lon, min_lat, max_lon, max_lat = self.bounds
            lat = (min_lat + max_lat) / 2.0
            lon = (min_lon + max_lon) / 2.0
            zoom = max(self.min_zoom, min(self.max_zoom, 6))
            return lat, lon, zoom
        zoom = max(self.min_zoom, min(self.max_zoom, 4))
        return 0.0, 0.0, zoom


class MBTiles:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._local = threading.local()
        self._connections: list[sqlite3.Connection] = []
        self._connections_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._tile_cache: OrderedDict[tuple[int, int, int], bytes] = OrderedDict()
        self._tile_cache_size = 512
        self.info = self._load_metadata()

    def close(self) -> None:
        with self._connections_lock:
            conns = list(self._connections)
            self._connections.clear()
        for conn in conns:
            conn.close()

    def get_tile(self, z: int, x: int, y: int) -> Optional[bytes]:
        tile_y = y
        if self.info.scheme == "tms":
            tile_y = (1 << z) - 1 - y
        key = (z, x, tile_y)
        with self._cache_lock:
            cached = self._tile_cache.get(key)
            if cached is not None:
                self._tile_cache.move_to_end(key)
                return cached
        conn = self._get_conn()
        row = conn.execute(
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
        if isinstance(data, bytes):
            with self._cache_lock:
                self._tile_cache[key] = data
                self._tile_cache.move_to_end(key)
                if len(self._tile_cache) > self._tile_cache_size:
                    self._tile_cache.popitem(last=False)
            return data
        return None

    def _load_metadata(self) -> MBTilesInfo:
        meta: dict[str, str] = {}
        conn = self._open_conn()
        try:
            rows = conn.execute("SELECT name, value FROM metadata").fetchall()
        finally:
            conn.close()
        for row in rows:
            meta[row["name"]] = row["value"]

        min_zoom = _parse_int(meta.get("minzoom"))
        max_zoom = _parse_int(meta.get("maxzoom"))
        if min_zoom is None or max_zoom is None:
            inferred_min, inferred_max = self._infer_zoom_range()
            min_zoom = inferred_min if min_zoom is None else min_zoom
            max_zoom = inferred_max if max_zoom is None else max_zoom

        bounds = _parse_bounds(meta.get("bounds"))
        center = _parse_center(meta.get("center"))

        tile_format = meta.get("format", "png").lower()
        scheme = meta.get("scheme", "tms").lower()
        name = meta.get("name")

        return MBTilesInfo(
            min_zoom=min_zoom or 0,
            max_zoom=max_zoom or 0,
            tile_format=tile_format,
            scheme=scheme,
            bounds=bounds,
            center=center,
            name=name,
        )

    def _infer_zoom_range(self) -> tuple[int, int]:
        conn = self._open_conn()
        try:
            row = conn.execute(
                "SELECT MIN(zoom_level) AS minz, MAX(zoom_level) AS maxz FROM tiles"
            ).fetchone()
        finally:
            conn.close()
        minz = row["minz"] if row and row["minz"] is not None else 0
        maxz = row["maxz"] if row and row["maxz"] is not None else 0
        return int(minz), int(maxz)

    def _open_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._open_conn()
            self._local.conn = conn
            with self._connections_lock:
                self._connections.append(conn)
        return conn


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except ValueError:
        return None


def _parse_bounds(value: Optional[str]) -> Optional[tuple[float, float, float, float]]:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 4:
        return None
    numbers: list[float] = []
    for part in parts:
        number = _parse_float(part)
        if number is None:
            return None
        numbers.append(number)
    min_lon, min_lat, max_lon, max_lat = numbers
    return (min_lon, min_lat, max_lon, max_lat)


def _parse_center(value: Optional[str]) -> Optional[tuple[float, float, int]]:
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
    return (float(lon), float(lat), int(zoom))
