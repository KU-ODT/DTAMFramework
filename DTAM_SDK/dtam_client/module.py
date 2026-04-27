"""DtamModule — 클라이언트 모듈이 SimulationState 서버에 참여하기 위한 1-stop facade.

각 클라이언트 모듈(AirMobility, MissionPlanner, OperationsConsole, Visualization)
이 반복적으로 작성하던 다음 보일러플레이트를 SDK 한 곳에 가둡니다:

  - WebSocket 연결/재연결 (DtamWsClient 위임)
  - identity 자동 채움 (KNOWN_MODULES[role].source)
  - 0002 Module Status heartbeat 1Hz 송신 thread
  - alias → mid 자동 변환 (catalog.resolve)
  - 송수신 통계 (tx_count, rx_count, last_error)

사용 예 (DTAMAirMobility)::

    from dtam_client import DtamModule, Role

    mod = DtamModule.start(
        role=Role.VEHICLE,
        server_url="ws://127.0.0.1:8096/ws/dtam",
        heartbeat=True,
    )
    mod.on("scheduled_flight",     on_3001)
    mod.on("common_time_info",     on_0003)
    mod.on("dtam_execute",         on_2002)
    mod.on("strategic_separation", on_3002)
    mod.on("tactical_separation",  on_3003)

    mod.send("vehicle_status", payload)        # 4001 (alias)
    mod.send("4001", payload)                  # 동일

    mod.close()
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from ._ws_client import DtamWsClient
from .catalog import CATALOG, MessageSpec, resolve, try_resolve
from .identity import KNOWN_MODULES, ModuleIdentity, Role, identity_of

logger = logging.getLogger(__name__)


HEARTBEAT_PERIOD_S = 1.0


def _iso_ts() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass
class ModuleStats:
    tx_count: int = 0
    rx_count: int = 0
    rx_per_mid: Dict[str, int] = field(default_factory=dict)
    tx_per_mid: Dict[str, int] = field(default_factory=dict)
    last_error: str = ""
    last_heartbeat_ok: bool = False
    last_heartbeat_ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_count": self.tx_count,
            "rx_count": self.rx_count,
            "rx_per_mid": dict(self.rx_per_mid),
            "tx_per_mid": dict(self.tx_per_mid),
            "last_error": self.last_error,
            "last_heartbeat_ok": self.last_heartbeat_ok,
            "last_heartbeat_ts": self.last_heartbeat_ts,
        }


class DtamModule:
    """DtamWsClient 위에 얹는 클라이언트-측 facade.

    - 콜백은 mid 또는 alias 로 등록 가능 (``on("4001", ...)`` ≡ ``on("vehicle_status", ...)``).
    - ``send`` / ``send_async`` 도 alias 허용. async 는 thread-pool 없이 fire-and-forget.
    - heartbeat=True 면 1Hz 로 0002 자동 송신 (source = identity.source).
    """

    def __init__(
        self,
        *,
        identity: ModuleIdentity,
        server_url: str,
        heartbeat: bool = True,
        reconnect_delay: float = 3.0,
    ) -> None:
        self.identity = identity
        self.server_url = server_url
        self._heartbeat_enabled = bool(heartbeat)
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._callbacks: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._lock = threading.RLock()
        self.stats = ModuleStats()

        self._ws = DtamWsClient(
            url=server_url,
            role=identity.role.value,
            source=identity.source,
            reconnect_delay=reconnect_delay,
        )

    # ── 라이프사이클 ────────────────────────────────────────────
    @classmethod
    def start(
        cls,
        *,
        role: Role | str,
        server_url: str,
        heartbeat: bool = True,
        reconnect_delay: float = 3.0,
    ) -> "DtamModule":
        """모듈을 만들고 즉시 connect + (옵션) heartbeat 까지 시작."""
        identity = identity_of(role)
        mod = cls(
            identity=identity,
            server_url=server_url,
            heartbeat=heartbeat,
            reconnect_delay=reconnect_delay,
        )
        mod.connect()
        return mod

    def connect(self) -> None:
        """서버에 연결 + 등록을 백그라운드로 시작."""
        self._ws.connect(block=False)
        if self._heartbeat_enabled and self._heartbeat_thread is None:
            self._heartbeat_stop.clear()
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name=f"dtam-hb-{self.identity.role.value}",
                daemon=True,
            )
            self._heartbeat_thread.start()

    def close(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        self._heartbeat_thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._ws.disconnect()

    @property
    def connected(self) -> bool:
        return bool(self._ws.connected)

    @property
    def registered(self) -> bool:
        return bool(self._ws.registered)

    @property
    def subscriptions(self) -> list[str]:
        return list(self._ws.subscriptions)

    # ── 송신 ──────────────────────────────────────────────────
    def send(
        self,
        message: str | int,
        payload: Dict[str, Any],
        *,
        image_bytes: bytes = b"",
    ) -> bool:
        """alias 또는 mid 로 메시지 송신. 성공 여부 반환."""
        spec = resolve(message)
        ok = self._ws.send(spec.mid, payload, image_bytes=image_bytes)
        with self._lock:
            if ok:
                self.stats.tx_count += 1
                self.stats.tx_per_mid[spec.mid] = self.stats.tx_per_mid.get(spec.mid, 0) + 1
            else:
                self.stats.last_error = f"send({spec.mid}) failed"
        return ok

    # send_async는 WS의 send가 이미 non-blocking에 가깝지만, 의미적으로 fire-and-forget을 의도.
    send_async = send

    # ── 수신 콜백 ────────────────────────────────────────────────
    def on(self, message: str | int, callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """콜백 등록. 데코레이터로도 사용 가능.

        ``mod.on("4001", cb)`` 또는 ``@mod.on("vehicle_status")`` 둘 다 가능.
        """
        spec = resolve(message)

        def register(cb: Callable[[Dict[str, Any]], None]) -> Callable:
            self._callbacks[spec.mid] = cb
            self._ws.on(spec.mid, lambda payload, _cb=cb, _mid=spec.mid: self._dispatch(_mid, payload, _cb))
            return cb

        if callback is None:
            return register
        return register(callback)

    def off(self, message: str | int) -> None:
        spec = resolve(message)
        self._callbacks.pop(spec.mid, None)
        self._ws.on(spec.mid, lambda _payload: None)

    def _dispatch(self, mid: str, payload: Any, cb: Callable) -> None:
        with self._lock:
            self.stats.rx_count += 1
            self.stats.rx_per_mid[mid] = self.stats.rx_per_mid.get(mid, 0) + 1
        try:
            cb(payload)
        except Exception as exc:
            logger.exception("DtamModule callback for %s failed: %s", mid, exc)
            with self._lock:
                self.stats.last_error = f"on({mid}) raised: {type(exc).__name__}: {exc}"

    # ── 0002 heartbeat ─────────────────────────────────────────
    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.is_set():
            ok = False
            try:
                if self._ws.connected and self._ws.registered:
                    ok = self._ws.send("0002", {
                        "timestamp": _iso_ts(),
                        "source": self.identity.source,
                        "status": 1,
                    })
            except Exception as exc:
                logger.debug("heartbeat send failed: %s", exc)
            with self._lock:
                self.stats.last_heartbeat_ok = bool(ok)
                self.stats.last_heartbeat_ts = time.time()
                if ok:
                    self.stats.tx_count += 1
                    self.stats.tx_per_mid["0002"] = self.stats.tx_per_mid.get("0002", 0) + 1
            if self._heartbeat_stop.wait(HEARTBEAT_PERIOD_S):
                break

    # ── 진단/상태 ──────────────────────────────────────────────
    def status(self) -> Dict[str, Any]:
        return {
            "role": self.identity.role.value,
            "source": self.identity.source,
            "display_name": self.identity.display_name,
            "server_url": self.server_url,
            "connected": self.connected,
            "registered": self.registered,
            "subscriptions": self.subscriptions,
            "stats": self.stats.to_dict(),
        }

    def __repr__(self) -> str:
        return (
            f"DtamModule(role={self.identity.role.value!r}, "
            f"connected={self.connected}, registered={self.registered})"
        )


__all__ = ["DtamModule", "ModuleStats", "HEARTBEAT_PERIOD_S"]
