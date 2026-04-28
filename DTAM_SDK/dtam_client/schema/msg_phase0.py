"""Phase 0 메시지 — 0001 Module Setting Info, 0002 Module Status."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Msg0001_ModuleSettingInfo:
    """MSG 0001: 모듈 세팅 정보 — 모듈이 서버에 자기 식별 정보를 보고.

    WebSocket(``/ws/dtam``) 단일 채널 체제에서는 모듈이 서버에 *접속* 하므로
    네트워크 endpoint 보고가 불필요하다. ``ModuleName`` 은 ``register`` 핸드셰이크
    의 ``source`` 와 동일한 역할로 쓰인다.
    """
    Timestamp: str = ""
    ModuleName: str = ""
    Role: str = ""               # "vehicle" / "mission" / "monitoring" / "visual"


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
