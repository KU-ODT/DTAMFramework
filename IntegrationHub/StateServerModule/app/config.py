"""Configuration values for the Simulation State Server.
"""
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]       # StateServerModule/
FRAMEWORK_ROOT = MODULE_ROOT.parents[1]                  # DTAMFramework/
DTAMSDK_ROOT = FRAMEWORK_ROOT / "DTAMSDK"

# Registration handling
# Registration handling
DEFAULT_DB_ROOT = MODULE_ROOT / "data" / "DB"

DEFAULT_WS_URL = "ws://127.0.0.1:8096/ws/dtam"
ROLE_NAME = "sim_state"
SOURCE_NAME = "StateServerModule"

# Registration handling
WEB_DIR = Path(__file__).resolve().parent / "web"
