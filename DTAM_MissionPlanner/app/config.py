"""DTAM Mission Planner 런타임 설정.

``data/`` 및 ``resources/`` 는 모듈 디렉토리 안에 위치한다.
환경 변수 ``DTAM_MP_DATA`` / ``DTAM_MP_RESOURCES`` 로 외부 경로 지정 가능.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]              # DTAM_MissionPlanner/
FRAMEWORK_ROOT = ROOT_DIR.parent                            # DTAMFramework/
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"


def _from_env_or(default: Path, env_name: str) -> Path:
    raw = os.environ.get(env_name)
    return Path(raw) if raw else default


RESOURCES_DIR = _from_env_or(ROOT_DIR / "resources", "DTAM_MP_RESOURCES")
DATA_DIR = _from_env_or(ROOT_DIR / "data", "DTAM_MP_DATA")
MBTILES_PATH = RESOURCES_DIR / "korea.mbtiles"
DEM_DIR = RESOURCES_DIR / "dem"
DEM_TILE_SIZE = 256
DEM_MAX_ZOOM = 12

WEB_DIR = ROOT_DIR / "app" / "web"

SERVER_HOST = os.getenv("DTAM_MP_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("DTAM_MP_PORT", "8090"))

# DTAM 통신 기본값 (WebSocket /ws/dtam — DTAM_SimulationState 서버)
DTAM_TARGET_IP = os.getenv("DTAM_MP_TARGET_IP", "127.0.0.1")
DTAM_WS_PORT   = int(os.getenv("DTAM_MP_WS_PORT", "8096"))
# ── legacy (UDP/TCP 시절) — 더 이상 사용하지 않지만 backward-compat 위해 유지 ──
DTAM_TARGET_PORT = int(os.getenv("DTAM_MP_TARGET_PORT", "17000"))
DTAM_MY_IP = os.getenv("DTAM_MP_MY_IP", "0.0.0.0")
DTAM_MY_PORT = int(os.getenv("DTAM_MP_MY_PORT", "17010"))

APP_TITLE = "DTAM Mission Planner"

DEFAULT_CENTER_LAT = 37.5665
DEFAULT_CENTER_LON = 126.978
DEFAULT_START_ZOOM = 11.5
USE_BOUNDS = False
