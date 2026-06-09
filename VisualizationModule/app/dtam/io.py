"""DTAM ICD 입출력 레이어 using the ServerRevision WebSocket SDK."""

from __future__ import annotations

import dataclasses
import logging
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

_FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
_SDK_ROOT = _FRAMEWORK_ROOT / "DTAMSDK"
if _SDK_ROOT.exists():
    sdk_root_text = str(_SDK_ROOT)
    if sdk_root_text not in sys.path:
        sys.path.insert(0, sdk_root_text)

from dtam_client import VisualModule  # type: ignore
from dtam_client.schema import parse_payload, to_dict as icd_to_dict  # type: ignore

from ..config import DtamEndpoint, INBOUND_MIDS, MODULE_SOURCE_NAME, OUTBOUND_MIDS

logger = logging.getLogger(__name__)


def _iso_ts() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass
class IoStats:
    rx_counts: Dict[str, int] = field(default_factory=dict)
    tx_counts: Dict[str, int] = field(default_factory=dict)
    last_rx_ts: Dict[str, float] = field(default_factory=dict)
    last_tx_ts: Dict[str, float] = field(default_factory=dict)
    last_rx_payload: Dict[str, Any] = field(default_factory=dict)
    last_error: str = ""
    running: bool = False
    rx_hz: Dict[str, float] = field(default_factory=dict)

    def note_rx(self, mid: str, payload: Any, recent_ts_buffer: Dict[str, Deque[float]]) -> None:
        now = time.time()
        self.rx_counts[mid] = int(self.rx_counts.get(mid, 0)) + 1
        self.last_rx_ts[mid] = now
        if isinstance(payload, dict):
            self.last_rx_payload[mid] = payload
        buf = recent_ts_buffer.setdefault(mid, deque(maxlen=32))
        buf.append(now)
        window = [t for t in buf if now - t < 5.0]
        if len(window) >= 2:
            span = max(1e-3, window[-1] - window[0])
            self.rx_hz[mid] = round((len(window) - 1) / span, 3)
        else:
            self.rx_hz[mid] = 0.0

    def note_tx(self, mid: str, ok: bool = True, error: str = "") -> None:
        self.tx_counts[mid] = int(self.tx_counts.get(mid, 0)) + 1
        self.last_tx_ts[mid] = time.time()
        if ok:
            self.last_error = ""
        elif error:
            self.last_error = error

    def to_dict(self, *, include_payload: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if include_payload:
            payload["last_rx_payload"] = dict(self.last_rx_payload)
        return {
            "running": self.running,
            "rx_counts": dict(self.rx_counts),
            "tx_counts": dict(self.tx_counts),
            "last_rx_ts": dict(self.last_rx_ts),
            "last_tx_ts": dict(self.last_tx_ts),
            **payload,
            "rx_hz": dict(self.rx_hz),
            "last_error": self.last_error,
            "inbound_mids": list(INBOUND_MIDS),
            "outbound_mids": list(OUTBOUND_MIDS),
            "transport": "ws",
        }


RxCallback = Callable[[str, Dict[str, Any], Any], None]


class _VisualBridgeModule(VisualModule):
    def __init__(self, *, server_url: str, dispatch: Callable[[str, Any], None]) -> None:
        self._dispatch_to_manager = dispatch
        super().__init__(server_url=server_url, heartbeat=True)

    def on_common_time_info(self, msg: Any) -> None:
        self._dispatch_to_manager("0003", msg)

    def on_simulation_setup(self, msg: Any) -> None:
        self._dispatch_to_manager("1002", msg)

    def on_scenario_setup(self, msg: Any) -> None:
        self._dispatch_to_manager("1003", msg)

    def on_dtam_execute(self, msg: Any) -> None:
        self._dispatch_to_manager("2002", msg)

    def on_scheduled_flight(self, msg: Any) -> None:
        self._dispatch_to_manager("3001", msg)

    def on_vehicle_status(self, msg: Any) -> None:
        self._dispatch_to_manager("4001", msg)

    def on_camera_control_command(self, msg: Any) -> None:
        self._dispatch_to_manager("5002", msg)

    def on_abnormal_situation_command(self, msg: Any) -> None:
        self._dispatch_to_manager("5003", msg)


class DtamIO:
    def __init__(self, endpoint: DtamEndpoint) -> None:
        self._lock = threading.RLock()
        self._endpoint = endpoint
        self._module: Optional[_VisualBridgeModule] = None
        self._stats = IoStats()
        self._rx_buffers: Dict[str, Deque[float]] = {}
        self._on_rx: Optional[RxCallback] = None

    def reconfigure(
        self,
        *,
        server_ip: Optional[str] = None,
        server_port: Optional[int] = None,
    ) -> DtamEndpoint:
        with self._lock:
            was_running = self._stats.running
            if was_running:
                self._stop_locked()
            if server_ip is not None:
                self._endpoint.server_ip = str(server_ip)
            if server_port is not None:
                self._endpoint.server_port = int(server_port)
            if was_running:
                self._start_locked()
            return DtamEndpoint(**self._endpoint.__dict__)

    def start(self, on_rx: RxCallback) -> None:
        with self._lock:
            self._on_rx = on_rx
            self._start_locked()

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def _start_locked(self) -> None:
        if self._module is not None:
            return
        url = f"ws://{self._endpoint.server_ip}:{self._endpoint.server_port}/ws/dtam"
        try:
            self._module = _VisualBridgeModule(server_url=url, dispatch=self._dispatch_rx)
            self._stats.running = True
            self._stats.last_error = ""
        except Exception as exc:
            self._module = None
            self._stats.running = False
            self._stats.last_error = f"{type(exc).__name__}: {exc}"
            logger.exception("visual module SDK start failed")

    def _stop_locked(self) -> None:
        module = self._module
        self._module = None
        self._stats.running = False
        if module is not None:
            try:
                module.close()
            except Exception:
                logger.exception("visual module close failed")

    def _dispatch_rx(self, mid: str, result: Any) -> None:
        payload = _result_to_dict(result)
        with self._lock:
            self._stats.note_rx(mid, payload, self._rx_buffers)
        hook = self._on_rx
        if hook is not None:
            try:
                hook(mid, payload, result)
            except Exception:
                logger.exception("on_rx callback raised for %s", mid)

    def send_module_status(self, status_code: int = 1) -> Dict[str, Any]:
        payload = {
            "timestamp": _iso_ts(),
            "source": MODULE_SOURCE_NAME,
            "status": int(status_code),
        }
        return self._send("0002", payload)

    def send_camera_image(self, header: Dict[str, Any], image_bytes: bytes) -> Dict[str, Any]:
        return self._send("4101", header, image_bytes=image_bytes)

    def send_camera_stream_descriptor(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._send("4102", payload)

    def send_vehicle_collision_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._send("4103", payload)

    def _send(
        self,
        mid: str,
        payload: Dict[str, Any],
        *,
        image_bytes: bytes = b"",
    ) -> Dict[str, Any]:
        with self._lock:
            module = self._module
        if module is None:
            self._stats.note_tx(mid, ok=False, error="client not initialised")
            return {"ok": False, "error": "client not initialised", "mid": mid}
        try:
            parsed = parse_payload(mid, payload)
            wire_payload = icd_to_dict(parsed)
            if image_bytes:
                ok = bool(module._ws.send(mid, wire_payload, image_bytes=image_bytes))
            else:
                ok = bool(module.send(parsed))
            self._stats.note_tx(mid, ok=ok, error="" if ok else "WebSocket send failed")
            return {"ok": ok, "mid": mid, "target": module.server_url, "errors": [] if ok else ["WebSocket send failed"]}
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            self._stats.note_tx(mid, ok=False, error=msg)
            return {"ok": False, "error": msg, "mid": mid}

    def endpoint(self) -> DtamEndpoint:
        with self._lock:
            return DtamEndpoint(**self._endpoint.__dict__)

    def stats(self, *, include_payload: bool = True) -> Dict[str, Any]:
        with self._lock:
            return self._stats.to_dict(include_payload=include_payload)

    def close(self) -> None:
        self.stop()


def _result_to_dict(result: Any) -> Dict[str, Any]:
    if result is None:
        return {}
    if isinstance(result, dict):
        return dict(result)
    if hasattr(result, "to_wire"):
        try:
            data = result.to_wire()
            if isinstance(data, dict):
                return dict(data)
        except Exception:
            pass
    if hasattr(result, "raw") and isinstance(result.raw, dict):
        return dict(result.raw)
    if hasattr(result, "to_dict"):
        try:
            data = result.to_dict()
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        return dataclasses.asdict(result)
    return {"_repr": repr(result)}


__all__ = ["DtamIO", "IoStats"]
