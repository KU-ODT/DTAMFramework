"""DTAM AirMobility 통신 layer (WebSocket /ws/dtam).

``VehicleModule`` (SDK 베이스) 를 상속해 5개 mid 핸들러만 override.
``IntegratedAirMobilityService`` 가 ``self.comm`` 으로 보유 (composition) —
도메인 로직(시계, 세션, 10Hz tick)은 service 가, 통신은 이 클래스가 담당.

수신 핸들러는 ``__init__`` 에서 받은 콜백 함수로 위임 — 콜백은 service
인스턴스의 메서드를 그대로 받으면 됨.

처리하지 않는 mid (1002 SimulationSetup) 는 ``VehicleModule`` 베이스의
빈 stub 이 그대로 유지되어 silent drop 으로 동작.

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

from dtam_client import VehicleModule  # type: ignore


class VehicleComm(VehicleModule):
    """Air Mobility 모듈의 DTAM 통신 layer.

    ``VehicleModule`` 베이스가 ``role = Role.VEHICLE`` + 6개 mid 의 빈
    ``@on_receive`` stub 을 제공. 이 클래스는 그 위에 5개를 콜백 위임으로
    override (1002 는 베이스 stub 유지).
    """

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
        # super().__init__ 보다 먼저 — dispatcher 안에서 self._cb_* 참조하므로 미리 세팅.
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

    # ── 5개 핸들러 override (콜백 위임) ─────────────────────────
    def on_scheduled_flight(self, msg: Any) -> None:
        cb = self._cb_scheduled
        if cb is not None:
            cb(msg)

    def on_common_time_info(self, msg: Any) -> None:
        cb = self._cb_clock
        if cb is not None:
            cb(msg)

    def on_dtam_execute(self, msg: Any) -> None:
        cb = self._cb_execute
        if cb is not None:
            cb(msg)

    def on_strategic_separation(self, msg: Any) -> None:
        cb = self._cb_strategic
        if cb is not None:
            cb(msg)

    def on_tactical_separation(self, msg: Any) -> None:
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
