"""DTAM Server 설정.

ServerConfig, ModuleEndpoint 등 데이터 클래스 + load_config().
기존 app/config.py 에서 데이터 정의(MESSAGE_TABLE 등)를 model/message.py 로 분리한 뒤
설정 관련 로직만 남긴 것.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .message import MODULE_ROLES


ROOT_DIR = Path(__file__).resolve().parents[2]          # DTAM_CoreServer/
FRAMEWORK_ROOT = ROOT_DIR.parent                         # DTAMFramework/
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"
ICD_DIR = DTAM_SDK_ROOT / "dtam_client" / "icd"
# (라이브 모니터 web 자산은 DTAM_SimulationState/app/web/ 으로 이전됨)

DEFAULT_CONFIG_FILE = ROOT_DIR / "config.json"


@dataclass
class ServerEndpoint:
    bind_ip: str = "0.0.0.0"


@dataclass
class ModuleEndpoint:
    role: str
    display_name: str
    expected_source: str = ""


@dataclass
class ServerConfig:
    server: ServerEndpoint = field(default_factory=ServerEndpoint)
    gui_host: str = "127.0.0.1"
    gui_port: int = 8095
    heartbeat_timeout_s: float = 3.5
    modules: List[ModuleEndpoint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server": asdict(self.server),
            "gui_host": self.gui_host,
            "gui_port": self.gui_port,
            "heartbeat_timeout_s": self.heartbeat_timeout_s,
            "modules": [asdict(m) for m in self.modules],
        }


def default_modules() -> List[ModuleEndpoint]:
    return [
        ModuleEndpoint(role="mission",     display_name="Mission Planner",     expected_source="DTAM_MissionPlanner"),
        ModuleEndpoint(role="monitoring",  display_name="Operations Console",  expected_source="DTAMOperationsConsole"),
        ModuleEndpoint(role="vehicle",     display_name="Air Mobility",        expected_source="DTAMAirMobility"),
        ModuleEndpoint(role="visual",      display_name="Visualization",       expected_source="DTAMVisualization"),
        ModuleEndpoint(role="sim_state",   display_name="Simulation State",    expected_source="DTAM_SimulationState"),
    ]


def load_config(path: Optional[Path] = None) -> ServerConfig:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_FILE
    raw: Dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[DSE] failed to read {cfg_path}: {exc}")

    server_raw = dict(raw.get("server") or {})
    srv = ServerEndpoint(
        bind_ip=str(server_raw.get("bind_ip", "0.0.0.0")),
    )

    gui_host = str(raw.get("gui_host", "127.0.0.1"))
    gui_port = int(raw.get("gui_port", 8095))

    heartbeat_timeout_s = float(raw.get("heartbeat_timeout_s", 3.5))

    modules: List[ModuleEndpoint] = []
    raw_modules = raw.get("modules")
    if isinstance(raw_modules, list) and raw_modules:
        for item in raw_modules:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            if role not in MODULE_ROLES:
                continue
            modules.append(ModuleEndpoint(
                role=role,
                display_name=str(item.get("display_name") or role.title()),
                expected_source=str(item.get("expected_source") or ""),
            ))
    if not modules:
        modules = default_modules()

    return ServerConfig(
        server=srv, gui_host=gui_host, gui_port=gui_port,
        heartbeat_timeout_s=heartbeat_timeout_s,
        modules=modules,
    )
