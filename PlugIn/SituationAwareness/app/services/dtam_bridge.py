"""DTAM ICD bridge for Situation Awareness.

The original reference module pulled imagery/state directly from AirSim.  In the
current DTAM architecture this plug-in can instead consume the server-forwarded
ICD stream:

* MSG 4001: vehicle state used as the ownship state for risk metrics
* MSG 4101: camera frame bytes used as the vision-processing input
"""

from __future__ import annotations

import base64
import dataclasses
import json
import logging
import os
import queue
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

import cv2
import numpy as np


def _ensure_framework_paths() -> None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        sdk_root = parent / "DTAMSDK"
        if sdk_root.is_dir():
            root_path = str(parent)
            sdk_path = str(sdk_root)
            if root_path not in sys.path:
                sys.path.insert(0, root_path)
            if sdk_path not in sys.path:
                sys.path.insert(0, sdk_path)
            return


_ensure_framework_paths()

from dtam_client import SituationAwarenessModule, on_receive  # type: ignore  # noqa: E402


logger = logging.getLogger(__name__)


class SituationAwarenessIcdBridge(SituationAwarenessModule):
    """Subscribe to DTAM 4001/4101 and feed the local SA processing pipeline."""

    def __init__(
        self,
        *,
        frame_queue: queue.Queue,
        sensor_queue: queue.Queue,
        frame_callback: Optional[Callable[[np.ndarray], None]] = None,
        target_ip: str | None = None,
        ws_port: int | None = None,
    ) -> None:
        ip = target_ip or os.environ.get("DTAM_TARGET_IP") or "127.0.0.1"
        port = int(ws_port or os.environ.get("DTAM_WS_PORT") or 8096)
        self.frame_queue = frame_queue
        self.sensor_queue = sensor_queue
        self.frame_callback = frame_callback
        self.latest_vehicle_status: dict[str, Any] = {}
        self.latest_camera_meta: dict[str, Any] = {}
        self.latest_stream_descriptor: dict[str, Any] = {}
        self._stream_url: str = ""
        self._stream_thread: threading.Thread | None = None
        self._stream_stop = threading.Event()
        self._stream_lock = threading.RLock()
        self._stream_frames = 0
        self._stream_last_frame_ts = 0.0
        self._stream_last_error = ""
        self._auto_discover_thread: threading.Thread | None = None
        self._auto_discover_stop = threading.Event()
        super().__init__(
            server_url=f"ws://{ip}:{port}/ws/dtam",
            heartbeat=True,
        )
        if _env_bool("DTAM_SA_AUTO_MEDIA_STREAM", True):
            self._start_auto_media_discovery()

    @on_receive("4001")
    def on_vehicle_status(self, msg: Any) -> None:
        vehicles = getattr(msg, "vehicles", None)
        if not vehicles and isinstance(msg, dict):
            vehicles = {
                key: value
                for key, value in msg.items()
                if key != "timestamp" and isinstance(value, dict)
            }
        if not vehicles:
            return

        vehicle_id, vehicle_data = next(iter(dict(vehicles).items()))
        self.latest_vehicle_status[str(vehicle_id)] = vehicle_data
        state = self._to_airsim_like_state(vehicle_data)
        if state is not None:
            self._put_latest(self.sensor_queue, state)

    @on_receive("4101")
    def on_camera_image(self, msg: Any) -> None:
        payload = _message_to_dict(msg)
        if not isinstance(payload, dict):
            return
        self.latest_camera_meta = {
            key: value for key, value in payload.items() if key != "image_b64"
        }
        image_b64 = str(payload.get("image_b64") or "")
        if not image_b64:
            return
        try:
            image_bytes = base64.b64decode(image_b64)
            img_1d = np.frombuffer(image_bytes, dtype=np.uint8)
            frame = cv2.imdecode(img_1d, cv2.IMREAD_COLOR)
        except Exception as exc:
            logger.debug("Failed to decode 4101 image frame: %s", exc)
            return
        if frame is None or frame.size == 0:
            return
        self._put_latest(self.frame_queue, frame)
        if self.frame_callback:
            try:
                self.frame_callback(frame)
            except Exception:
                logger.exception("Situation Awareness frame callback failed")

    @on_receive("4102")
    def on_camera_stream_descriptor(self, msg: Any) -> None:
        """Open the direct MJPEG media-plane URL announced by Visualization.

        MSG 4101 is intentionally low-rate.  For continuous video, Visualization
        sends MSG 4102 with an HTTP MJPEG URL such as
        ``/api/media/stream?...``.  This plug-in consumes that URL directly and
        feeds frames into the same vision pipeline as 4101 snapshots.
        """

        payload = _message_to_dict(msg)
        if not isinstance(payload, dict):
            return
        self.latest_stream_descriptor = dict(payload)

        status = str(payload.get("status") or "available").strip().lower()
        stream_type = str(payload.get("stream_type") or payload.get("codec") or "").strip().lower()
        transport = str(payload.get("transport") or "").strip().lower()
        url = str(payload.get("url") or payload.get("embed_url") or "").strip()
        if status and status not in {"available", "active", "ok", "ready"}:
            return
        if not url:
            return
        if not (
            "mjpeg" in stream_type
            or "mjpeg" in str(payload.get("codec") or "").lower()
            or url.lower().startswith(("http://", "https://"))
        ):
            # Pixel Streaming/WebRTC descriptors are discovery-only for this
            # plug-in; the vision pipeline needs decoded image frames.
            return
        if transport and transport not in {"http", "https", "mjpeg"} and not url.lower().startswith(("http://", "https://")):
            return
        self._start_stream_reader(url)

    def _start_auto_media_discovery(self) -> None:
        with self._stream_lock:
            if self._auto_discover_thread and self._auto_discover_thread.is_alive():
                return
            self._auto_discover_stop.clear()
            self._auto_discover_thread = threading.Thread(
                target=self._auto_media_discovery_loop,
                name="dtam-sa-media-discovery",
                daemon=True,
            )
            self._auto_discover_thread.start()

    def _auto_media_discovery_loop(self) -> None:
        """Best-effort local discovery for Visualization's media-plane URL.

        This keeps SA usable even if nobody manually presses the Visualization
        "announce 4102" button.  The endpoint also publishes 4102 when
        ``announce=true`` so the IntegrationHub audit state stays consistent.
        """

        base_url = os.environ.get("DTAM_VISUAL_API_URL", "http://127.0.0.1:8097").strip().rstrip("/")
        if not base_url:
            return
        vehicle_id = os.environ.get("DTAM_SA_CAMERA_VEHICLE_ID", "UAM0001")
        vehicle_name = os.environ.get("DTAM_SA_CAMERA_VEHICLE_NAME", "")
        camera_name = os.environ.get("DTAM_SA_CAMERA_NAME", "front_center")
        image_type = os.environ.get("DTAM_SA_CAMERA_IMAGE_TYPE", "0")
        fps = os.environ.get("DTAM_SA_MEDIA_FPS", "15")
        quality = os.environ.get("DTAM_SA_MEDIA_QUALITY", "60")

        params = urllib.parse.urlencode(
            {
                "vehicle_id": vehicle_id,
                "vehicle_name": vehicle_name,
                "camera_name": camera_name,
                "image_type": image_type,
                "fps": fps,
                "quality": quality,
                "announce": "true",
            }
        )
        url = f"{base_url}/api/media/streams?{params}"

        # Retry while the current stream is not producing frames.  Once frames
        # are flowing, exit; later 4102 messages can still reconfigure it.
        while not self._auto_discover_stop.is_set():
            if self._stream_frames > 0 and time.time() - self._stream_last_frame_ts < 5.0:
                return
            try:
                with urllib.request.urlopen(url, timeout=4.0) as resp:
                    raw = resp.read(512 * 1024)
                data = json.loads(raw.decode("utf-8", errors="replace"))
                streams = data.get("streams") if isinstance(data, dict) else None
                if streams:
                    descriptor = dict(streams[0])
                    self.on_camera_stream_descriptor(descriptor)
                    # Give the reader time to connect before another announce.
                    if self._auto_discover_stop.wait(5.0):
                        return
                    continue
            except Exception as exc:
                with self._stream_lock:
                    self._stream_last_error = f"media discovery: {type(exc).__name__}: {exc}"
            if self._auto_discover_stop.wait(5.0):
                return

    def _start_stream_reader(self, url: str) -> None:
        with self._stream_lock:
            if url == self._stream_url and self._stream_thread and self._stream_thread.is_alive():
                return
            self._stop_stream_reader_locked(join=False)
            self._stream_url = url
            self._stream_stop = threading.Event()
            self._stream_thread = threading.Thread(
                target=self._stream_reader_loop,
                args=(url, self._stream_stop),
                name="dtam-sa-mjpeg-reader",
                daemon=True,
            )
            self._stream_thread.start()

    def _stop_stream_reader_locked(self, *, join: bool = True) -> None:
        thread = self._stream_thread
        if thread is None:
            return
        self._stream_stop.set()
        self._stream_thread = None
        if join and thread.is_alive():
            thread.join(timeout=2.0)

    def _stream_reader_loop(self, url: str, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                self._read_mjpeg_stream(url, stop_event)
            except Exception as exc:
                with self._stream_lock:
                    self._stream_last_error = f"{type(exc).__name__}: {exc}"
            if stop_event.wait(1.5):
                break

    def _read_mjpeg_stream(self, url: str, stop_event: threading.Event) -> None:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "DTAM-SituationAwareness/1.0",
                "Accept": "multipart/x-mixed-replace,image/jpeg,*/*",
            },
        )
        with urllib.request.urlopen(request, timeout=10.0) as resp:
            buffer = bytearray()
            while not stop_event.is_set():
                chunk = resp.read(16384)
                if not chunk:
                    raise EOFError("MJPEG stream ended")
                buffer.extend(chunk)
                # Keep memory bounded if a malformed stream never yields EOI.
                if len(buffer) > 4 * 1024 * 1024:
                    del buffer[:-1024 * 1024]

                while True:
                    start = buffer.find(b"\xff\xd8")
                    if start < 0:
                        if len(buffer) > 4096:
                            del buffer[:-2048]
                        break
                    end = buffer.find(b"\xff\xd9", start + 2)
                    if end < 0:
                        if start > 0:
                            del buffer[:start]
                        break
                    jpg = bytes(buffer[start : end + 2])
                    del buffer[: end + 2]
                    frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is None or frame.size == 0:
                        continue
                    self._handle_frame(frame, source="4102")

    def _handle_frame(self, frame: np.ndarray, *, source: str) -> None:
        self._put_latest(self.frame_queue, frame)
        with self._stream_lock:
            if source == "4102":
                self._stream_frames += 1
                self._stream_last_frame_ts = time.time()
                self._stream_last_error = ""
        if self.frame_callback:
            try:
                self.frame_callback(frame)
            except Exception:
                logger.exception("Situation Awareness frame callback failed")

    def _put_latest(self, target_queue: queue.Queue, value: Any) -> None:
        try:
            target_queue.put(value, block=False)
            return
        except queue.Full:
            pass
        try:
            target_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            target_queue.put(value, block=False)
        except queue.Full:
            pass

    def status(self) -> dict[str, Any]:
        base = super().status()
        with self._stream_lock:
            base["camera_stream"] = {
                "url": self._stream_url,
                "running": bool(self._stream_thread and self._stream_thread.is_alive()),
                "frames": self._stream_frames,
                "last_frame_ts": self._stream_last_frame_ts,
                "last_error": self._stream_last_error,
                "descriptor": dict(self.latest_stream_descriptor),
            }
            if self.latest_camera_meta:
                base["latest_camera_meta"] = dict(self.latest_camera_meta)
        return base

    def close(self) -> None:
        self._auto_discover_stop.set()
        with self._stream_lock:
            self._stop_stream_reader_locked(join=True)
        thread = self._auto_discover_thread
        self._auto_discover_thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        super().close()

    def _to_airsim_like_state(self, vehicle_data: Any) -> Any:
        """Convert MSG 4001 VehicleData into the minimal shape expected by the
        reference risk-assessment thread.
        """

        def get(obj: Any, name: str, default: float = 0.0) -> float:
            if isinstance(obj, dict):
                return float(obj.get(name, default) or default)
            return float(getattr(obj, name, default) or default)

        position = getattr(vehicle_data, "position", None)
        gps = getattr(vehicle_data, "gps", None)
        if isinstance(vehicle_data, dict):
            position = vehicle_data.get("position") or {}
            gps = vehicle_data.get("gps") or {}
        if position is None:
            return None
        return SimpleNamespace(
            kinematics_estimated=SimpleNamespace(
                position=SimpleNamespace(
                    x_val=get(position, "north"),
                    y_val=get(position, "east"),
                    z_val=get(position, "down"),
                ),
                linear_velocity=SimpleNamespace(
                    x_val=get(gps, "velocity_north"),
                    y_val=get(gps, "velocity_east"),
                    z_val=get(gps, "velocity_down"),
                ),
            )
        )


def _message_to_dict(msg: Any) -> dict[str, Any]:
    if isinstance(msg, dict):
        return dict(msg)
    if dataclasses.is_dataclass(msg) and not isinstance(msg, type):
        return dataclasses.asdict(msg)
    if hasattr(msg, "to_wire"):
        try:
            data = msg.to_wire()
            if isinstance(data, dict):
                return dict(data)
        except Exception:
            pass
    if hasattr(msg, "__dict__"):
        return dict(getattr(msg, "__dict__", {}) or {})
    return {}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on", "enable", "enabled"}


__all__ = ["SituationAwarenessIcdBridge"]
