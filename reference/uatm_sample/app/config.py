from __future__ import annotations

import os
import sys
from pathlib import Path

def _env_path(name: str, fallback: Path) -> Path:
    value = os.getenv(name)
    if not value:
        return fallback
    return Path(value).expanduser().resolve()


def _env_int(name: str, fallback: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return fallback
    try:
        return int(value)
    except ValueError:
        return fallback


def _env_bool(name: str, fallback: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return fallback
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def _runtime_env() -> str:
    raw = os.getenv("UATM_ENV", "").strip().lower()
    if raw in ("prod", "production"):
        return "prod"
    if raw in ("dev", "development", "staging"):
        return "dev"
    return "local"


def _default_bind_host(runtime_env: str) -> str:
    if runtime_env == "prod":
        return "0.0.0.0"
    return "127.0.0.1"


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _default_user_root() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
    if base:
        return Path(base) / "TrafficS"
    return Path.home() / "TrafficS"


ROOT_DIR = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT_DIR
USER_DIR = ROOT_DIR
if _is_frozen():
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", ROOT_DIR))
    USER_DIR = _default_user_root()

root_override = os.getenv("UATM_ROOT_DIR")
if root_override:
    override = Path(root_override).expanduser().resolve()
    BUNDLE_DIR = override
    USER_DIR = override

ROOT_DIR = BUNDLE_DIR

RESOURCES_DIR = _env_path("UATM_RESOURCES_DIR", BUNDLE_DIR / "resources")
DATA_DIR = _env_path("UATM_DATA_DIR", USER_DIR / "data")
WEB_DIR = _env_path("UATM_WEB_DIR", BUNDLE_DIR / "app" / "web")
MBTILES_PATH = _env_path("UATM_MBTILES_PATH", RESOURCES_DIR / "korea.mbtiles")
LOG_DIR = _env_path("UATM_LOG_DIR", USER_DIR / "log")
DEM_DIR = _env_path("UATM_DEM_DIR", RESOURCES_DIR / "dem")
DEM_TILE_SIZE = _env_int("UATM_DEM_TILE_SIZE", 256)
DEM_MAX_ZOOM = _env_int("UATM_DEM_MAX_ZOOM", 12)

RUNTIME_ENV = _runtime_env()
DEFAULT_BIND_HOST = _default_bind_host(RUNTIME_ENV)

SERVER_HOST = os.getenv("UATM_SERVER_HOST", DEFAULT_BIND_HOST)
SERVER_PORT = _env_int("UATM_SERVER_PORT", 8002)
TILE_SERVER_HOST = os.getenv("UATM_TILE_HOST", SERVER_HOST)
TILE_SERVER_PORT = _env_int("UATM_TILE_PORT", 8001)
FRONTEND_HOST = os.getenv("UATM_FRONTEND_HOST", SERVER_HOST)
FRONTEND_PORT = _env_int("UATM_FRONTEND_PORT", 5173)
OPEN_BROWSER = _env_bool("UATM_OPEN_BROWSER", _is_frozen())
ENABLE_FLIGHTPLAN_MODE = _env_bool("UATM_ENABLE_FLIGHTPLAN_MODE", False)

APP_TITLE = "TrafficS"

DEFAULT_CENTER_LAT = 37.5665
DEFAULT_CENTER_LON = 126.978
DEFAULT_START_ZOOM = 11.5
USE_BOUNDS = False

AIRSIM_HOST = "127.0.0.1"
AIRSIM_PORT = 41451
