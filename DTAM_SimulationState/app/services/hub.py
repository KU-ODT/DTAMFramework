"""DTAM Simulation State 중앙 허브 (WebSocket-only).

역할:
 1. WebSocket 모듈 연결 관리 (/ws/dtam)
 2. 수신 메시지를 ICD 검증 → registry 갱신 → DB 기록 → 다른 모듈로 forward
 3. 0003 Common Time Info 1 Hz 송신은 SimulationEngine 이 hub.push_to_role 으로 위임
 4. TrafficEvent 를 GUI WebSocket(/ws/events) 로 브로드캐스트
 5. 카메라 프레임(4101) 저장 → MJPEG 스트림 제공

동기화: WebSocket 콜백은 FastAPI 의 asyncio loop 에서 실행되지만, 외부에서
일반 thread 가 push_to_role 을 호출하는 경우도 있어 내부 상태는 RLock 으로
보호한다.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional

from DTAM_CoreServer.app.model.config import ServerConfig
from DTAM_CoreServer.app.model.message import FORWARD_RULES, MESSAGE_TABLE
from DTAM_CoreServer.app.model.traffic import TrafficEvent
# ICD dataclass + parse/to_dict 는 SDK 단일 권위
from dtam_client.schema import parse_payload, to_dict as icd_to_dict
from DTAM_CoreServer.app.services.registry import ModuleRegistry

logger = logging.getLogger(__name__)


def _iso_ts() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


class ServerHub:
    """서버 코어 (WebSocket only).

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
        self._lock = threading.RLock()
        self._running = False
        self._stop_event = threading.Event()
        self._traffic: Deque[TrafficEvent] = deque(maxlen=self.MAX_TRAFFIC)
        self._started_at = time.time()
        # GUI broadcast hook
        self.on_event: Optional[Callable[[TrafficEvent], None]] = None
        # ── WebSocket 모듈 연결 관리 ─────────────────────────
        self._ws_clients: Dict[str, Any] = {}   # role -> WebSocket
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        # ── 카메라 프레임 저장 (4101 MJPEG 스트림용) ──────────
        self.camera_frames: Dict[str, bytes] = {}   # vehicle_id -> JPEG bytes

    # ── 라이프사이클 ──────────────────────────────────────────
    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._started_at = time.time()
            self._stop_event.clear()
            self._running = True

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
        self._stop_event.set()

    # ── WebSocket 모듈 관리 ────────────────────────────────────
    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """FastAPI startup 시 이벤트 루프를 등록."""
        self._event_loop = loop

    def register_ws_module(self, role: str, ws: Any, source: str = "") -> None:
        """WebSocket 모듈 등록. role 당 1개."""
        with self._lock:
            self._ws_clients[role] = ws
        if source:
            self.registry.heartbeat({"source": source})
        logger.info("WS module registered: role=%s source=%s", role, source)

    def unregister_ws_module(self, role: str) -> None:
        """WebSocket 모듈 해제."""
        with self._lock:
            self._ws_clients.pop(role, None)
        logger.info("WS module unregistered: role=%s", role)

    def ws_connected_roles(self) -> List[str]:
        """현재 WebSocket 으로 연결된 역할 목록."""
        with self._lock:
            return list(self._ws_clients.keys())

    def _send_ws(self, ws: Any, data: Dict[str, Any]) -> bool:
        """Thread-safe WebSocket 전송 (sync 스레드 → async 이벤트루프)."""
        try:
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if current_loop:
                # 이미 비동기 스코프(이벤트 루프 스레드) 내 — fire-and-forget
                current_loop.create_task(ws.send_json(data))
                return True
            else:
                # 외부 일반 스레드에서 호출 시
                loop = self._event_loop
                if loop is None:
                    return False
                future = asyncio.run_coroutine_threadsafe(ws.send_json(data), loop)
                future.result(timeout=2.0)
                return True
        except Exception as exc:
            logger.debug("WS send failed: %s", exc)
            return False

    def on_ws_message(self, role: str, mid: str, payload: Dict[str, Any],
                      image_bytes: bytes = b"") -> None:
        """WebSocket 에서 수신한 메시지를 파이프라인에 투입."""
        logger.debug("[WS] received %s from %s", mid, role)

        # 4101 카메라: image_bytes 보관
        if mid == "4101" and image_bytes:
            vehicle_id = str(payload.get("vehicle_id") or payload.get("aircraftId") or "unknown")
            with self._lock:
                self.camera_frames[vehicle_id] = image_bytes

        # ICD dataclass 정적 검증
        try:
            parsed = parse_payload(mid, payload)
            payload = icd_to_dict(parsed) if parsed is not payload else payload
        except Exception as exc:
            logger.warning("ICD validation failed for %s: %s", mid, exc)

        # 0002 heartbeat 갱신, 그 외엔 direction 으로 role 추정도 가능
        if mid == "0002":
            self.registry.heartbeat(payload)

        self.registry.note_rx(role, mid, payload)

        rx_evt = TrafficEvent(
            ts=time.time(), mid=mid,
            name=str(MESSAGE_TABLE.get(mid, {}).get("name") or mid),
            kind="rx", proto="ws", peer_role=role,
            peer_ip="ws", peer_port=0, ok=True,
            note="ws", payload_preview=_preview(payload),
            full_payload=payload,
        )
        self._append_traffic(rx_evt)

        # 포워딩 — FORWARD_RULES 그대로. DB 기록은 server.on_event 가 처리.
        for target_role in FORWARD_RULES.get(mid, []):
            if target_role == role:
                continue
            self.push_to_role(target_role, mid, payload, image_bytes=image_bytes)

    # ── 외부 전송 API ─────────────────────────────────────────
    def push_to_role(self, role: str, mid: str, payload: Dict[str, Any],
                     *, image_bytes: bytes = b"") -> Dict[str, Any]:
        """특정 역할에 메시지 전송. WebSocket 연결이 있어야 송신 가능."""
        with self._lock:
            ws = self._ws_clients.get(role)

        if ws is None:
            # 연결되지 않은 role — 송신 시도 자체가 noop. registry 만 갱신.
            self.registry.note_tx(role, mid, payload)
            evt = TrafficEvent(
                ts=time.time(), mid=mid,
                name=str(MESSAGE_TABLE.get(mid, {}).get("name") or mid),
                kind="tx", proto="ws", peer_role=role,
                peer_ip="-", peer_port=0, ok=False,
                note="not connected", payload_preview=_preview(payload),
                full_payload=payload,
            )
            self._append_traffic(evt)
            return {"ok": False, "errors": ["not connected"], "target": f"ws:{role}"}

        # WS 송신
        msg: Dict[str, Any] = {"type": "message", "mid": mid, "from_role": "server",
                               "payload": payload}
        if image_bytes and mid == "4101":
            msg["image_b64"] = base64.b64encode(image_bytes).decode()
        ok = self._send_ws(ws, msg)
        errs: List[str] = [] if ok else ["WebSocket send failed"]
        self.registry.note_tx(role, mid, payload)

        # Visual 모듈은 수신 전용이므로 데이터 송신 시 하트비트 자동 갱신
        if role == "visual":
            self.registry.heartbeat({"source": "DTAM_VISUAL"})

        evt = TrafficEvent(
            ts=time.time(), mid=mid,
            name=str(MESSAGE_TABLE.get(mid, {}).get("name") or mid),
            kind="tx", proto="ws", peer_role=role,
            peer_ip="ws", peer_port=0, ok=ok,
            note="" if ok else "ws send failed",
            payload_preview=_preview(payload),
            full_payload=payload,
        )
        self._append_traffic(evt)
        return {"ok": ok, "errors": errs, "target": f"ws:{role}"}

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
                "ws_port": getattr(self.config, "ws_port", 8096),
            },
            "registry": registry_desc,
            "messages": MESSAGE_TABLE,
            "forward_rules": FORWARD_RULES,
            "traffic": traffic,
        }

    # ── 모듈 endpoint 갱신 ────────────────────────────────────
    def update_module_endpoint(
        self,
        role: str,
        *,
        expected_source: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """모듈 expected_source 갱신 (WS-only 환경에서는 source 매칭만 의미)."""
        module = self.registry.update_endpoint(
            role,
            expected_source=expected_source,
        )
        if module is None:
            return None
        return module.describe(self.registry.heartbeat_timeout_s)

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


def _preview(payload: Any, *, limit: int = 240) -> Any:
    """Traffic 이벤트에 들어갈 미니 payload — JSON 길이 제한."""
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
