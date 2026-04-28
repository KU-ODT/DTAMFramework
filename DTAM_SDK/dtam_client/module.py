"""DtamModule — 클라이언트 모듈의 1-stop facade.

각 모듈(AirMobility, MissionPlanner, OperationsConsole, Visualization) 이
DtamModule 을 **상속** 하고, 콜백은 ``@on_receive("3001")`` 데코레이터로
선언합니다. 등록·재연결·heartbeat·dataclass 직렬화는 SDK 가 모두 흡수.

표준 사용 예 (DTAMAirMobility)::

    from dtam_client import DtamModule, Role, on_receive
    from dtam_client.schema import (
        Msg3001_ScheduledFlight,
        Msg0003_CommonTimeInfo,
        Msg4001_VehicleStatus,
    )

    class VehicleService(DtamModule):
        role = Role.VEHICLE                    # ← 클래스 속성으로 한 번 선언

        def __init__(self, server_url="ws://127.0.0.1:8096/ws/dtam"):
            super().__init__(server_url=server_url)
            self._plans = {}

        @on_receive("3001")
        def handle_plan(self, plan: Msg3001_ScheduledFlight):
            self._plans[plan.aircraftId] = plan

        @on_receive("0003")
        def handle_time(self, msg: Msg0003_CommonTimeInfo):
            self._sim_time_s = parse_iso(msg.simTime)

        # 송신은 dataclass 인스턴스를 그대로 send().
        def push_status(self, vehicles: dict):
            return self.send(Msg4001_VehicleStatus(timestamp="...", vehicles=vehicles))


설계 결정:
  - 데코레이터는 ``@on_receive("MID")`` 1종 (mid 문자열만 받음, alias 거부).
  - send() 는 dataclass 인스턴스를 받아 mid 자동 추론.
  - 마이그레이션 호환: STRICT_DATACLASS=False (기본) 동안에는 dict 도 받지만
    DeprecationWarning 발생. 모든 모듈 마이그레이션 후 ``set_strict_dataclass(True)`` 로 전환.
"""
from __future__ import annotations

import dataclasses as _dc
import logging
import threading
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Type

from ._ws_client import DtamWsClient
from .catalog import CATALOG, MessageSpec, resolve as resolve_message
from .identity import KNOWN_MODULES, ModuleIdentity, Role, identity_of
from .schema import mid_for_dataclass, parse_payload, to_dict as _icd_to_dict

logger = logging.getLogger(__name__)


HEARTBEAT_PERIOD_S = 1.0
DECORATOR_TAG = "__dtam_on_receive_mid__"

# ── 마이그레이션 모드 ────────────────────────────────────────
# 권장: 이 토글은 **켜지 않아도 됩니다.** dataclass 송신이 표준이고, dict
# 송신은 ``send_legacy(...)`` / ``send(mid, dict)`` 시 DeprecationWarning 으로
# 알려집니다. ICD wire 와 dataclass 가 ``to_wire`` / ``from_wire`` 로 이미 정렬
# 되어 있어 양쪽 경로 모두 동일한 wire 모양을 만듭니다.
#
# ``set_strict_dataclass(True)`` 를 켜면 dict 호출이 모두 ``TypeError`` 가 됩니다.
# SDK 를 외부 사용자에게 배포하거나 dict 사용을 절대 금지하고 싶을 때만 사용.
_STRICT_DATACLASS = False


def set_strict_dataclass(strict: bool) -> None:
    """dict 송신 거부 모드 토글 (선택 사항).

    True 면 ``send(mid, dict)`` / ``send_legacy()`` 가 ``TypeError`` 발생.
    기본은 False (lenient + DeprecationWarning) — 권장 설정.
    """
    global _STRICT_DATACLASS
    _STRICT_DATACLASS = bool(strict)


def is_strict_dataclass() -> bool:
    return _STRICT_DATACLASS


# ── @on_receive("MID") 데코레이터 ─────────────────────────────

def on_receive(mid: str) -> Callable:
    """DtamModule subclass 의 메서드에 mid 를 부착.

    ``DtamModule.__init__`` 가 클래스를 스캔해 자동 등록합니다.

    사용::

        @on_receive("3001")
        def handle_plan(self, plan: Msg3001_ScheduledFlight):
            ...
    """
    spec = resolve_message(mid)  # 즉시 검증 — 잘못된 mid 면 import 시점 에러
    def deco(method: Callable) -> Callable:
        setattr(method, DECORATOR_TAG, spec.mid)
        return method
    return deco


