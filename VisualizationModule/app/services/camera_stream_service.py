"""Low-latency camera stream producer/cache for direct MJPEG streaming.

The important rule is: browsers must not call AirSim directly per client.
One background producer captures the requested camera, stores only the newest
JPEG frame in memory, and any number of HTTP MJPEG consumers read that latest
frame.  Old frames are deliberately dropped to keep latency low.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, Optional, Tuple


CaptureFn = Callable[..., Tuple[bytes, Dict[str, Any]]]


@dataclass(frozen=True)
class CameraStreamSpec:
    aircraft_id: str = "UAM0001"
    vehicle_name: str = ""
    camera_name: str = "front_center"
    image_type: int = 0
    fps: float = 20.0
    quality: int = 60

    def key(self) -> str:
        """Return the producer key for one physical camera source.

        ``fps`` and ``quality`` are intentionally excluded.  They are capture
        parameters, not a different source.  Keeping them in the key made the
        same AirSim/VPO camera spawn multiple background producers whenever two
        clients requested slightly different frame rates or JPEG qualities.
        The first producer keeps its configured fps/quality and all consumers
        share its latest-frame cache.
        """
        return "|".join(
            [
                self.aircraft_id or "UAM0001",
                self.vehicle_name or "",
                self.camera_name or "front_center",
                str(int(self.image_type or 0)),
            ]
        )


@dataclass
class CameraFrame:
    sequence: int
    timestamp: float
    frame: bytes
    meta: Dict[str, Any]
    capture_ms: float


class CameraStreamWorker:
    """Background producer for one physical camera source."""

    def __init__(
        self,
        spec: CameraStreamSpec,
        capture_fn: CaptureFn,
        *,
        idle_timeout_s: float = 20.0,
    ) -> None:
        self.spec = spec
        self._capture_fn = capture_fn
        self._idle_timeout_s = max(2.0, float(idle_timeout_s))
        self._condition = threading.Condition()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._latest: Optional[CameraFrame] = None
        self._sequence = 0
        self._started_at = 0.0
        self._last_touch = time.time()
        self._last_frame_ts = 0.0
        self._last_error = ""
        self._last_meta: Dict[str, Any] = {}
        self._frame_times: Deque[float] = deque(maxlen=120)
        self._capture_times_ms: Deque[float] = deque(maxlen=120)
        self._frames = 0
        self._errors = 0
        self._empty_frames = 0
        self._capture_exceptions = 0
        self._consecutive_errors = 0
        self._overrun_count = 0
        self._last_sleep_s = 0.0
        self._last_backoff_s = 0.0
        self._consumers = 0
        self._stopped = True

    def start(self) -> "CameraStreamWorker":
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                self._last_touch = time.time()
                return self
            self._stop_event.clear()
            self._started_at = time.time()
            self._last_touch = self._started_at
            self._stopped = False
            self._thread = threading.Thread(
                target=self._run,
                name=f"dtam-camera-stream-{self.spec.camera_name}",
                daemon=True,
            )
            self._thread.start()
            return self

    def stop(self, *, join_timeout_s: float = 1.0) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, float(join_timeout_s)))

    def acquire_consumer(self) -> None:
        with self._condition:
            self._consumers += 1
            self._last_touch = time.time()

    def release_consumer(self) -> None:
        with self._condition:
            self._consumers = max(0, self._consumers - 1)
            self._last_touch = time.time()

    def touch(self) -> None:
        with self._condition:
            self._last_touch = time.time()

    def is_stopped(self) -> bool:
        with self._condition:
            return bool(self._stopped)

    def wait_for_frame(self, after_sequence: int = 0, timeout_s: float = 1.0) -> Optional[CameraFrame]:
        """Return the newest frame once its sequence is newer than after_sequence."""
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        with self._condition:
            self._last_touch = time.time()
            while not self._stop_event.is_set():
                latest = self._latest
                if latest is not None and latest.sequence != int(after_sequence or 0):
                    return latest
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(timeout=min(remaining, 0.25))
            return self._latest

    def stats(self) -> Dict[str, Any]:
        with self._condition:
            actual_fps = 0.0
            if len(self._frame_times) >= 2:
                span = self._frame_times[-1] - self._frame_times[0]
                if span > 0:
                    actual_fps = (len(self._frame_times) - 1) / span
            capture_values = list(self._capture_times_ms)
            avg_capture_ms = round(sum(capture_values) / len(capture_values), 3) if capture_values else 0.0
            max_capture_ms = round(max(capture_values), 3) if capture_values else 0.0
            if capture_values:
                sorted_values = sorted(capture_values)
                p95_index = min(len(sorted_values) - 1, int(round((len(sorted_values) - 1) * 0.95)))
                p95_capture_ms = round(sorted_values[p95_index], 3)
            else:
                p95_capture_ms = 0.0
            latest = self._latest
            return {
                "key": self.spec.key(),
                "aircraft_id": self.spec.aircraft_id,
                "vehicle_name": self.spec.vehicle_name,
                "camera_name": self.spec.camera_name,
                "image_type": self.spec.image_type,
                "target_fps": self.spec.fps,
                "actual_fps": round(actual_fps, 2),
                "quality": self.spec.quality,
                "frames": self._frames,
                "errors": self._errors,
                "empty_frames": self._empty_frames,
                "capture_exceptions": self._capture_exceptions,
                "consecutive_errors": self._consecutive_errors,
                "overrun_count": self._overrun_count,
                "consumers": self._consumers,
                "started_at": self._started_at,
                "uptime_s": round(time.time() - self._started_at, 3) if self._started_at else 0.0,
                "last_frame_ts": self._last_frame_ts,
                "last_error": self._last_error,
                "stopped": self._stopped,
                "latest_sequence": latest.sequence if latest else 0,
                "latest_bytes_len": len(latest.frame) if latest else 0,
                "latest_capture_ms": round(latest.capture_ms, 3) if latest else 0.0,
                "avg_capture_ms": avg_capture_ms,
                "max_capture_ms": max_capture_ms,
                "p95_capture_ms": p95_capture_ms,
                "last_sleep_ms": round(float(self._last_sleep_s) * 1000.0, 3),
                "last_backoff_ms": round(float(self._last_backoff_s) * 1000.0, 3),
                "latest_meta": dict(self._last_meta or {}),
            }

    def _run(self) -> None:
        period_s = 1.0 / max(0.2, min(30.0, float(self.spec.fps or 20.0)))
        try:
            while not self._stop_event.is_set():
                with self._condition:
                    idle_for = time.time() - self._last_touch
                    consumers = self._consumers
                if consumers <= 0 and idle_for > self._idle_timeout_s:
                    break

                start_perf = time.perf_counter()
                try:
                    frame, meta = self._capture_fn(
                        aircraft_id=self.spec.aircraft_id,
                        camera_name=self.spec.camera_name,
                        image_type=self.spec.image_type,
                        vehicle_name=self.spec.vehicle_name,
                        quality=self.spec.quality,
                    )
                except Exception as exc:  # pragma: no cover - defensive runtime guard
                    frame = b""
                    meta = {"error": f"{type(exc).__name__}: {exc}"}
                    with self._condition:
                        self._capture_exceptions += 1
                capture_ms = (time.perf_counter() - start_perf) * 1000.0
                now = time.time()

                with self._condition:
                    self._capture_times_ms.append(capture_ms)
                    if frame:
                        self._sequence += 1
                        frame_meta = dict(meta or {})
                        frame_meta["producer_target_fps"] = self.spec.fps
                        frame_meta["producer_quality"] = self.spec.quality
                        frame_meta["producer_capture_ms"] = capture_ms
                        self._latest = CameraFrame(
                            sequence=self._sequence,
                            timestamp=now,
                            frame=bytes(frame),
                            meta=frame_meta,
                            capture_ms=capture_ms,
                        )
                        self._frames += 1
                        self._last_frame_ts = now
                        self._last_error = ""
                        self._consecutive_errors = 0
                        self._last_meta = frame_meta
                        self._frame_times.append(now)
                        self._condition.notify_all()
                    else:
                        self._errors += 1
                        self._empty_frames += 1
                        self._consecutive_errors += 1
                        self._last_error = str((meta or {}).get("error") or "empty frame")
                        self._last_meta = dict(meta or {})

                elapsed_s = time.perf_counter() - start_perf
                sleep_s = max(0.0, period_s - elapsed_s)
                backoff_s = self._error_backoff_s()
                if backoff_s > sleep_s:
                    sleep_s = backoff_s
                with self._condition:
                    self._last_sleep_s = sleep_s
                    self._last_backoff_s = backoff_s
                    if elapsed_s > period_s:
                        self._overrun_count += 1
                if self._stop_event.wait(timeout=sleep_s):
                    break
        finally:
            with self._condition:
                self._stopped = True
                self._condition.notify_all()

    def _error_backoff_s(self) -> float:
        """Slow failing producers so unavailable RPCs do not spin at stream FPS."""
        with self._condition:
            consecutive_errors = int(self._consecutive_errors)
            last_error = str(self._last_error or "").lower()
        if consecutive_errors <= 3:
            return 0.0

        # Missing/disabled camera paths are not transient per-frame events.  Keep
        # retrying in case DT World finishes loading, but avoid hammering AirSim.
        if any(
            token in last_error
            for token in (
                "not connected",
                "unavailable",
                "not found",
                "unknown",
                "missing",
                "disabled",
                "empty frame",
            )
        ):
            return min(5.0, 0.5 + (consecutive_errors - 3) * 0.25)

        return min(2.0, (consecutive_errors - 3) * 0.1)


class CameraStreamService:
    """Registry of camera stream workers."""

    def __init__(self, capture_fn: CaptureFn, *, idle_timeout_s: float = 20.0) -> None:
        self._capture_fn = capture_fn
        self._idle_timeout_s = max(2.0, float(idle_timeout_s))
        self._lock = threading.RLock()
        self._workers: Dict[str, CameraStreamWorker] = {}

    def ensure_stream(self, spec: CameraStreamSpec) -> CameraStreamWorker:
        key = spec.key()
        with self._lock:
            worker = self._workers.get(key)
            if worker is None or worker.is_stopped():
                worker = CameraStreamWorker(
                    spec,
                    self._capture_fn,
                    idle_timeout_s=self._idle_timeout_s,
                )
                self._workers[key] = worker
                worker.start()
            else:
                worker.touch()
            return worker

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._workers),
                "streams": [worker.stats() for worker in self._workers.values()],
            }

    def stop_all(self) -> None:
        with self._lock:
            workers = list(self._workers.values())
            self._workers.clear()
        for worker in workers:
            worker.stop(join_timeout_s=1.0)
