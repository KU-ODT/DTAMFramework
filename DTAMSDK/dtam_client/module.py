"""High-level DtamModule facade for module authors.
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

# Registration handling
# Registration handling
# Registration handling
# Registration handling
# Registration handling
#
# Registration handling
# Registration handling
_STRICT_DATACLASS = False


def set_strict_dataclass(strict: bool) -> None:
    """Internal DTAM helper."""
    global _STRICT_DATACLASS
    _STRICT_DATACLASS = bool(strict)


def is_strict_dataclass() -> bool:
    return _STRICT_DATACLASS


# Registration handling

def on_receive(mid: str) -> Callable:
    """Internal DTAM helper."""
    spec = resolve_message(mid)  # Validate immediately; bad mids fail at import time.
    def deco(method: Callable) -> Callable:
        setattr(method, DECORATOR_TAG, spec.mid)
        return method
    return deco


# Registration handling

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


# Registration handling

class DtamModule:
    """Internal DTAM helper."""

    # Registration handling
    role: Role | str | None = None

    def __init__(
        self,
        *,
        server_url: str,
        role: Role | str | None = None,
        heartbeat: bool = True,
        reconnect_delay: float = 3.0,
    ) -> None:
        # Registration handling
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
        # Registration handling
        self._runtime_callbacks: Dict[str, Callable] = {}
        # Registration handling
        self._reconnect_delay = float(reconnect_delay)

        self._ws = DtamWsClient(
            url=server_url,
            role=identity.role.value,
            source=identity.source,
            reconnect_delay=reconnect_delay,
        )

        # Registration handling
        self._auto_register_handlers()

        # Heartbeat handling
        self._ws.connect(block=False)
        if self._heartbeat_enabled:
            self._start_heartbeat()

    # Registration handling
    @classmethod
    def start(
        cls,
        *,
        role: Role | str,
        server_url: str,
        heartbeat: bool = True,
        reconnect_delay: float = 3.0,
    ) -> "DtamModule":
        """Internal DTAM helper."""
        return cls(
            server_url=server_url,
            role=role,
            heartbeat=heartbeat,
            reconnect_delay=reconnect_delay,
        )

    def on(self, mid_or_alias: str, callback: Callable[[Any], None]) -> None:
        """Internal DTAM helper."""
        spec = resolve_message(mid_or_alias)
        self._runtime_callbacks[spec.mid] = callback
        self._ws.on(spec.mid, self._make_dispatcher(spec.mid, callback))

    # Registration handling
    def _resolve_identity(self) -> ModuleIdentity:
        role = self.role
        if role is None:
            raise TypeError(
                f"{type(self).__name__} must declare a class attribute `role` "
                "(e.g., `role = Role.VEHICLE`)."
            )
        return identity_of(role)

    # Registration handling
    def _auto_register_handlers(self) -> None:
        """Internal DTAM helper."""
        mid_to_name: Dict[str, str] = {}    # mid to most-derived method name
        name_to_mid: Dict[str, str] = {}    # method name to mid for mismatch checks

        for klass in type(self).__mro__:
            if klass is object:
                break
            per_class: Dict[str, str] = {}   # mid to method name within this class
            for name, method in vars(klass).items():
                mid = getattr(method, DECORATOR_TAG, None)
                if not mid:
                    continue
                # Registration handling
                if mid in per_class:
                    raise TypeError(
                        f"{klass.__name__}: duplicate @on_receive({mid!r}) on "
                        f"both {per_class[mid]} and {name}. Each mid can have only one handler."
                    )
                per_class[mid] = name
                # Registration handling
                if name in name_to_mid and name_to_mid[name] != mid:
                    raise TypeError(
                        f"{type(self).__name__}.{name}: subclass declares "
                        f"@on_receive({name_to_mid[name]!r}) but base declares "
                        f"@on_receive({mid!r}). Mids must match; fix the "
                        f"subclass decorator or remove it (base's is enough)."
                    )
                name_to_mid.setdefault(name, mid)
                # Registration handling
                mid_to_name.setdefault(mid, name)

        for mid, name in mid_to_name.items():
            bound_method = getattr(self, name)
            self._ws.on(mid, self._make_dispatcher(mid, bound_method))

    def _make_dispatcher(self, mid: str, method: Callable) -> Callable[[Dict[str, Any]], None]:
        """Internal helper."""
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

    # Registration handling
    def send(self, message: Any, payload: Optional[Dict[str, Any]] = None) -> bool:
        """Internal DTAM helper."""
        # Registration handling
        if _dc.is_dataclass(message) and not isinstance(message, type):
            if payload is not None:
                raise TypeError(
                    "send(dataclass_instance): second arg must be omitted."
                )
            mid = mid_for_dataclass(type(message))
            if mid is None:
                raise TypeError(
                    f"send(): dataclass {type(message).__name__} is not a registered "
                    f"ICD message. Use one of dtam_client.schema.MsgXXXX_*."
                )
            # Registration handling
            return self._dispatch_send(mid, _icd_to_dict(message))

        # Registration handling
        if isinstance(message, str) and isinstance(payload, dict):
            if _STRICT_DATACLASS:
                raise TypeError(
                "DtamModule.send(): strict mode allows dataclass instances only. "
                f"send({message!r}, dict) call"
                )
            warnings.warn(
                f"send({message!r}, dict) call"
                f"dataclass instance from dtam_client.schema instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            spec = resolve_message(message)
            return self._dispatch_send(spec.mid, payload)

        # Registration handling
        raise TypeError(
            "DtamModule.send(): expected dataclass instance OR (mid, dict). "
            f"Got message={type(message).__name__}, payload={type(payload).__name__}."
        )

    def send_legacy(self, mid: str, payload: Dict[str, Any]) -> bool:
        """Internal helper."""
        if _STRICT_DATACLASS:
            raise TypeError(
                "DtamModule.send(): strict mode allows dataclass instances only. "
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

    # Heartbeat handling
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

    # Registration handling
    def close(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        self._heartbeat_thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._ws.disconnect()

    def reconfigure(self, *, server_url: str) -> None:
        """Internal DTAM helper."""
        if server_url == self.server_url:
            return
        # Heartbeat handling
        self.close()
        # Registration handling
        self.server_url = server_url
        self._ws = DtamWsClient(
            url=server_url,
            role=self.identity.role.value,
            source=self.identity.source,
            reconnect_delay=self._reconnect_delay,
        )
        # Registration handling
        self._auto_register_handlers()
        for mid, callback in self._runtime_callbacks.items():
            self._ws.on(mid, self._make_dispatcher(mid, callback))
        # Heartbeat handling
        self._heartbeat_stop = threading.Event()
        self._ws.connect(block=False)
        if self._heartbeat_enabled:
            self._start_heartbeat()

    # Registration handling
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
