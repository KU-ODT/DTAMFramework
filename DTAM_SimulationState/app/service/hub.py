"""DTAM Server 중앙 허브.

역할:
 1. UDP/TCP 리스너 가동 (DTAM_SDK 의 DtamListener 재사용)
 2. WebSocket 모듈 연결 지원 (/ws/dtam)
 3. 수신한 메시지를 sequence_diagram 규칙대로 DB 저장 + 타 모듈에 포워딩
 4. 0003 Common Time Info 를 1 Hz 로 vehicle / visual 에 주기 전송
 5. 이벤트 브로드캐스트: FastAPI WebSocket 으로 GUI 에 푸시
 6. 카메라 프레임(4101) 저장 → MJPEG 스트림 제공

동기화: 리스너 콜백은 SDK 내부 스레드에서 실행되므로 허브의 내부 상태는
lock 또는 thread-safe 자료구조로 보호한다.
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
from pathlib import Path
import sys
from typing import Any, Callable, Deque, Dict, List, Optional

# DTAM_SDK 로컬 경로 우선 참조
_HERE = Path(__file__).resolve()
_FRAMEWORK_ROOT = _HERE.parents[3] # DTAMFramework
_SDK_PATH = _FRAMEWORK_ROOT / "DTAM_SDK"
if _SDK_PATH.is_dir() and str(_SDK_PATH) not in sys.path:
    sys.path.insert(0, str(_SDK_PATH))

from dtam_client import DtamClient  # type: ignore
from dtam_client._listener import DtamListener  # type: ignore

from DTAM_CoreServer.app.model.config import ServerConfig
from DTAM_CoreServer.app.model.message import FORWARD_RULES, MESSAGE_TABLE
from DTAM_CoreServer.app.model.traffic import TrafficEvent
from DTAM_CoreServer.app.schema.icd_registry import parse_payload, to_dict as icd_to_dict
from DTAM_CoreServer.app.service.registry import ModuleRegistry

logger = logging.getLogger(__name__)


def _iso_ts() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


# TrafficEvent 는 model.traffic 에서 import
# from ..model.traffic import TrafficEvent  (위에서 이미 import됨)


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
        import inspect
        print(f"[DEBUG] DtamClient loaded from: {inspect.getfile(DtamClient)}")
        print(f"[DEBUG] DtamClient.__init__ args: {inspect.signature(DtamClient.__init__)}")
        
        self.config = config
        self.registry = ModuleRegistry(
            modules=config.modules,
            heartbeat_timeout_s=config.heartbeat_timeout_s,
        )
        self._lock = threading.RLock()
        self._running = False
        self._listener: Optional[DtamListener] = None
        self._stop_event = threading.Event()
        self._traffic: Deque[TrafficEvent] = deque(maxlen=self.MAX_TRAFFIC)
        self._started_at = time.time()
        # per-role 전송 클라이언트 캐시 — peer 별 1개 유지
        self._send_clients: Dict[str, DtamClient] = {}
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
            self._build_listener()
            self._running = True

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
        # close send clients
        with self._lock:
            for client in self._send_clients.values():
                try:
                    client.close()
                except Exception:
                    pass
            self._send_clients.clear()

    # ── WebSocket 모듈 관리 ────────────────────────────────────
    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """FastAPI startup 시 이벤트 루프를 등록."""
        self._event_loop = loop

    def register_ws_module(self, role: str, ws: Any, source: str = "") -> None:
        """WebSocket 모듈 등록. role 당 1개."""
        with self._lock:
            self._ws_clients[role] = ws
        # heartbeat 자동 갱신
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
                # 이미 비동기 스코프(이벤트 루프 스레드)에서 실행 중이므로 fire-and-forget
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
        """WebSocket 에서 수신한 메시지를 기존 파이프라인에 투입."""
        logger.info(f"[DEBUG WS] received {mid} from {role}")
        # 4101 카메라: image_bytes 보관
        if mid == "4101" and image_bytes:
            vehicle_id = str(payload.get("vehicle_id") or payload.get("aircraftId") or "unknown")
            with self._lock:
                self.camera_frames[vehicle_id] = image_bytes

        # ICD dataclass 정적 검증
        try:
            parsed = parse_payload(mid, payload)
            payload = icd_to_dict(parsed) if parsed is not payload else payload
            logger.info(f"[DEBUG WS] validation passed for {mid}")
        except Exception as exc:
            logger.error(f"[DEBUG WS] validation failed for {mid}: {exc}")

        # 기존 _on_received 와 동일한 파이프라인
        if mid == "0002":
            self.registry.heartbeat(payload)

        self.registry.note_rx(role, mid, payload)

        # GUI 이벤트
        rx_evt = TrafficEvent(
            ts=time.time(), mid=mid,
            name=str(MESSAGE_TABLE.get(mid, {}).get("name") or mid),
            kind="rx", proto="ws", peer_role=role,
            peer_ip="ws", peer_port=0, ok=True,
            note="ws", payload_preview=_preview(payload),
            full_payload=payload,
        )
        self._append_traffic(rx_evt)

        # 포워딩
        forward_roles = FORWARD_RULES.get(mid, [])
        # DB 로깅을 위해 sim_state 에게 항상 복사본 전달
        if "sim_state" not in forward_roles:
            forward_roles = list(forward_roles) + ["sim_state"]
        
        logger.info(f"[DEBUG WS] forwarding {mid} to {forward_roles}")
        for target_role in forward_roles:
            if target_role == role:
                continue
            res = self.push_to_role(target_role, mid, payload, image_bytes=image_bytes)
            logger.info(f"[DEBUG WS] pushed {mid} to {target_role}: {res}")

    # ── 외부 전송 API ─────────────────────────────────────────
    def push_to_role(self, role: str, mid: str, payload: Dict[str, Any], *, image_bytes: bytes = b"") -> Dict[str, Any]:
        """GUI 나 스케줄러가 특정 모듈에 메시지를 보낼 때 호출.

        WebSocket 연결이 있으면 WS 로, 없으면 기존 UDP/TCP 로 전송.
        """
        proto = str(MESSAGE_TABLE.get(mid, {}).get("proto") or "udp")

        # ── WebSocket 전송 시도 ──────────────────────────────
        with self._lock:
            ws = self._ws_clients.get(role)
        if ws is not None:
            msg: Dict[str, Any] = {"type": "message", "mid": mid, "from_role": "server", "payload": payload}
            if image_bytes and mid == "4101":
                msg["image_b64"] = base64.b64encode(image_bytes).decode()
            ok = self._send_ws(ws, msg)
            errs: List[str] = [] if ok else ["WebSocket send failed"]
            self.registry.note_tx(role, mid, payload)
            
            # [NEW] Visual 모듈은 수신 전용이므로, 데이터를 보낼 때 하트비트 자동 갱신
            if role == "visual":
                self.registry.heartbeat({"source": "DTAM_VISUAL"})

            evt = TrafficEvent(
                ts=time.time(), mid=mid,
                name=str(MESSAGE_TABLE.get(mid, {}).get("name") or mid),
                kind="tx", proto="ws", peer_role=role,
                peer_ip="ws", peer_port=0, ok=ok,
                note="", payload_preview=_preview(payload),
                full_payload=payload,
            )
            self._append_traffic(evt)
            return {"ok": ok, "errors": errs, "target": f"ws:{role}"}

        # ── 기존 UDP/TCP 전송 ────────────────────────────────
        module = self.registry.get_by_role(role)
        if module is None:
            return {"ok": False, "error": f"unknown role {role}"}

        # ── 기존 UDP/TCP 전송 ────────────────────────────────
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

        # [NEW] Visual 모듈 하트비트 자동 갱신
        if role == "visual":
            self.registry.heartbeat({"source": "DTAM_VISUAL"})

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
            full_payload=payload,
        )
        self._append_traffic(evt)
        return {"ok": ok, "errors": errs, "target": f"{module.ip}:{evt.peer_port}"}

    # ── 주기/DB 삭제됨 ──
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
            "registry": registry_desc,
            "messages": MESSAGE_TABLE,
            "forward_rules": FORWARD_RULES,
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

        # ICD dataclass 정적 검증
        parsed = parse_payload(mid, payload)
        payload = icd_to_dict(parsed) if parsed is not payload else payload

        # 1) 역할 파악
        role: Optional[str] = None
        if mid == "0002":
            role = self.registry.heartbeat(payload)
        else:
            direction = str(MESSAGE_TABLE.get(mid, {}).get("direction") or "")
            if "->server" in direction:
                role = direction.split("->")[0].strip()
            
            # [NEW] 메시지가 수신되었다면 해당 모듈은 살아있는 것이므로 하트비트 갱신
            if role:
                self.registry.heartbeat({"source": f"DTAM_{role.upper()}"})

        # 2) rx 카운트
        self.registry.note_rx(role, mid, payload)

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
            full_payload=payload,
        )
        self._append_traffic(rx_evt)

        # 4) 포워딩
        forward_roles = FORWARD_RULES.get(mid, [])
        # DB 로깅을 위해 sim_state 에게 항상 복사본 전달
        if "sim_state" not in forward_roles:
            forward_roles = list(forward_roles) + ["sim_state"]
            
        for target_role in forward_roles:
            if target_role == role:
                continue  # 자기 자신에게 되돌리지 않음
            self.push_to_role(target_role, mid, payload, image_bytes=image_bytes)

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
