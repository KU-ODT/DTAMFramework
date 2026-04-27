"""Phase 0 메시지 — 0001 Module Setting Info, 0002 Module Status."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Msg0001_ModuleSettingInfo:
    """MSG 0001: 모듈 세팅 정보 — 모듈이 서버에 수신 포트를 보고."""
    Timestamp: str = ""
    ModuleName: str = ""
    IP: str = "127.0.0.1"
    UDPPort: int = 0
    TCPPort: int = 0


@dataclass
class Msg0002_ModuleStatus:
    """MSG 0002: 모듈 상태 — 1Hz 주기 heartbeat."""
    timestamp: str = ""
    source: str = ""
    status: int = 1


@dataclass
class Msg0003_CommonTimeInfo:
    """MSG 0003: 공통 시간 정보 — 서버→모듈 1Hz."""
    timestamp: str = ""
    simTime: str = ""
