"""Low-level WebSocket client for DTAM modules.
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
    """Internal DTAM helper."""

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
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._send_lock = threading.Lock()

    # Registration handling

    @property
    def connected(self) -> bool:
        """Internal helper."""
        return self._connected

    @property
    def registered(self) -> bool:
        """Internal helper."""
        return self._registered

    @property
    def subscriptions(self) -> List[str]:
        """Internal helper."""
        return list(self._subscriptions)

    def on(self, mid: str, callback: Optional[Callable] = None):
        """Internal DTAM helper."""
        def register(cb: Callable) -> Callable:
            self._callbacks[str(mid)] = cb
            return cb
        if callback is not None:
            return register(callback)
        return register

    def connect(self, block: bool = False) -> None:
        """Internal helper."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
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
        """Internal helper."""
        self._running = False
        self._stop_event.set()
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
        """Internal helper."""
        self.disconnect()

    def send(self, mid: str, payload: Dict[str, Any],
             image_bytes: bytes = b"") -> bool:
        """Internal DTAM helper."""
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

    # Registration handling

    def _connect_loop(self) -> None:
        """Internal helper."""
        try:
            import websocket as ws_lib
        except ImportError:
            logger.error(
                    "[DtamWsClient] The 'websocket-client' package is required. "
                    "Install: pip install websocket-client"
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

                # Registration handling
                self._do_register(ws)

                # Registration handling
                ws.settimeout(None)  # Blocking receive
                self._recv_loop(ws)

            except Exception as exc:
                if self._running:
                    logger.warning("[DtamWsClient] connection error: %s", exc)
                self._connected = False
                self._registered = False

            if self._running:
                logger.info(
                    "[DtamWsClient] reconnecting in %.1fs ...",
                    self.reconnect_delay,
                )
                self._stop_event.wait(self.reconnect_delay)

    def _do_register(self, ws: Any) -> None:
        """Internal helper."""
        register_msg = json.dumps({
            "type": "register",
            "role": self.role,
            "source": self.source,
        })
        ws.send(register_msg)

        # Registration handling
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
        """Internal helper."""
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
                image_b64 = msg.get("image_b64") or ""
                if image_b64 and isinstance(payload, dict) and not payload.get("image_b64"):
                    payload = dict(payload)
                    payload["image_b64"] = image_b64
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
                pass  # heartbeat response
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
