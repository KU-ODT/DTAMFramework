"""DTAM Mission Planner path and runtime settings.

``app/web/`` contains the web frontend. ``data/`` and ``resources/`` stay under
the module directory by default because they include runtime data and large map
assets. Set ``DTAM_MP_WEB``, ``DTAM_MP_DATA`` or ``DTAM_MP_RESOURCES`` to
override those paths.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent                   # MissionModule/app/
ROOT_DIR = APP_DIR.parent                                   # MissionModule/
FRAMEWORK_ROOT = ROOT_DIR.parent                            # DTAMFramework/
DTAMSDK_ROOT = FRAMEWORK_ROOT / "DTAMSDK"


def _first_existing(default: Path, *fallbacks: Path) -> Path:
    for path in (default, *fallbacks):
        if path.exists():
            return path
    return default


def _from_env_or(default: Path, env_name: str, *fallbacks: Path) -> Path:
    raw = os.environ.get(env_name)
    return Path(raw) if raw else _first_existing(default, *fallbacks)


RESOURCES_DIR = _from_env_or(ROOT_DIR / "resources", "DTAM_MP_RESOURCES", APP_DIR / "resources")
DATA_DIR = _from_env_or(ROOT_DIR / "data", "DTAM_MP_DATA", APP_DIR / "data")
MBTILES_PATH = RESOURCES_DIR / "korea.mbtiles"
DEM_DIR = RESOURCES_DIR / "dem"
DEM_TILE_SIZE = 256
DEM_MAX_ZOOM = 12

WEB_DIR = _from_env_or(APP_DIR / "web", "DTAM_MP_WEB", ROOT_DIR / "web")
STATIC_DIR = WEB_DIR
TEMPLATE_DIR = WEB_DIR

SERVER_HOST = os.getenv("DTAM_MP_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("DTAM_MP_PORT", "8090"))

# DTAM communication defaults (StateServerModule WebSocket /ws/dtam)
DTAM_TARGET_IP = os.getenv("DTAM_MP_TARGET_IP", "127.0.0.1")
DTAM_WS_PORT   = int(os.getenv("DTAM_MP_WS_PORT", "8096"))

APP_TITLE = "DTAM Mission Planner"

DEFAULT_CENTER_LAT = 37.5665
DEFAULT_CENTER_LON = 126.978
DEFAULT_START_ZOOM = 11.5
USE_BOUNDS = False
