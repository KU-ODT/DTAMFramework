from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class MBTilesReader:
    """Lazy SQLite reader for MBTiles archives.

    MBTiles stores tiles using TMS coordinates (Y axis flipped). XYZ requests
    from MapLibre/Leaflet are converted on lookup.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._connection: sqlite3.Connection | None = None
        self._metadata: dict[str, str] = {}

    def exists(self) -> bool:
        return self.path.is_file()

    def _ensure_open(self) -> None:
        if self._connection is not None:
            return
        if not self.exists():
            raise FileNotFoundError(f"MBTiles not found: {self.path}")
        self._connection = sqlite3.connect(str(self.path), check_same_thread=False)
        cursor = self._connection.execute("SELECT name, value FROM metadata")
        self._metadata = {str(name): str(value) for name, value in cursor.fetchall()}

    @property
    def metadata(self) -> dict[str, str]:
        with self._lock:
            self._ensure_open()
            return dict(self._metadata)

    def get_tile(self, z: int, x: int, y: int) -> bytes | None:
        tms_y = (1 << z) - 1 - y
        with self._lock:
            self._ensure_open()
            cursor = self._connection.execute(  # type: ignore[union-attr]
                "SELECT tile_data FROM tiles "
                "WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                (z, x, tms_y),
            )
            row = cursor.fetchone()
        return bytes(row[0]) if row else None


def is_gzipped(data: bytes) -> bool:
    return len(data) >= 2 and data[0] == 0x1F and data[1] == 0x8B
