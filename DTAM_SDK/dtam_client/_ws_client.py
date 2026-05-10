"""DTAM WebSocket 기반 클라이언트.

모듈 개발자가 서버 URL 하나만 알면 바로 통신할 수 있는 간결한 클라이언트.

사용 예::

    from dtam_client import DtamWsClient

    dtam = DtamWsClient(
    url="ws://127.0.0.1:8096/ws/dtam",
        role="vehicle",
        source="DTAMAirMobility",
    )

    @dtam.on("3001")
    def on_flight(payload):
        print("비행계획 수신:", payload)

    dtam.connect()                # 백그라운드 스레드에서 WebSocket 수신 시작
    dtam.send("4001", payload)    # 메시지 전송
    dtam.disconnect()             # 연결 종료
"""
from __future__ import annotations

import base64
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class DtamWsClient:
    """WebSocket 기반 DTAM 클라이언트.

    - ``connect()`` 호출 시 백그라운드 스레드에서 서버에 연결 + 수신 루프 시작
    - ``send(mid, payload)`` 로 메시지 전송
    - ``on(mid, callback)`` 으로 수신 콜백 등록
    - 자동 재연결 내장
    """

    def __init__(
        self,
        url: str,
        *,
        role: str,
        source: str = "",
        reconnect_delay: float = 3.0,
    ) -> None:
        self.url = url
        self.role = role
        self.source = source
        self.reconnect_delay = float(reconnect_delay)

        self._ws: Any = None  # websocket.WebSocket instance
        self._callbacks: Dict[str, Callable] = {}
        self._connected = False
        self._registered = False
        self._subscriptions: List[str] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._send_lock = threading.Lock()

    # ── 공개 API ─────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        """서버에 연결되어 있는지 여부."""
        return self._connected

    @property
    def registered(self) -> bool:
        """서버에 role 등록이 완료되었는지 여부."""
        return self._registered

    @property
    def subscriptions(self) -> List[str]:
        """서버가 이 모듈에 보내줄 메시지 ID 목록."""
        return list(self._subscriptions)

    def on(self, mid: str, callback: Optional[Callable] = None):
        """메시지 수신 콜백 등록. 데코레이터로도 사용 가능.

        사용 예::

            @dtam.on("3001")
            def on_flight(payload: dict):
                print(payload)

            # 또는
            dtam.on("3001", my_handler)
        """
        def register(cb: Callable) -> Callable:
            self._callbacks[str(mid)] = cb
            return cb
        if callback is not None:
            return register(callback)
        return register

    def connect(self, block: bool = False) -> None:
        """서버에 연결. block=True이면 disconnect될 때까지 블로킹."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._connect_loop,
            name=f"dtam-ws-{self.role}",
            daemon=True,
        )
        self._thread.start()
        if block:
            try:
                while self._running:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                self.disconnect()

    def disconnect(self) -> None:
        """연결 종료."""
        self._running = False
        ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        self._connected = False
        self._registered = False
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=3.0)
        self._thread = None

    def close(self) -> None:
        """disconnect의 별칭."""
        self.disconnect()

    def send(self, mid: str, payload: Dict[str, Any],
             image_bytes: bytes = b"") -> bool:
        """서버에 메시지 전송.

        Args:
            mid: 메시지 ID (예: "4001", "3001")
            payload: JSON 직렬화 가능한 dict
            image_bytes: 4101 카메라용 바이너리 데이터 (선택)

        Returns:
            전송 성공 여부
        """
        if not self._connected or self._ws is None:
            logger.warning("[DtamWsClient] not connected, send(%s) skipped", mid)
            return False

        msg: Dict[str, Any] = {
            "type": "message",
            "mid": str(mid),
            "payload": payload,
        }
        if image_bytes:
            msg["image_b64"] = base64.b64encode(image_bytes).decode()

        with self._send_lock:
            try:
                self._ws.send(json.dumps(msg, ensure_ascii=False))
                return True
            except Exception as exc:
                logger.warning("[DtamWsClient] send(%s) failed: %s", mid, exc)
                self._connected = False
                return False

    # ── 내부 ─────────────────────────────────────────────────

    def _connect_loop(self) -> None:
        """자동 재연결 루프."""
        try:
            import websocket as ws_lib
        except ImportError:
            logger.error(
                "[DtamWsClient] 'websocket-client' 패키지가 필요합니다. "
                "설치: pip install websocket-client"
            )
            self._running = False
            return

        while self._running:
            try:
                ws = ws_lib.WebSocket()
                ws.settimeout(5.0)
                logger.info("[DtamWsClient] connecting to %s ...", self.url)
                ws.connect(self.url)
                self._ws = ws
                self._connected = True
                logger.info("[DtamWsClient] connected")

                # 등록
                self._do_register(ws)

                # 수신 루프
                ws.settimeout(None)  # 블로킹 수신
                self._recv_loop(ws)

            except Exception as exc:
                logger.warning("[DtamWsClient] connection error: %s", exc)
                self._connected = False
                self._registered = False

            if self._running:
                logger.info(
                    "[DtamWsClient] reconnecting in %.1fs ...",
                    self.reconnect_delay,
                )
                time.sleep(self.reconnect_delay)

    def _do_register(self, ws: Any) -> None:
        """서버에 role 등록."""
        register_msg = json.dumps({
            "type": "register",
            "role": self.role,
            "source": self.source,
        })
        ws.send(register_msg)

        # 등록 응답 대기
        ws.settimeout(5.0)
        try:
            raw = ws.recv()
            resp = json.loads(raw)
            if resp.get("type") == "registered":
                self._registered = True
                self._subscriptions = resp.get("subscriptions", [])
                logger.info(
                    "[DtamWsClient] registered as '%s', subscriptions: %s",
                    self.role,
                    self._subscriptions,
                )
            elif resp.get("type") == "error":
                logger.error(
                    "[DtamWsClient] registration failed: %s",
                    resp.get("error"),
                )
        except Exception as exc:
            logger.warning("[DtamWsClient] register response failed: %s", exc)

    def _recv_loop(self, ws: Any) -> None:
        """메시지 수신 루프."""
        while self._running:
            try:
                raw = ws.recv()
                if not raw:
                    break
                msg = json.loads(raw)
            except Exception:
                break

            msg_type = str(msg.get("type") or "")
            if msg_type == "message":
                mid = str(msg.get("mid") or "")
                payload = msg.get("payload") or {}
                cb = self._callbacks.get(mid)
                if cb is not None:
                    try:
                        cb(payload)
                    except Exception as exc:
                        logger.exception(
                            "[DtamWsClient] callback error for %s: %s",
                            mid, exc,
                        )
            elif msg_type == "pong":
                pass  # heartbeat 응답
            elif msg_type == "error":
                logger.warning(
                    "[DtamWsClient] server error: %s",
                    msg.get("error"),
                )

        self._connected = False
        self._registered = False

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"DtamWsClient(url={self.url!r}, role={self.role!r}, {status})"


__all__ = ["DtamWsClient"]
