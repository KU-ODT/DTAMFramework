"""DTAM Visualization Manager 설정.

- AirSim RPC endpoint (기본 127.0.0.1:41451)
- DTAM WebSocket endpoint (SimulationState ``/ws/dtam``)
- GUI http 포트
- 주기성 작업 Hz (0002 heartbeat / 4101 camera)

``config.json`` 이 존재하면 그것을 우선 사용한다.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]                # DTAMVisualization/
FRAMEWORK_ROOT = ROOT_DIR.parent                              # DTAMFramework/
DTAM_SDK_ROOT = FRAMEWORK_ROOT / "DTAM_SDK"
AIRSIM_PY_ROOT = ROOT_DIR / "PythonClient"
WEB_DIR = ROOT_DIR / "vm_app" / "web"

DEFAULT_CONFIG_FILE = ROOT_DIR / "vm_config.json"

# 이 모듈이 상시 처리해야 하는 ICD 메시지.
INBOUND_MIDS: List[str] = ["1001", "1002", "1003", "2002", "3001", "0003", "4001", "5002"]
OUTBOUND_MIDS: List[str] = ["0002", "4101"]

MODULE_SOURCE_NAME = "DTAMVisualization"


@dataclass
class AirSimConfig:
    host: str = "127.0.0.1"
    port: int = 41451
    vehicle_prefix: str = ""      # 외부 UAM0001 ↔ AirSim "Drone1" 매핑 시 접두어 (빈 문자열이면 그대로 사용)
    ignore_collisions: bool = True
    # UAM → AirSim 차량 이름 직접 매핑 (prefix 보다 우선). 예: {"UAM0001": "Drone1"}
    vehicle_map: Dict[str, str] = field(default_factory=dict)


@dataclass
class DtamEndpoint:
    server_ip: str = "127.0.0.1"
    server_port: int = 8096      # SimulationState HTTP/WebSocket port


@dataclass
class StreamingConfig:
    module_status_hz: float = 1.0
    camera_enabled: bool = False
    camera_name: str = "front_center"
    camera_image_type: int = 0       # Scene
    camera_hz: float = 5.0
    camera_quality: int = 80
    camera_vehicle: str = ""         # 빈 문자열이면 AirSim 기본 차량 사용


@dataclass
class UnrealRuntimeConfig:
    executable: str = ""
    args: List[str] = field(default_factory=lambda: ["-windowed"])
    working_dir: str = ""


@dataclass
class VMConfig:
    gui_host: str = "127.0.0.1"
    gui_port: int = 8097
    log_level: str = "info"
    airsim: AirSimConfig = field(default_factory=AirSimConfig)
    dtam: DtamEndpoint = field(default_factory=DtamEndpoint)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    unreal: UnrealRuntimeConfig = field(default_factory=UnrealRuntimeConfig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gui_host": self.gui_host,
            "gui_port": self.gui_port,
            "log_level": self.log_level,
            "airsim": asdict(self.airsim),
            "dtam": asdict(self.dtam),
            "streaming": asdict(self.streaming),
            "unreal": asdict(self.unreal),
        }


def load_config(path: Optional[Path] = None) -> VMConfig:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_FILE
    raw: Dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[DTAM VM] failed to read {cfg_path}: {exc}")

    gui_host = str(raw.get("gui_host", "127.0.0.1"))
    gui_port = int(raw.get("gui_port", 8097))
    log_level = str(raw.get("log_level", "info"))

    airsim_raw = dict(raw.get("airsim") or {})
    airsim = AirSimConfig(
        host=str(airsim_raw.get("host", "127.0.0.1")),
        port=int(airsim_raw.get("port", 41451)),
        vehicle_prefix=str(airsim_raw.get("vehicle_prefix", "")),
        ignore_collisions=bool(airsim_raw.get("ignore_collisions", True)),
        vehicle_map={str(k): str(v) for k, v in dict(airsim_raw.get("vehicle_map") or {}).items()},
    )

    dtam_raw = dict(raw.get("dtam") or {})
    dtam = DtamEndpoint(
        server_ip=str(dtam_raw.get("server_ip", "127.0.0.1")),
        server_port=int(dtam_raw.get("server_port", 8096)),
    )

    stream_raw = dict(raw.get("streaming") or {})
    streaming = StreamingConfig(
        module_status_hz=float(stream_raw.get("module_status_hz", 1.0)),
        camera_enabled=bool(stream_raw.get("camera_enabled", False)),
        camera_name=str(stream_raw.get("camera_name", "front_center")),
        camera_image_type=int(stream_raw.get("camera_image_type", 0)),
        camera_hz=float(stream_raw.get("camera_hz", 5.0)),
        camera_quality=int(stream_raw.get("camera_quality", 80)),
        camera_vehicle=str(stream_raw.get("camera_vehicle", "")),
    )

    unreal_raw = dict(raw.get("unreal") or {})
    unreal_args_raw = unreal_raw.get("args", ["-windowed"])
    if isinstance(unreal_args_raw, str):
        unreal_args = [unreal_args_raw]
    else:
        unreal_args = [str(item) for item in list(unreal_args_raw or [])]
    unreal = UnrealRuntimeConfig(
        executable=str(unreal_raw.get("executable", "")),
        args=unreal_args,
        working_dir=str(unreal_raw.get("working_dir", "")),
    )

    return VMConfig(
        gui_host=gui_host,
        gui_port=gui_port,
        log_level=log_level,
        airsim=airsim,
        dtam=dtam,
        streaming=streaming,
        unreal=unreal,
    )


def save_config(cfg: VMConfig, path: Optional[Path] = None) -> Path:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_FILE
    cfg_path.write_text(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg_path
