"""Simulation State Server 설정 변수 관리."""
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]       # DTAM_SimulationState/
FRAMEWORK_ROOT = MODULE_ROOT.parent                      # DTAMFramework/
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"

# DB 는 SimulationState 모듈 안에 둔다 (다른 모듈의 ``data/`` 컨벤션과 정렬).
# ``--db-root`` CLI 또는 ``DTAM_DSE_DB_ROOT`` ENV 로 override 가능.
DEFAULT_DB_ROOT = MODULE_ROOT / "data" / "DB"

DEFAULT_WS_URL = "ws://127.0.0.1:8095/ws/dtam"
ROLE_NAME = "sim_state"
SOURCE_NAME = "DTAM_SimulationState"

# 라이브 모니터 웹 UI 자산
WEB_DIR = Path(__file__).resolve().parent / "web"
