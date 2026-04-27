"""Simulation State Server 설정 변수 관리."""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]          # DTAM_SimulationState/
FRAMEWORK_ROOT = ROOT_DIR.parent                         # DTAMFramework/
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"
DEFAULT_DB_ROOT = FRAMEWORK_ROOT / "DB"

DEFAULT_WS_URL = "ws://127.0.0.1:8095/ws/dtam"
ROLE_NAME = "sim_state"
SOURCE_NAME = "DTAM_SimulationState"
