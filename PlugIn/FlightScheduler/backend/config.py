from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
DATA_DIR = BACKEND_DIR / "data"

_MBTILES_CANDIDATES = ("korea.mbtiles", "map.mbtiles")


def _resolve_default_mbtiles() -> Path:
    for name in _MBTILES_CANDIDATES:
        candidate = DATA_DIR / name
        if candidate.is_file():
            return candidate
    return DATA_DIR / _MBTILES_CANDIDATES[0]


MBTILES_PATH = Path(
    os.environ.get("MBTILES_PATH") or _resolve_default_mbtiles()
).expanduser()

VERTIPORT_CSV = DATA_DIR / "vertiport.csv"
WAYPOINT_CSV = DATA_DIR / "waypoint.csv"