# ── 통계 dataclass ───────────────────────────────────────────

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


def _iso_ts() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


# ── DtamModule ────────────────────────────────────────────────

class DtamModule:
    """클라이언트 service 베이스 클래스.

    서브클래스는:
      1. 클래스 속성 ``role`` 에 자기 역할 (Role enum 또는 문자열) 지정.
      2. ``@on_receive("MID")`` 가 붙은 메서드를 자유롭게 정의.
      3. ``__init__`` 에서 ``super().__init__(server_url=...)`` 호출.

    그러면 SDK 가:
      - DtamWsClient 를 시작하고 register
      - 데코레이트된 메서드들을 mid → 메서드 로 자동 등록
      - 0002 heartbeat 1Hz thread 시작
      - 통계 (tx/rx count) 추적
    """

    # 서브클래스가 오버라이드해야 함. 안 해도 되지만 그러면 KNOWN_MODULES 자동 채움 X.
    role: Role | str | None = None

    def __init__(
        self,
        *,
        server_url: str,
        role: Role | str | None = None,
        heartbeat: bool = True,
        reconnect_delay: float = 3.0,
    ) -> None:
        # composition API: __init__ 인자로 role 을 직접 받을 수도 있음.
        if role is not None and self.__class__.role is None:
            self.role = role
        identity = self._resolve_identity()
        self.identity = identity
        self.server_url = server_url
        self.stats = ModuleStats()
        self._lock = threading.RLock()
        self._heartbeat_enabled = bool(heartbeat)
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        # composition 패턴용 — runtime 등록한 콜백
        self._runtime_callbacks: Dict[str, Callable] = {}
        # reconfigure() 시 동일 값으로 재생성하기 위해 보존
        self._reconnect_delay = float(reconnect_delay)

        self._ws = DtamWsClient(
            url=server_url,
            role=identity.role.value,
            source=identity.source,
            reconnect_delay=reconnect_delay,
        )

        # @on_receive 자동 등록 (subclass 패턴)
        self._auto_register_handlers()

        # 연결 + heartbeat 즉시 시작 (백그라운드)
        self._ws.connect(block=False)
        if self._heartbeat_enabled:
            self._start_heartbeat()

    # ── composition API: 런타임 등록/시작 ─────────────────────
    @classmethod
    def start(
        cls,
        *,
        role: Role | str,
        server_url: str,
        heartbeat: bool = True,
        reconnect_delay: float = 3.0,
    ) -> "DtamModule":
        """클래스 상속 없이 한 번 호출로 모듈을 띄우는 편의 생성자.

        예) ``mod = DtamModule.start(role=Role.VEHICLE, server_url="ws://...")``
        """
        return cls(
            server_url=server_url,
            role=role,
            heartbeat=heartbeat,
            reconnect_delay=reconnect_delay,
        )

    def on(self, mid_or_alias: str, callback: Callable[[Any], None]) -> None:
        """런타임에 수신 콜백 등록 (composition 패턴).

        ``@on_receive`` 데코레이터의 런타임 대안. 같은 mid 에 두 번 호출하면
        뒤의 호출이 앞을 덮어씁니다.

        예) ``mod.on("scheduled_flight", self._on_scheduled_flight)``
        """
        spec = resolve_message(mid_or_alias)
        self._runtime_callbacks[spec.mid] = callback
        self._ws.on(spec.mid, self._make_dispatcher(spec.mid, callback))

    # ── 서브클래스 identity 결정 ──────────────────────────────
    def _resolve_identity(self) -> ModuleIdentity:
        role = self.role
        if role is None:
            raise TypeError(
                f"{type(self).__name__} must declare a class attribute `role` "
                "(e.g., `role = Role.VEHICLE`)."
            )
        return identity_of(role)

    # ── @on_receive 자동 등록 ─────────────────────────────────
    def _auto_register_handlers(self) -> None:
        """클래스 MRO 를 따라 @on_receive 데코레이터를 찾고, 각 mid 별로
        가장 derived 한 구현을 등록한다.

        규칙:
          1. 서브클래스가 데코레이터 없이 메서드를 override 해도 정상 동작 —
             base 의 데코레이터로 mid 가 결정되고, ``getattr(self, name)`` 이
             MRO 를 따라 가장 derived 한 bound method 를 반환한다.
          2. 가독성을 위해 서브클래스가 같은 메서드에 ``@on_receive`` 를 다시
             적어도 OK — 단, base 의 mid 와 **반드시 일치** 해야 한다. 일치
             하지 않으면 ``TypeError`` (실수로 잘못된 mid 가 silent 하게
             등록되는 footgun 방지).
          3. 한 mid 는 한 메서드만 처리 가능. 두 메서드가 같은 mid 를 들고
             있으면 ``TypeError``.

        역할별 base class (``MissionModule`` 등) 의 stub 들이 ``FORWARD_RULES``
        와 import 시점에 검증되므로, 서브클래스의 override 이름이 base 와
        다르면 라우팅되지 않음에 주의 (그건 의도된 동작 — role 변경에 해당).
        """
        # 1차 패스: MRO 를 subclass → base 순으로 돌면서 method-name → mid
        # 매핑을 모은다. 가장 derived 가 우선, base 의 stub 과 mid 가 다르면
        # 즉시 에러.
        method_to_mid: Dict[str, str] = {}
        for klass in type(self).__mro__:
            if klass is object:
                break
            for name, method in vars(klass).items():
                mid = getattr(method, DECORATOR_TAG, None)
                if not mid:
                    continue
                if name in method_to_mid:
                    if method_to_mid[name] != mid:
                        raise TypeError(
                            f"{type(self).__name__}.{name}: subclass declares "
                            f"@on_receive({method_to_mid[name]!r}) but base declares "
                            f"@on_receive({mid!r}). Mids must match — fix the "
                            f"subclass decorator or remove it (base's is enough)."
                        )
                    continue  # 같은 mid 의 redundant decorator — OK
                method_to_mid[name] = mid

        # 2차 패스: 등록. mid 중복 검사 + 가장 derived 한 bound method 사용.
        seen_mids: Dict[str, str] = {}
        for name, mid in method_to_mid.items():
            if mid in seen_mids:
                raise TypeError(
                    f"{type(self).__name__}: duplicate @on_receive({mid!r}) on "
                    f"both {seen_mids[mid]} and {name}. Each mid can have only one handler."
                )
            seen_mids[mid] = name
            bound_method = getattr(self, name)
            self._ws.on(mid, self._make_dispatcher(mid, bound_method))

    def _make_dispatcher(self, mid: str, method: Callable) -> Callable[[Dict[str, Any]], None]:
        """수신 dict → dataclass 인스턴스로 parse 후 사용자 메서드 호출."""
        def _dispatch(payload_dict: Dict[str, Any]) -> None:
            with self._lock:
                self.stats.rx_count += 1
                self.stats.rx_per_mid[mid] = self.stats.rx_per_mid.get(mid, 0) + 1
            try:
                parsed = parse_payload(mid, payload_dict)
                method(parsed)
            except Exception as exc:
                logger.exception(
                    "%s: handler for mid %s raised: %s",
                    type(self).__name__, mid, exc,
                )
                with self._lock:
                    self.stats.last_error = (
                        f"@on_receive({mid}) raised: {type(exc).__name__}: {exc}"
                    )
        return _dispatch

    # ── 송신 ──────────────────────────────────────────────────
    def send(self, message: Any, payload: Optional[Dict[str, Any]] = None) -> bool:
        """ICD 메시지 송신. 두 가지 호출 시그니처:

        1. ``send(Msg4001_VehicleStatus(...))`` — dataclass 인스턴스 (정식)
        2. ``send("4001", {...})`` 또는 ``send("vehicle_status", {...})``
           — mid/alias + dict (마이그레이션 호환, lenient 모드 한정)

        STRICT 모드에서는 (1) 만 허용.
        """
        # ── 1) dataclass 경로 ─────────────────────────────────
        if _dc.is_dataclass(message) and not isinstance(message, type):
            if payload is not None:
                raise TypeError(
                    "send(dataclass_instance) — second arg must be omitted."
                )
            mid = mid_for_dataclass(type(message))
            if mid is None:
                raise TypeError(
                    f"send(): dataclass {type(message).__name__} is not a registered "
                    f"ICD message. Use one of dtam_client.schema.MsgXXXX_*."
                )
            # _icd_to_dict 가 to_wire() 메서드 우선 사용 → 4001 처럼 wire 모양이
            # dataclass 와 다른 메시지도 ICD 호환 wire dict 생성.
            return self._dispatch_send(mid, _icd_to_dict(message))

        # ── 2) (mid, dict) 경로: 마이그레이션 호환 ──────────────
        if isinstance(message, str) and isinstance(payload, dict):
            if _STRICT_DATACLASS:
                raise TypeError(
                    "DtamModule.send(): strict mode 에서는 dataclass 만 허용. "
                    f"send({message!r}, dict) 호출됨."
                )
            warnings.warn(
                f"DtamModule.send({message!r}, dict) is deprecated; pass a "
                f"dataclass instance from dtam_client.schema instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            spec = resolve_message(message)
            return self._dispatch_send(spec.mid, payload)

        # ── 그 외: 형식 오류 ──────────────────────────────────
        raise TypeError(
            "DtamModule.send(): expected dataclass instance OR (mid, dict). "
            f"Got message={type(message).__name__}, payload={type(payload).__name__}."
        )

    def send_legacy(self, mid: str, payload: Dict[str, Any]) -> bool:
        """마이그레이션용 dict 송신. STRICT 모드에서는 거부."""
        if _STRICT_DATACLASS:
            raise TypeError(
                "send_legacy() is disabled in strict mode. Convert to dataclass."
            )
        warnings.warn(
            "send_legacy(mid, dict) is deprecated; use send(dataclass_instance).",
            DeprecationWarning,
            stacklevel=2,
        )
        spec = resolve_message(mid)
        return self._dispatch_send(spec.mid, payload)

    def _dispatch_send(self, mid: str, payload_dict: Dict[str, Any]) -> bool:
        ok = self._ws.send(mid, payload_dict)
        with self._lock:
            if ok:
                self.stats.tx_count += 1
                self.stats.tx_per_mid[mid] = self.stats.tx_per_mid.get(mid, 0) + 1
            else:
                self.stats.last_error = f"send({mid}) failed"
        return ok

    # ── 0002 heartbeat ─────────────────────────────────────────
    def _start_heartbeat(self) -> None:
        if self._heartbeat_thread is not None:
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"dtam-hb-{self.identity.role.value}",
            daemon=True,
        )
        self._heartbeat_thread.start()

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

    # ── 라이프사이클 ───────────────────────────────────────────
    def close(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        self._heartbeat_thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._ws.disconnect()

    def reconfigure(self, *, server_url: str) -> None:
        """WebSocket endpoint 재설정 — 기존 연결을 닫고 새 URL 로 다시 띄움.

        ``@on_receive`` 데코레이터 핸들러와 ``self.on(...)`` 으로 등록한 런타임
        콜백 모두 자동으로 새 연결에 다시 등록되며, heartbeat 도 자동 재기동된다.
        """
        if server_url == self.server_url:
            return
        # 기존 WS + heartbeat 정리
        self.close()
        # 새 _ws 생성 (역할/소스/재연결 간격 그대로)
        self.server_url = server_url
        self._ws = DtamWsClient(
            url=server_url,
            role=self.identity.role.value,
            source=self.identity.source,
            reconnect_delay=self._reconnect_delay,
        )
        # 데코레이터 + 런타임 콜백 다시 등록
        self._auto_register_handlers()
        for mid, callback in self._runtime_callbacks.items():
            self._ws.on(mid, self._make_dispatcher(mid, callback))
        # 다시 연결 + heartbeat
        self._heartbeat_stop = threading.Event()
        self._ws.connect(block=False)
        if self._heartbeat_enabled:
            self._start_heartbeat()

    # ── 진단 ──────────────────────────────────────────────────
    @property
    def connected(self) -> bool:
        return bool(self._ws.connected)

    @property
    def registered(self) -> bool:
        return bool(self._ws.registered)

    @property
    def subscriptions(self) -> List[str]:
        return list(self._ws.subscriptions)

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
            f"{type(self).__name__}(role={self.identity.role.value!r}, "
            f"connected={self.connected}, registered={self.registered})"
        )


__all__ = [
    "DtamModule",
    "ModuleStats",
    "on_receive",
    "set_strict_dataclass",
    "is_strict_dataclass",
    "HEARTBEAT_PERIOD_S",
]
