"""모듈 연결 상태 레지스트리.

- 4 종 역할 (mission / monitoring / vehicle / visual) 을 설정 기반으로 초기화.
- 0002 Module Status 가 도착하면 해당 역할의 heartbeat/status 갱신.
- heartbeat 가 일정 시간 안 오면 `connected = False`.
- per-mid rx/tx 카운터 + 최근 payload 보관.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Optional

from ..model.message import MESSAGE_TABLE
from ..model.config import ModuleEndpoint


_MAX_RECENT = 200


@dataclass
class MessageCounter:
    mid: str
    name: str = ""
    rx_count: int = 0
    tx_count: int = 0
    last_rx_ts: float = 0.0
    last_tx_ts: float = 0.0
    last_rx_payload: Optional[Dict[str, Any]] = None
    last_tx_payload: Optional[Dict[str, Any]] = None
    hz: float = 0.0
    _rx_timestamps: Deque[float] = field(default_factory=lambda: deque(maxlen=64))

    def note_rx(self, payload: Any) -> None:
        now = time.time()
        self.rx_count += 1
        self.last_rx_ts = now
        self._rx_timestamps.append(now)
        if isinstance(payload, dict):
            self.last_rx_payload = payload
        window = [t for t in self._rx_timestamps if now - t < 5.0]
        if len(window) >= 2:
            span = max(1e-3, window[-1] - window[0])
            self.hz = round((len(window) - 1) / span, 3)
        else:
            self.hz = 0.0

    def note_tx(self, payload: Any) -> None:
        self.tx_count += 1
        self.last_tx_ts = time.time()
        if isinstance(payload, dict):
            self.last_tx_payload = payload

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mid": self.mid,
            "name": self.name,
            "rx_count": self.rx_count,
            "tx_count": self.tx_count,
            "last_rx_ts": self.last_rx_ts,
            "last_tx_ts": self.last_tx_ts,
            "last_rx_payload": self.last_rx_payload,
            "last_tx_payload": self.last_tx_payload,
            "hz": self.hz,
        }


@dataclass
class ModuleState:
    role: str
    display_name: str
    expected_source: str = ""
    last_heartbeat_ts: float = 0.0
    last_source: str = ""
    last_status: Optional[Dict[str, Any]] = None
    rx_count: int = 0
    tx_count: int = 0
    messages: Dict[str, MessageCounter] = field(default_factory=dict)

    def connected(self, heartbeat_timeout_s: float) -> bool:
        return bool(self.last_heartbeat_ts) and (
            time.time() - self.last_heartbeat_ts <= float(heartbeat_timeout_s)
        )

    def describe(self, heartbeat_timeout_s: float) -> Dict[str, Any]:
        return {
            "role": self.role,
            "display_name": self.display_name,
            "expected_source": self.expected_source,
            "last_heartbeat_ts": self.last_heartbeat_ts,
            "last_source": self.last_source,
            "last_status": self.last_status,
            "rx_count": self.rx_count,
            "tx_count": self.tx_count,
            "connected": self.connected(heartbeat_timeout_s),
            "messages": {mid: mc.to_dict() for mid, mc in sorted(self.messages.items())},
        }


class ModuleRegistry:
    """설정 기반 모듈 4종을 추적. Thread-safe."""

    def __init__(self, modules: Iterable[ModuleEndpoint], heartbeat_timeout_s: float = 3.5) -> None:
        self._lock = threading.RLock()
        self.heartbeat_timeout_s = float(heartbeat_timeout_s)
        self._by_role: Dict[str, ModuleState] = {}
        self._source_to_role: Dict[str, str] = {}
        self._global_counters: Dict[str, MessageCounter] = {}
        for mid, meta in MESSAGE_TABLE.items():
            self._global_counters[mid] = MessageCounter(mid=mid, name=str(meta.get("name") or ""))
        for ep in modules:
            self._by_role[ep.role] = ModuleState(
                role=ep.role,
                display_name=ep.display_name,
                expected_source=ep.expected_source,
            )
            if ep.expected_source:
                self._source_to_role[ep.expected_source] = ep.role

    # ── 업데이트 ──────────────────────────────────────────────
    def note_rx(self, role: Optional[str], mid: str, payload: Any) -> None:
        with self._lock:
            counter = self._global_counters.get(mid)
            if counter is None:
                counter = MessageCounter(mid=mid)
                self._global_counters[mid] = counter
            counter.note_rx(payload)

            if role and role in self._by_role:
                module = self._by_role[role]
                module.rx_count += 1
                mc = module.messages.setdefault(mid, MessageCounter(
                    mid=mid, name=(MESSAGE_TABLE.get(mid, {}).get("name") or ""),
                ))
                mc.note_rx(payload)

    def note_tx(self, role: Optional[str], mid: str, payload: Any) -> None:
        with self._lock:
            counter = self._global_counters.get(mid)
            if counter is None:
                counter = MessageCounter(mid=mid)
                self._global_counters[mid] = counter
            counter.note_tx(payload)

            if role and role in self._by_role:
                module = self._by_role[role]
                module.tx_count += 1
                mc = module.messages.setdefault(mid, MessageCounter(
                    mid=mid, name=(MESSAGE_TABLE.get(mid, {}).get("name") or ""),
                ))
                mc.note_tx(payload)

    def heartbeat(self, payload: Dict[str, Any]) -> Optional[str]:
        """0002 Module Status 수신. source 필드를 기준으로 역할을 찾는다.

        Returns:
            업데이트된 역할 id — 못 찾으면 ``None``.
        """
        source = str((payload or {}).get("source") or "").strip()
        if not source:
            return None
        with self._lock:
            role = self._source_to_role.get(source)
            if role is None:
                # fallback: source 가 role 자체 (예: "vehicle") 인 경우
                role = source.lower() if source.lower() in self._by_role else None
                if role is None:
                    # expected_source 가 빈 모듈이 있으면 거기로 임시 연결
                    for candidate in self._by_role.values():
                        if not candidate.expected_source:
                            role = candidate.role
                            candidate.expected_source = source
                            self._source_to_role[source] = role
                            break
            if role is None:
                return None
            module = self._by_role[role]
            module.last_heartbeat_ts = time.time()
            module.last_source = source
            module.last_status = dict(payload)
            return role

    # ── 조회 ─────────────────────────────────────────────────
    def get_by_role(self, role: str) -> Optional[ModuleState]:
        with self._lock:
            return self._by_role.get(role)

    def all_modules(self) -> List[ModuleState]:
        with self._lock:
            return list(self._by_role.values())

    def connected_roles(self) -> List[str]:
        with self._lock:
            return [m.role for m in self._by_role.values() if m.connected(self.heartbeat_timeout_s)]

    def describe(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "heartbeat_timeout_s": self.heartbeat_timeout_s,
                "modules": [m.describe(self.heartbeat_timeout_s) for m in self._by_role.values()],
                "global_counters": {mid: c.to_dict() for mid, c in sorted(self._global_counters.items())},
            }

    def update_endpoint(
        self,
        role: str,
        *,
        expected_source: Optional[str] = None,
    ) -> Optional[ModuleState]:
        with self._lock:
            module = self._by_role.get(role)
            if module is None:
                return None
            if expected_source is not None:
                if module.expected_source:
                    self._source_to_role.pop(module.expected_source, None)
                module.expected_source = str(expected_source)
                if module.expected_source:
                    self._source_to_role[module.expected_source] = role
            return module


__all__ = ["ModuleRegistry", "ModuleState", "MessageCounter"]
