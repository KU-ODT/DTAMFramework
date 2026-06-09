"""DTAM Mission Planner 런타임 설정.

``data/`` 및 ``resources/`` 는 기본적으로 odt_mp 의 것을 그대로 재사용한다
(같은 CSV / mbtiles / DEM / 레이아웃이 필요하므로). 환경 변수로 재정의 가능.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]              # DTAM_MissionManagement/
FRAMEWORK_ROOT = ROOT_DIR.parent                            # DTAM/
ODT_MP_ROOT = FRAMEWORK_ROOT / "odt_mp"
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"

# ── 리소스 경로 (odt_mp 의 실데이터를 그대로 사용) ──────────────────────────
def _first_existing(*candidates: Path) -> Path:
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


RESOURCES_DIR = _first_existing(
    Path(os.environ.get("DTAM_MP_RESOURCES", "")) if os.environ.get("DTAM_MP_RESOURCES") else ROOT_DIR / "resources",
    ROOT_DIR / "resources",
    ODT_MP_ROOT / "resources",
)
DATA_DIR = _first_existing(
    Path(os.environ.get("DTAM_MP_DATA", "")) if os.environ.get("DTAM_MP_DATA") else ROOT_DIR / "data",
    ROOT_DIR / "data",
    ODT_MP_ROOT / "data",
)
MBTILES_PATH = RESOURCES_DIR / "korea.mbtiles"
DEM_DIR = RESOURCES_DIR / "dem"
DEM_TILE_SIZE = 256
DEM_MAX_ZOOM = 12

WEB_DIR = ROOT_DIR / "app" / "web"

SERVER_HOST = os.getenv("DTAM_MP_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("DTAM_MP_PORT", "8090"))

# DTAM 3001 송신 기본값 (AM_main.py 기본 listen 포트와 맞춘다)
DTAM_TARGET_IP = os.getenv("DTAM_MP_TARGET_IP", "127.0.0.1")
DTAM_TARGET_PORT = int(os.getenv("DTAM_MP_TARGET_PORT", "17000"))  # UDP base; TCP = +1
DTAM_MY_IP = os.getenv("DTAM_MP_MY_IP", "0.0.0.0")
DTAM_MY_PORT = int(os.getenv("DTAM_MP_MY_PORT", "17010"))

APP_TITLE = "DTAM Mission Planner"

DEFAULT_CENTER_LAT = 37.5665
DEFAULT_CENTER_LON = 126.978
DEFAULT_START_ZOOM = 11.5
USE_BOUNDS = False
