"""DTAM Server 설정.

ServerConfig, ModuleEndpoint 등 데이터 클래스 + load_config().
기존 app/config.py 에서 데이터 정의(MESSAGE_TABLE 등)를 model/message.py 로 분리한 뒤
설정 관련 로직만 남긴 것.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .message import MODULE_ROLES


ROOT_DIR = Path(__file__).resolve().parents[2]          # DTAM_CoreServer/
FRAMEWORK_ROOT = ROOT_DIR.parent                         # DTAMFramework/
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"
DEFAULT_DB_ROOT = FRAMEWORK_ROOT / "DB"
ICD_DIR = DTAM_SDK_ROOT / "dtam_client" / "icd"
# (라이브 모니터 web 자산은 DTAM_SimulationState/app/web/ 으로 이전됨)

DEFAULT_CONFIG_FILE = ROOT_DIR / "config.json"


@dataclass
class ServerEndpoint:
    bind_ip: str = "0.0.0.0"
    udp_port: int = 17000

    @property
    def tcp_port(self) -> int:
        return self.udp_port + 1


@dataclass
class ModuleEndpoint:
    role: str
    display_name: str
    ip: str = "127.0.0.1"
    udp_port: int = 17010
    tcp_port: Optional[int] = None
    expected_source: str = ""

    @property
    def resolved_tcp_port(self) -> int:
        return int(self.tcp_port) if self.tcp_port is not None else int(self.udp_port) + 1


@dataclass
class ServerConfig:
    server: ServerEndpoint = field(default_factory=ServerEndpoint)
    gui_host: str = "127.0.0.1"
    gui_port: int = 8095
    db_root: Path = field(default_factory=lambda: DEFAULT_DB_ROOT)
    heartbeat_timeout_s: float = 3.5
    modules: List[ModuleEndpoint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server": asdict(self.server),
            "gui_host": self.gui_host,
            "gui_port": self.gui_port,
            "db_root": str(self.db_root),
            "heartbeat_timeout_s": self.heartbeat_timeout_s,
            "modules": [asdict(m) for m in self.modules],
        }


def default_modules() -> List[ModuleEndpoint]:
    return [
        ModuleEndpoint(role="mission", display_name="Mission Planner",
                       ip="127.0.0.1", udp_port=17010, expected_source="DTAM_MissionPlanner"),
        ModuleEndpoint(role="monitoring", display_name="Operations Console",
                       ip="127.0.0.1", udp_port=17020, expected_source="DTAMOperationsConsole"),
        ModuleEndpoint(role="vehicle", display_name="Air Mobility",
                       ip="127.0.0.1", udp_port=17030, expected_source="DTAMAirMobility"),
        ModuleEndpoint(role="visual", display_name="Visualization",
                       ip="127.0.0.1", udp_port=17040, expected_source="DTAMVisualization"),
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
        udp_port=int(server_raw.get("udp_port", 17000)),
    )

    gui_host = str(raw.get("gui_host", "127.0.0.1"))
    gui_port = int(raw.get("gui_port", 8095))

    db_root_env = os.environ.get("DTAM_DSE_DB_ROOT")
    if db_root_env:
        db_root = Path(db_root_env)
    else:
        raw_db = raw.get("db_root")
        if raw_db:
            db_root = Path(raw_db)
            if not db_root.is_absolute():
                db_root = (cfg_path.parent / db_root).resolve()
        else:
            db_root = DEFAULT_DB_ROOT

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
                ip=str(item.get("ip") or "127.0.0.1"),
                udp_port=int(item.get("udp_port") or 17010),
                tcp_port=int(item["tcp_port"]) if item.get("tcp_port") is not None else None,
                expected_source=str(item.get("expected_source") or ""),
            ))
    if not modules:
        modules = default_modules()

    return ServerConfig(
        server=srv, gui_host=gui_host, gui_port=gui_port,
        db_root=db_root, heartbeat_timeout_s=heartbeat_timeout_s,
        modules=modules,
    )
