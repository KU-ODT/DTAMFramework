"""Central Simulation State hub for WebSocket modules, message forwarding, DB logging, and GUI event broadcasts.
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

from IntegrationHub.CoreServerModule.app.model.config import ServerConfig
from IntegrationHub.CoreServerModule.app.model.message import FORWARD_RULES, MESSAGE_TABLE
from IntegrationHub.CoreServerModule.app.model.traffic import TrafficEvent
# Registration handling
from dtam_client.schema import parse_payload, to_dict as icd_to_dict
from IntegrationHub.CoreServerModule.app.services.registry import ModuleRegistry

logger = logging.getLogger(__name__)
OPTIONAL_FORWARD_ROLES = {"situation_awareness", "psu"}
HIGH_RATE_MIDS = {"4001", "4101", "5001"}
LATEST_ONLY_FORWARD_MIDS = {"4001", "4101"}
CAMERA_4101_FORWARD_ROLES = {"situation_awareness"}

# MSG 4101 is intentionally treated as a low-rate ICD snapshot path.  High-rate
# video should use the direct media-plane URL announced by MSG 4102; accepting
# every base64 JPEG over /ws/dtam makes the single asyncio receive loop spend
# most of its time JSON/base64 handling and forwarding camera frames.
CAMERA_4101_ACCEPT_MIN_INTERVAL_S = 0.2  # 5 FPS max per vehicle/camera.

# Additional per-target forward caps.  These are safety valves: a slow
# monitoring/AI client must not build an unbounded backlog that delays control
# or vehicle-state messages for other clients.
FORWARD_MIN_INTERVAL_S = {
    "4101": 0.5,  # 2 FPS max per target for server-forwarded image bytes.
}


def _iso_ts() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


class ServerHub:
    """Internal DTAM helper."""

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
        # Registration handling
        self._ws_clients: Dict[str, Any] = {}   # role -> WebSocket
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        # Registration handling
        self.camera_frames: Dict[str, bytes] = {}   # vehicle_id -> JPEG bytes
        self.camera_streams: Dict[str, Dict[str, Any]] = {}   # stream_id -> 4102 descriptor
        self._last_camera_accept_ts: Dict[str, float] = {}
        self._last_forward_ts: Dict[tuple[str, str], float] = {}
        self._pending_latest_send: Dict[tuple[str, str], int] = {}
        self._dropped_latest_send: Dict[tuple[str, str], int] = {}

    # Registration handling
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

    # Registration handling
    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Internal helper."""
        self._event_loop = loop

    def register_ws_module(self, role: str, ws: Any, source: str = "") -> None:
        """Internal helper."""
        with self._lock:
            self._ws_clients[role] = ws
        if source:
            self.registry.heartbeat({"source": source})
        logger.info("WS module registered: role=%s source=%s", role, source)

    def unregister_ws_module(self, role: str, ws: Any = None) -> None:
        """Internal helper."""
        with self._lock:
            current = self._ws_clients.get(role)
            if ws is None or current is ws:
                self._ws_clients.pop(role, None)
        logger.info("WS module unregistered: role=%s", role)

    def ws_connected_roles(self) -> List[str]:
        """Internal helper."""
        with self._lock:
            return list(self._ws_clients.keys())

    def should_accept_message(self, mid: str, payload: Dict[str, Any]) -> bool:
        """Return whether an inbound high-rate message should be processed.

        The server cannot avoid receiving a full text WebSocket frame, but this
        gate lets us skip expensive base64 decoding, DB writes, event fan-out,
        and downstream forwarding for excessive 4101 camera snapshots.
        """
        mid = str(mid)
        if mid != "4101":
            return True

        now = time.monotonic()
        key = _camera_key(payload)
        with self._lock:
            last = float(self._last_camera_accept_ts.get(key, 0.0) or 0.0)
            if now - last < CAMERA_4101_ACCEPT_MIN_INTERVAL_S:
                return False
            self._last_camera_accept_ts[key] = now
            return True

    def _send_ws(self, ws: Any, data: Dict[str, Any], *, role: str = "", mid: str = "") -> bool:
        """Internal helper."""
        try:
            key = (str(role or ""), str(mid or data.get("mid") or ""))
            latest_only = bool(key[0] and key[1] in LATEST_ONLY_FORWARD_MIDS)
            if latest_only:
                with self._lock:
                    pending = int(self._pending_latest_send.get(key, 0) or 0)
                    if pending > 0:
                        self._dropped_latest_send[key] = int(self._dropped_latest_send.get(key, 0) or 0) + 1
                        return False
                    self._pending_latest_send[key] = pending + 1

            def _mark_done(_: Any = None) -> None:
                try:
                    if _ is not None and hasattr(_, "exception"):
                        _.exception()
                except Exception:
                    pass
                if not latest_only:
                    return
                with self._lock:
                    current = int(self._pending_latest_send.get(key, 0) or 0)
                    if current <= 1:
                        self._pending_latest_send.pop(key, None)
                    else:
                        self._pending_latest_send[key] = current - 1

            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if current_loop:
                # Registration handling
                task = current_loop.create_task(ws.send_json(data))
                task.add_done_callback(_mark_done)
                return True
            else:
                loop = self._event_loop
                if loop is None:
                    _mark_done()
                    return False
                future = asyncio.run_coroutine_threadsafe(ws.send_json(data), loop)
                future.result(timeout=2.0)
                _mark_done()
                return True
        except Exception as exc:
            try:
                _mark_done()
            except Exception:
                pass
            logger.debug("WS send failed: %s", exc)
            return False

    def on_ws_message(self, role: str, mid: str, payload: Dict[str, Any],
                      image_bytes: bytes = b"") -> None:
        """Internal helper."""
        logger.debug("[WS] received %s from %s", mid, role)

        # Registration handling
        if mid == "4101" and image_bytes:
            vehicle_id = str(payload.get("vehicle_id") or payload.get("aircraftId") or "unknown")
            with self._lock:
                self.camera_frames[vehicle_id] = image_bytes
        if mid == "4102" and isinstance(payload, dict):
            stream_id = str(
                payload.get("stream_id")
                or f"{payload.get('vehicle_id') or payload.get('aircraftId') or 'unknown'}:"
                   f"{payload.get('camera_name') or payload.get('cameraName') or 'camera'}"
            )
            with self._lock:
                self.camera_streams[stream_id] = dict(payload)

        # Validate against the SDK ICD dataclass when available.  High-rate
        # telemetry uses a fast path because repeatedly constructing nested
        # dataclasses on the server's receive loop can delay unrelated control
        # messages.
        if mid not in HIGH_RATE_MIDS:
            try:
                parsed = parse_payload(mid, payload)
                payload = icd_to_dict(parsed) if parsed is not payload else payload
            except Exception as exc:
                logger.warning("ICD validation failed for %s: %s", mid, exc)

        if mid == "0002":
            self.registry.heartbeat(payload)

        self.registry.note_rx(role, mid, payload)

        rx_evt = TrafficEvent(
            ts=time.time(), mid=mid,
            name=str(MESSAGE_TABLE.get(mid, {}).get("name") or mid),
            kind="rx", proto="ws", peer_role=role,
            peer_ip="ws", peer_port=0, ok=True,
            note="ws", payload_preview=_preview(payload, mid=mid),
            full_payload=payload,
            extra_bytes=image_bytes,
        )
        self._append_traffic(rx_evt)

        # Registration handling
        for target_role in FORWARD_RULES.get(mid, []):
            if target_role == role:
                continue
            if mid == "4101" and target_role not in CAMERA_4101_FORWARD_ROLES:
                continue
            if target_role in OPTIONAL_FORWARD_ROLES:
                with self._lock:
                    optional_ws = self._ws_clients.get(target_role)
                if optional_ws is None:
                    continue
            self.push_to_role(target_role, mid, payload, image_bytes=image_bytes)

    # Registration handling
    def push_to_role(self, role: str, mid: str, payload: Dict[str, Any],
                     *, image_bytes: bytes = b"") -> Dict[str, Any]:
        """Internal helper."""
        if role == "sim_state":
            return self._push_to_local_sink(role, mid, payload)

        with self._lock:
            ws = self._ws_clients.get(role)

        if not self._should_forward(role, mid):
            return {"ok": False, "errors": ["rate limited"], "target": f"ws:{role}", "dropped": True}

        if ws is None:
            # Registration handling
            self.registry.note_tx(role, mid, payload)
            evt = TrafficEvent(
                ts=time.time(), mid=mid,
                name=str(MESSAGE_TABLE.get(mid, {}).get("name") or mid),
                kind="tx", proto="ws", peer_role=role,
                peer_ip="-", peer_port=0, ok=False,
                note="not connected", payload_preview=_preview(payload, mid=mid),
                full_payload=payload,
            )
            self._append_traffic(evt)
            return {"ok": False, "errors": ["not connected"], "target": f"ws:{role}"}

        # Registration handling
        msg: Dict[str, Any] = {"type": "message", "mid": mid, "from_role": "server",
                               "payload": payload}
        if image_bytes and mid == "4101":
            msg["image_b64"] = base64.b64encode(image_bytes).decode()
        ok = self._send_ws(ws, msg, role=role, mid=mid)
        errs: List[str] = [] if ok else ["WebSocket send failed"]
        self.registry.note_tx(role, mid, payload)

        # Registration handling
        if role == "visual":
            self.registry.heartbeat({"source": "DTAM_VISUAL"})

        evt = TrafficEvent(
            ts=time.time(), mid=mid,
            name=str(MESSAGE_TABLE.get(mid, {}).get("name") or mid),
            kind="tx", proto="ws", peer_role=role,
            peer_ip="ws", peer_port=0, ok=ok,
            note="" if ok else "ws send failed",
            payload_preview=_preview(payload, mid=mid),
            full_payload=payload,
        )
        # Latest-only drops are an internal backpressure mechanism.  Do not
        # flood the GUI traffic log with failed TX rows when a slow consumer is
        # intentionally being protected from stale high-rate frames.
        if ok or mid not in LATEST_ONLY_FORWARD_MIDS:
            self._append_traffic(evt)
        return {"ok": ok, "errors": errs, "target": f"ws:{role}"}

    def _should_forward(self, role: str, mid: str) -> bool:
        interval = float(FORWARD_MIN_INTERVAL_S.get(str(mid), 0.0) or 0.0)
        if interval <= 0.0:
            return True
        key = (str(role), str(mid))
        now = time.monotonic()
        with self._lock:
            last = float(self._last_forward_ts.get(key, 0.0) or 0.0)
            if now - last < interval:
                return False
            self._last_forward_ts[key] = now
            return True

    def _push_to_local_sink(self, role: str, mid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver SimulationState-targeted messages without a WebSocket client."""
        self.registry.note_tx(role, mid, payload)
        evt = TrafficEvent(
            ts=time.time(), mid=mid,
            name=str(MESSAGE_TABLE.get(mid, {}).get("name") or mid),
            kind="tx", proto="local", peer_role=role,
            peer_ip="local", peer_port=0, ok=True,
            note="local sink", payload_preview=_preview(payload, mid=mid),
            full_payload=payload,
        )
        self._append_traffic(evt)
        return {"ok": True, "errors": [], "target": f"local:{role}"}

    # Registration handling
    def snapshot(self) -> Dict[str, Any]:
        """Internal helper."""
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
            "camera_streams": dict(self.camera_streams),
            "transport": {
                "high_rate_mids": sorted(HIGH_RATE_MIDS),
                "camera_4101_forward_roles": sorted(CAMERA_4101_FORWARD_ROLES),
                "camera_4101_accept_fps": round(1.0 / CAMERA_4101_ACCEPT_MIN_INTERVAL_S, 3),
                "forward_rate_limits_s": dict(FORWARD_MIN_INTERVAL_S),
                "dropped_latest_send": {
                    f"{role}:{mid}": count
                    for (role, mid), count in sorted(self._dropped_latest_send.items())
                },
            },
            "traffic": traffic,
        }

    # Registration handling
    def update_module_endpoint(
        self,
        role: str,
        *,
        expected_source: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Internal helper."""
        module = self.registry.update_endpoint(
            role,
            expected_source=expected_source,
        )
        if module is None:
            return None
        return module.describe(self.registry.heartbeat_timeout_s)

    # Registration handling
    def _append_traffic(self, evt: TrafficEvent) -> None:
        stored_evt = _stored_traffic_event(evt)
        with self._lock:
            self._traffic.append(stored_evt)
        hook = self.on_event
        if hook is not None:
            try:
                hook(evt)
            except Exception:
                logger.exception("on_event hook raised")


def _camera_key(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "unknown:camera"
    vehicle_id = str(payload.get("vehicle_id") or payload.get("aircraftId") or "unknown")
    camera_name = str(payload.get("camera_name") or payload.get("cameraName") or "camera")
    return f"{vehicle_id}:{camera_name}"


def _stored_traffic_event(evt: TrafficEvent) -> TrafficEvent:
    """Return a lightweight event for the in-memory traffic ring buffer."""
    if evt.mid not in HIGH_RATE_MIDS and not evt.extra_bytes:
        return evt
    return TrafficEvent(
        ts=evt.ts,
        mid=evt.mid,
        name=evt.name,
        kind=evt.kind,
        proto=evt.proto,
        peer_role=evt.peer_role,
        peer_ip=evt.peer_ip,
        peer_port=evt.peer_port,
        ok=evt.ok,
        note=evt.note,
        payload_preview=evt.payload_preview,
        full_payload=None,
        extra_bytes=b"",
    )


def _preview(payload: Any, *, mid: str = "", limit: int = 240) -> Any:
    """Internal helper."""
    if not isinstance(payload, dict):
        return payload
    if mid == "4001":
        vehicle_ids = [
            str(key)
            for key, value in payload.items()
            if key != "timestamp" and isinstance(value, dict)
        ]
        return {
            "timestamp": payload.get("timestamp"),
            "vehicle_count": len(vehicle_ids),
            "vehicles": vehicle_ids[:8],
            "truncated": len(vehicle_ids) > 8,
        }
    if mid == "4101":
        return {
            key: value
            for key, value in payload.items()
            if key not in {"image_b64"}
        }
    if mid == "5001":
        return {
            key: payload.get(key)
            for key in (
                "timestamp", "aircraftId", "vehicleId", "roll", "pitch",
                "yaw", "throttle", "brake", "mode",
            )
            if key in payload
        } or payload
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except Exception:
        return None
    if len(text) <= limit:
        return payload
    return {"_truncated": text[:limit] + f"...({len(text) - limit}B more)"}


__all__ = ["ServerHub", "TrafficEvent"]
