"""DTAM Server Emulator configuration.

- 서버 자신의 수신 endpoint (UDP port / TCP port = UDP+1)
- 알려진 모듈 4종의 endpoint (mission / monitoring / vehicle / visual)
- Database 루트 디렉토리 (기본: DTAM/Database/)
- HTTP GUI 포트

환경 변수 및 config.json 으로 재정의 가능하며, GUI 런타임 내에서도
PATCH 로 업데이트 가능.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]          # DTAM_Server/
FRAMEWORK_ROOT = ROOT_DIR.parent                         # DTAM/
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"
DEFAULT_DB_ROOT = FRAMEWORK_ROOT / "Database"
WEB_DIR = ROOT_DIR / "app" / "web"

DEFAULT_CONFIG_FILE = ROOT_DIR / "config.json"


# 시퀀스 다이어그램의 actor id 와 동일한 키를 쓴다.
MODULE_ROLES: List[str] = ["mission", "monitoring", "vehicle", "visual"]

# 메시지 ID → (이름, 전송 프로토콜). ICD 기준.
MESSAGE_TABLE: Dict[str, Dict[str, Any]] = {
    "0002": {"name": "Module Status",            "proto": "udp", "direction": "module->server", "rate_hz": 1.0},
    "0003": {"name": "Common Time Info",         "proto": "udp", "direction": "server->module", "rate_hz": 1.0},
    "1001": {"name": "Sim Mode Setup",           "proto": "udp", "direction": "user->server",   "rate_hz": 0.0},
    "1002": {"name": "Simulation Setup",         "proto": "udp", "direction": "user->server",   "rate_hz": 0.0},
    "1003": {"name": "Scenario Setup",           "proto": "udp", "direction": "user->server",   "rate_hz": 0.0},
    "2001": {"name": "Flight Plan Request",      "proto": "tcp", "direction": "user->server",   "rate_hz": 0.0},
    "2002": {"name": "DTAM Execute",             "proto": "tcp", "direction": "user->server",   "rate_hz": 0.0},
    "3001": {"name": "Scheduled Flight",         "proto": "tcp", "direction": "mission->server","rate_hz": 0.0},
    "3002": {"name": "Strategic Separation",     "proto": "tcp", "direction": "mission->server","rate_hz": 0.0},
    "3003": {"name": "Tactical Separation",      "proto": "tcp", "direction": "mission->server","rate_hz": 0.0},
    "4001": {"name": "Vehicle Status",           "proto": "udp", "direction": "vehicle->server","rate_hz": 10.0},
    "4101": {"name": "Camera Image Frame",       "proto": "tcp", "direction": "visual->server", "rate_hz": 5.0},
}

# 메시지 ID → Database 저장 폴더명. (timestamp 하위 경로)
DB_FOLDER_FOR_MID: Dict[str, str] = {
    "0002": "ModuleStatus",
    "0003": "CommonTimeInfo",
    "1001": "SimModeSetup",
    "1002": "SimulationSetup",
    "1003": "ScenarioSetup",
    "2001": "FlightPlanRequest",
    "2002": "DtamExecute",
    "3001": "ScheduledFlight",
    "3002": "ScheduledFlightModification",
    "3003": "TacticalActionCommand",
    "4001": "VehicleStatus",
    "4101": "CameraImage",
}

# 시퀀스 다이어그램 기준 포워딩 규칙.
#   mid → list of roles to forward to.
FORWARD_RULES: Dict[str, List[str]] = {
    "2001": ["mission"],
    "2002": ["mission", "monitoring", "vehicle", "visual"],
    "3001": ["vehicle"],
    "3002": ["vehicle"],
    "3003": ["vehicle"],
    "4001": ["monitoring", "visual"],
    "4101": ["monitoring"],
}

# 서버가 주기적으로 푸시해야 하는 메시지.
PUSH_SCHEDULE: Dict[str, Dict[str, Any]] = {
    "0003": {"rate_hz": 1.0, "targets": ["vehicle", "visual"]},
}


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
    expected_source: str = ""     # 0002 Module Status 의 "source" 필드 기대값

    @property
    def resolved_tcp_port(self) -> int:
        return int(self.tcp_port) if self.tcp_port is not None else int(self.udp_port) + 1


@dataclass
class ServerConfig:
    server: ServerEndpoint = field(default_factory=ServerEndpoint)
    gui_host: str = "127.0.0.1"
    gui_port: int = 8095
    db_root: Path = field(default_factory=lambda: DEFAULT_DB_ROOT)
    heartbeat_timeout_s: float = 3.5        # 0002 이 이 시간 내 안 오면 disconnected
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
    """프레임워크 기본 포트 레이아웃.

    Server 는 17000/17001 을 쓰므로 각 모듈은 17010~ 에서 10 씩 띄워 할당.
    필요하면 ``config.json`` 에서 덮어쓰면 된다.
    """
    return [
        ModuleEndpoint(
            role="mission", display_name="Mission Planner",
            ip="127.0.0.1", udp_port=17010,
            expected_source="DTAM_MissionManagement",
        ),
        ModuleEndpoint(
            role="monitoring", display_name="Operations Console",
            ip="127.0.0.1", udp_port=17020,
            expected_source="DTAMOperationsConsole",
        ),
        ModuleEndpoint(
            role="vehicle", display_name="Air Mobility",
            ip="127.0.0.1", udp_port=17030,
            expected_source="DTAMAirVehicle",
        ),
        ModuleEndpoint(
            role="visual", display_name="Visualization",
            ip="127.0.0.1", udp_port=17040,
            expected_source="DTAMVisualization",
        ),
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
                # config.json 기준으로 해석 (CWD 와 무관)
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
        server=srv,
        gui_host=gui_host,
        gui_port=gui_port,
        db_root=db_root,
        heartbeat_timeout_s=heartbeat_timeout_s,
        modules=modules,
    )


def save_config(config: ServerConfig, path: Optional[Path] = None) -> Path:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_FILE
    data = config.to_dict()
    cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg_path
