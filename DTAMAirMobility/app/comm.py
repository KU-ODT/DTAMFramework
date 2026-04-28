"""DTAM AirMobility 통신 layer (WebSocket /ws/dtam).

``DtamModule`` 서브클래스 + ``@on_receive("MID")`` 데코레이터 패턴.
``IntegratedAirMobilityService`` 가 ``self.comm`` 으로 보유 (composition) —
도메인 로직(시계, 세션, 10Hz tick)은 service 가, 통신은 이 클래스가 담당.

수신 핸들러는 모두 캡슐화돼 있고, 실제 처리는 ``__init__`` 에서 받은 콜백
함수로 위임. 콜백은 service 인스턴스의 메서드를 그대로 받으면 됨.

외부 인터페이스:
  - VehicleComm(target_ip, ws_port, on_scheduled_flight, on_common_time_info,
                on_dtam_execute, on_strategic_separation, on_tactical_separation)
  - .send(message)                                    # dataclass 또는 (alias, dict)
  - .reconfigure_endpoint(target_ip=..., ws_port=...) # WS 재접속
  - .close()
  - .connected, .registered, .server_url, .stats     # DtamModule 에서 상속
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Optional

_SDK_ROOT = Path(__file__).resolve().parents[2] / "DTAM_SDK"
if _SDK_ROOT.is_dir() and str(_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_SDK_ROOT))

from dtam_client import DtamModule, Role, on_receive  # type: ignore


class VehicleComm(DtamModule):
    """Air Mobility 모듈의 DTAM 통신 layer.

    - role = Role.VEHICLE
    - 수신: ``@on_receive`` 로 5개 mid 자동 등록 (3001/0003/2002/3002/3003)
    - 송신: ``self.send(...)`` (DtamModule 상속)
    - heartbeat 0002 1Hz: DtamModule 가 자동 송신
    """

    role = Role.VEHICLE

    def __init__(
        self,
        *,
        target_ip: str = "127.0.0.1",
        ws_port: int = 8096,
        on_scheduled_flight: Optional[Callable[[Any], None]] = None,
        on_common_time_info: Optional[Callable[[Any], None]] = None,
        on_dtam_execute: Optional[Callable[[Any], None]] = None,
        on_strategic_separation: Optional[Callable[[Any], None]] = None,
        on_tactical_separation: Optional[Callable[[Any], None]] = None,
    ) -> None:
        # super().__init__ 보다 먼저 — _auto_register_handlers 가 콜백을 호출하지는
        # 않지만 dispatcher 안에서 self.* 참조하므로 미리 세팅.
        self._target_ip = str(target_ip)
        self._ws_port = int(ws_port)
        self._cb_scheduled = on_scheduled_flight
        self._cb_clock = on_common_time_info
        self._cb_execute = on_dtam_execute
        self._cb_strategic = on_strategic_separation
        self._cb_tactical = on_tactical_separation

        super().__init__(
            server_url=f"ws://{target_ip}:{ws_port}/ws/dtam",
            heartbeat=True,
        )

    # ── @on_receive 자동 등록되는 핸들러들 (실제 처리는 콜백 위임) ─
    @on_receive("3001")
    def _on_3001(self, msg: Any) -> None:
        cb = self._cb_scheduled
        if cb is not None:
            cb(msg)

    @on_receive("0003")
    def _on_0003(self, msg: Any) -> None:
        cb = self._cb_clock
        if cb is not None:
            cb(msg)

    @on_receive("2002")
    def _on_2002(self, msg: Any) -> None:
        cb = self._cb_execute
        if cb is not None:
            cb(msg)

    @on_receive("3002")
    def _on_3002(self, msg: Any) -> None:
        cb = self._cb_strategic
        if cb is not None:
            cb(msg)

    @on_receive("3003")
    def _on_3003(self, msg: Any) -> None:
        cb = self._cb_tactical
        if cb is not None:
            cb(msg)

    # ── 설정 ──────────────────────────────────────────────────
    def reconfigure_endpoint(
        self,
        *,
        target_ip: Optional[str] = None,
        ws_port: Optional[int] = None,
    ) -> None:
        """target_ip/ws_port 변경 시 WS 끊고 새 URL 로 재접속."""
        changed = False
        if target_ip is not None and str(target_ip) != self._target_ip:
            self._target_ip = str(target_ip)
            changed = True
        if ws_port is not None and int(ws_port) != self._ws_port:
            self._ws_port = int(ws_port)
            changed = True
        if changed:
            new_url = f"ws://{self._target_ip}:{self._ws_port}/ws/dtam"
            super().reconfigure(server_url=new_url)

    @property
    def target_ip(self) -> str:
        return self._target_ip

    @property
    def ws_port(self) -> int:
        return self._ws_port


__all__ = ["VehicleComm"]
