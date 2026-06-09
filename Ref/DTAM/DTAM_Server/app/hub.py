"""DTAM Server 에뮬레이터 중앙 허브.

역할:
 1. UDP/TCP 리스너 가동 (DTAM_SDK 의 DtamListener 재사용)
 2. 수신한 메시지를 sequence_diagram 규칙대로 Database 저장 + 타 모듈에 포워딩
 3. 0003 Common Time Info 를 1 Hz 로 vehicle / visual 에 주기 전송
 4. 이벤트 브로드캐스트: FastAPI WebSocket 으로 GUI 에 푸시

동기화: 리스너 콜백은 SDK 내부 스레드에서 실행되므로 허브의 내부 상태는
lock 또는 thread-safe 자료구조로 보호한다.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional

from dtam_client import DtamClient  # type: ignore
from dtam_client._listener import DtamListener  # type: ignore

from .config import (
    FORWARD_RULES,
    MESSAGE_TABLE,
    PUSH_SCHEDULE,
    ModuleEndpoint,
    ServerConfig,
)
from .db_writer import DtamFileDb
from .registry import ModuleRegistry

logger = logging.getLogger(__name__)


def _iso_ts() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass
class TrafficEvent:
    ts: float
    mid: str
    name: str
    kind: str              # "rx" | "tx"
    proto: str             # "udp" | "tcp"
    peer_role: Optional[str]
    peer_ip: str
    peer_port: int
    ok: bool
    note: str = ""
    payload_preview: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "mid": self.mid,
            "name": self.name,
            "kind": self.kind,
            "proto": self.proto,
            "peer_role": self.peer_role,
            "peer_ip": self.peer_ip,
            "peer_port": self.peer_port,
            "ok": self.ok,
            "note": self.note,
            "payload_preview": self.payload_preview,
        }


class ServerHub:
    """서버 에뮬레이터 코어.

    사용 예::

        hub = ServerHub(config)
        hub.start()
        hub.on_event = lambda evt: websocket_broadcast(evt.to_dict())
        ...
        hub.stop()
    """

    MAX_TRAFFIC = 400

    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.registry = ModuleRegistry(
            modules=config.modules,
            heartbeat_timeout_s=config.heartbeat_timeout_s,
        )
        self.db = DtamFileDb(config.db_root)
        self._lock = threading.RLock()
        self._running = False
        self._listener: Optional[DtamListener] = None
        self._push_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._traffic: Deque[TrafficEvent] = deque(maxlen=self.MAX_TRAFFIC)
        self._started_at = time.time()
        # per-role 전송 클라이언트 캐시 — peer 별 1개 유지
        self._send_clients: Dict[str, DtamClient] = {}
        # GUI broadcast hook
        self.on_event: Optional[Callable[[TrafficEvent], None]] = None

    # ── 라이프사이클 ──────────────────────────────────────────
    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._started_at = time.time()
            self._stop_event.clear()
            self._build_listener()
            self._running = True
            self._push_thread = threading.Thread(
                target=self._push_loop,
                name="dse-push-loop",
                daemon=True,
            )
            self._push_thread.start()

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
        self._stop_event.set()
        listener = self._listener
        self._listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                logger.exception("listener.stop failed")
        push_thread = self._push_thread
        self._push_thread = None
        if push_thread and push_thread.is_alive():
            push_thread.join(timeout=2.0)
        # close send clients
        with self._lock:
            for client in self._send_clients.values():
                try:
                    client.close()
                except Exception:
                    pass
            self._send_clients.clear()

    # ── 외부 전송 API ─────────────────────────────────────────
    def push_to_role(self, role: str, mid: str, payload: Dict[str, Any], *, image_bytes: bytes = b"") -> Dict[str, Any]:
        """GUI 나 스케줄러가 특정 모듈에 메시지를 보낼 때 호출."""
        module = self.registry.get_by_role(role)
        if module is None:
            return {"ok": False, "error": f"unknown role {role}"}
        proto = str(MESSAGE_TABLE.get(mid, {}).get("proto") or "udp")
        client = self._ensure_send_client(module)
        try:
            result = client.send(
                mid, payload,
                image_bytes=image_bytes,
                target_ip=module.ip,
                udp_port=module.udp_port if proto == "udp" else None,
                tcp_port=module.tcp_port if proto == "tcp" else None,
            )
            ok = bool(result)
            errs = list(getattr(result, "errors", []) or [])
        except Exception as exc:
            ok = False
            errs = [f"{type(exc).__name__}: {exc}"]

        self.registry.note_tx(role, mid, payload)
        evt = TrafficEvent(
            ts=time.time(),
            mid=mid,
            name=str(MESSAGE_TABLE.get(mid, {}).get("name") or mid),
            kind="tx",
            proto=proto,
            peer_role=role,
            peer_ip=module.ip,
            peer_port=module.tcp_port if proto == "tcp" else module.udp_port,
            ok=ok,
            note="forward" if errs == [] and not ok else ("; ".join(errs) if errs else ""),
            payload_preview=_preview(payload),
        )
        self._append_traffic(evt)
        return {"ok": ok, "errors": errs, "target": f"{module.ip}:{evt.peer_port}"}

    def push_scheduled_mid(self, mid: str) -> Dict[str, Any]:
        """PUSH_SCHEDULE 안의 메시지를 지금 한 번 발행."""
        spec = PUSH_SCHEDULE.get(mid)
        if not spec:
            return {"ok": False, "error": f"{mid} not scheduled"}
        payload = self._build_scheduled_payload(mid)
        targets = spec.get("targets") or []
        results: List[Dict[str, Any]] = []
        for role in targets:
            results.append({"role": role, **self.push_to_role(role, mid, payload)})
        try:
            self.db.write_event(mid, payload)
        except Exception:
            logger.exception("Database write failed for %s", mid)
        return {"ok": all(r["ok"] for r in results) if results else False, "results": results}

    # ── 조회 ──────────────────────────────────────────────────
    def snapshot(self) -> Dict[str, Any]:
        """GUI 초기 로드용 상태 스냅샷."""
        with self._lock:
            traffic = [evt.to_dict() for evt in self._traffic]
        registry_desc = self.registry.describe()
        return {
            "running": self._running,
            "started_at": self._started_at,
            "uptime_s": time.time() - self._started_at,
            "server": {
                "bind_ip": self.config.server.bind_ip,
                "udp_port": self.config.server.udp_port,
                "tcp_port": self.config.server.tcp_port,
            },
            "db": self.db.stats(),
            "registry": registry_desc,
            "messages": MESSAGE_TABLE,
            "forward_rules": FORWARD_RULES,
            "push_schedule": PUSH_SCHEDULE,
            "traffic": traffic,
        }

    # ── 내부: 리스너 ──────────────────────────────────────────
    def _build_listener(self) -> None:
        listener = DtamListener(
            bind_ip=self.config.server.bind_ip,
            udp_port=self.config.server.udp_port,
            tcp_port=self.config.server.tcp_port,
        )
        # 콜백 연결 — dispatch_mid 로 한 번에 처리
        listener.on_module_status = lambda r: self._on_received("0002", r)
        listener.on_common_time_info = lambda r: self._on_received("0003", r)
        listener.on_sim_mode_setup = lambda r: self._on_received("1001", r)
        listener.on_simulation_setup = lambda r: self._on_received("1002", r)
        listener.on_scenario_setup = lambda r: self._on_received("1003", r)
        listener.on_flight_plan_request = lambda r: self._on_received("2001", r)
        listener.on_dtam_execute = lambda r: self._on_received("2002", r)
        listener.on_scheduled_flight = lambda r: self._on_received("3001", r)
        listener.on_strategic_separation = lambda r: self._on_received("3002", r)
        listener.on_tactical_separation = lambda r: self._on_received("3003", r)
        listener.on_vehicle_status = lambda r: self._on_received("4001", r)
        listener.on_camera_image = lambda r: self._on_received("4101", r)
        listener.start(block=False)
        self._listener = listener

    # ── 내부: 수신 핸들러 ────────────────────────────────────
    def _on_received(self, mid: str, result: Any) -> None:
        payload = self._result_to_dict(result)
        image_bytes = getattr(result, "image_bytes", b"") or b""

        # 1) 역할 파악
        role: Optional[str] = None
        if mid == "0002":
            role = self.registry.heartbeat(payload)
        else:
            direction = str(MESSAGE_TABLE.get(mid, {}).get("direction") or "")
            if "->server" in direction:
                role = direction.split("->")[0].strip()

        # 2) rx 카운트 + Database 저장
        self.registry.note_rx(role, mid, payload)
        try:
            self.db.write_event(mid, payload, extra_bytes=image_bytes)
        except Exception:
            logger.exception("Database write failed for %s", mid)

        # 3) GUI 이벤트 브로드캐스트
        peer_ip = ""
        peer_port = 0
        if role:
            module = self.registry.get_by_role(role)
            if module is not None:
                peer_ip = module.ip
                peer_port = module.tcp_port if MESSAGE_TABLE.get(mid, {}).get("proto") == "tcp" else module.udp_port
        rx_evt = TrafficEvent(
            ts=time.time(),
            mid=mid,
            name=str(MESSAGE_TABLE.get(mid, {}).get("name") or mid),
            kind="rx",
            proto=str(MESSAGE_TABLE.get(mid, {}).get("proto") or "udp"),
            peer_role=role,
            peer_ip=peer_ip,
            peer_port=peer_port,
            ok=True,
            note="save" if role is not None else "received",
            payload_preview=_preview(payload),
        )
        self._append_traffic(rx_evt)

        # 4) 포워딩
        forward_roles = FORWARD_RULES.get(mid, [])
        for target_role in forward_roles:
            if target_role == role:
                continue  # 자기 자신에게 되돌리지 않음
            self.push_to_role(target_role, mid, payload, image_bytes=image_bytes)

    # ── 내부: 주기 push (0003 등) ─────────────────────────────
    def _push_loop(self) -> None:
        last_fire: Dict[str, float] = {}
        while not self._stop_event.is_set():
            for mid, spec in PUSH_SCHEDULE.items():
                rate = max(1e-3, float(spec.get("rate_hz") or 1.0))
                period = 1.0 / rate
                now = time.time()
                if now - last_fire.get(mid, 0.0) < period:
                    continue
                last_fire[mid] = now
                try:
                    self.push_scheduled_mid(mid)
                except Exception:
                    logger.exception("scheduled push failed for %s", mid)
            # 50 ms 마다 체크 — 최소 주기 1 Hz 기준 여유
            if self._stop_event.wait(timeout=0.05):
                break

    def _build_scheduled_payload(self, mid: str) -> Dict[str, Any]:
        if mid == "0003":
            return {
                "timestamp": _iso_ts(),
                "simTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        return {"timestamp": _iso_ts()}

    # ── 내부: 전송 클라이언트 캐시 ───────────────────────────
    def _ensure_send_client(self, module: Any) -> DtamClient:
        with self._lock:
            client = self._send_clients.get(module.role)
            if client is not None:
                try:
                    client.configure(
                        target_ip=module.ip,
                        target_udp_port=module.udp_port,
                        target_tcp_port=module.tcp_port,
                    )
                except Exception:
                    client = None
            if client is None:
                client = DtamClient.module(
                    my_ip=self.config.server.bind_ip if self.config.server.bind_ip != "0.0.0.0" else "127.0.0.1",
                    my_port=self.config.server.udp_port + 2,          # 전송 bind 는 서버 수신 포트와 겹치지 않게
                    peer_ip=module.ip,
                    peer_port=module.udp_port,
                    peer_tcp_port=module.tcp_port,
                    auto_listen=False,
                )
                self._send_clients[module.role] = client
            return client

    # ── 내부: 트래픽 기록 + 브로드캐스트 ─────────────────────
    def _append_traffic(self, evt: TrafficEvent) -> None:
        with self._lock:
            self._traffic.append(evt)
        hook = self.on_event
        if hook is not None:
            try:
                hook(evt)
            except Exception:
                logger.exception("on_event hook raised")

    @staticmethod
    def _result_to_dict(result: Any) -> Dict[str, Any]:
        if result is None:
            return {}
        if isinstance(result, dict):
            return result
        if hasattr(result, "raw") and isinstance(result.raw, dict):
            return dict(result.raw)
        if hasattr(result, "to_dict"):
            try:
                data = result.to_dict()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {"_repr": repr(result)}

    def update_module_endpoint(
        self,
        role: str,
        *,
        ip: Optional[str] = None,
        udp_port: Optional[int] = None,
        tcp_port: Optional[int] = None,
        expected_source: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        module = self.registry.update_endpoint(
            role,
            ip=ip,
            udp_port=udp_port,
            tcp_port=tcp_port,
            expected_source=expected_source,
        )
        if module is None:
            return None
        # send client 캐시 무효화
        with self._lock:
            cached = self._send_clients.pop(role, None)
        if cached is not None:
            try:
                cached.close()
            except Exception:
                pass
        return module.describe(self.registry.heartbeat_timeout_s)


def _preview(payload: Any, *, limit: int = 240) -> Any:
    """Traffic 이벤트에 찔러넣을 미니 payload — JSON 길이 제한."""
    if not isinstance(payload, dict):
        return payload
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except Exception:
        return None
    if len(text) <= limit:
        return payload
    return {"_truncated": text[:limit] + f"...({len(text) - limit}B more)"}


__all__ = ["ServerHub", "TrafficEvent"]
