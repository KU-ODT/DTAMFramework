"""Central hub for the Visualization Manager.

- Converts inbound ICD messages from DtamIO into AirSimBridge method calls.
- Runs periodic tasks: 0002 Module Status at 1 Hz and optional 4101 Camera Image.
- Provides a public API for REST/WebSocket status queries and manual controls.

Data flow:
  Other modules -> DTAMSDK socket -> DtamIO -> Manager -> AirSimBridge -> AirSim RPC
  AirSim / periodic tasks -> Manager -> DtamIO -> DTAMSDK socket -> other modules
"""
from __future__ import annotations

import json
import logging
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional
from urllib.parse import urlencode
from urllib.parse import urlparse

from ..adapters.airsim import AirSimBridge
from ..config import FRAMEWORK_ROOT, UNREAL_ROOT, VMConfig, rendering_preset_defaults, save_config
from ..dtam.io import DtamIO
from .camera_stream_service import CameraStreamService, CameraStreamSpec, CameraStreamWorker

logger = logging.getLogger(__name__)

MAX_EVENTS = 400
MISSION_GUIDE_PATH = UNREAL_ROOT / "Environments" / "DTAMVisualization" / "Data" / "mission_guides.json"
MISSION_GUIDE_TOGGLE_VK = 0x55  # U
DEFAULT_DIRECT_CAMERA_WIDTH = 640
DEFAULT_DIRECT_CAMERA_HEIGHT = 360
VEHICLE_STATUS_APPLY_HZ = 30.0
VEHICLE_STATUS_EVENT_PERIOD_S = 0.5
ICD_CAMERA_SNAPSHOT_MAX_HZ = 2.0
UNREAL_DEFAULT_MAP = "/AirSim/KP2A/KP2A_Map"


@dataclass
class HubEvent:
    ts: float
    kind: str            # "rx" | "tx" | "translate" | "airsim" | "error"
    mid: str
    summary: str
    detail: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "kind": self.kind,
            "mid": self.mid,
            "summary": self.summary,
            "detail": self.detail,
        }


def _hub_event(
    *,
    kind: str,
    mid: str,
    summary: str,
    detail: Optional[Dict[str, Any]] = None,
    ts: Optional[float] = None,
) -> HubEvent:
    """Build a complete Visualization event record.

    A few migration-era call sites created ``HubEvent`` with only summary/detail.
    That crashed the VM periodic thread and produced callback errors for every
    inbound 4001 frame.  Keeping construction centralized prevents that class
    of bug from coming back.
    """
    return HubEvent(
        ts=float(ts if ts is not None else time.time()),
        kind=str(kind or ""),
        mid=str(mid or ""),
        summary=str(summary or ""),
        detail=dict(detail or {}),
    )


def _duration_stats_ms(samples: Deque[float]) -> Dict[str, float]:
    values = [float(item) * 1000.0 for item in list(samples)]
    if not values:
        return {"avg_ms": 0.0, "max_ms": 0.0, "min_ms": 0.0, "samples": 0}
    return {
        "avg_ms": round(sum(values) / len(values), 3),
        "max_ms": round(max(values), 3),
        "min_ms": round(min(values), 3),
        "samples": len(values),
    }


def _effective_hz(timestamps: Deque[float]) -> float:
    values = [float(item) for item in list(timestamps)]
    if len(values) < 2:
        return 0.0
    span = max(0.0, values[-1] - values[0])
    if span <= 0.0:
        return 0.0
    return round((len(values) - 1) / span, 2)


def _iso_timestamp_utc(now: Optional[float] = None) -> str:
    dt = datetime.fromtimestamp(
        time.time() if now is None else float(now),
        tz=timezone.utc,
    )
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _pose_feedback_to_4103_payload(
    feedback: Dict[str, Any],
    *,
    default_recommended_action: str = "none",
) -> Optional[Dict[str, Any]]:
    """Convert a blocked sweep/pose-feedback diagnostic into a 4103 event.

    Some packaged Unreal/AirSim vehicle pawns report blocked movement via
    ``simSetVehiclePose(..., ignore_collision=False)``/pose mismatch while
    ``simGetCollisionInfo`` remains empty because the actor root is not the
    collider component.  This diagnostic is useful for logs, but is noisy when
    the world/vehicle origin is still settling.  Therefore it defaults to a
    record-only 4103 action and is only sent to the server when explicitly
    enabled in config/runtime settings.
    """
    if not isinstance(feedback, dict) or not feedback.get("blocked_suspected"):
        return None
    aircraft_id = str(feedback.get("aircraftId") or "").strip() or "UNKNOWN"
    vehicle_name = str(feedback.get("airsimVehicleName") or "").strip()
    now = time.time()
    collision_time_nanos = int(now * 1_000_000_000)
    error_m = float(feedback.get("error_m") or 0.0)
    threshold_m = float(feedback.get("threshold_m") or 0.0)
    severity = "critical" if error_m >= max(2.0, threshold_m * 3.0) else "warning"
    event_id = f"COL-{aircraft_id}-POSE-{collision_time_nanos}"
    return {
        "message_id": 4103,
        "message_name": "Vehicle Collision Event",
        "timestamp": _iso_timestamp_utc(now),
        "eventId": event_id,
        "aircraftId": aircraft_id,
        "airsimVehicleName": vehicle_name,
        "hasCollided": True,
        "objectName": "movement-blocked",
        "objectId": -1,
        "positionNed": dict(feedback.get("actual") or {}),
        "impactPointNed": dict(feedback.get("actual") or {}),
        "normalNed": {},
        "penetrationDepth": max(0.0, error_m - max(0.0, threshold_m)),
        "collisionTimeNanos": collision_time_nanos,
        "impactSpeedMps": 0.0,
        "severity": severity,
        "recommendedAction": str(default_recommended_action or "none"),
        "source": "airsim.pose_feedback",
        "metadata": {
            # Stable key: emit at most once per dedup window while blocked.
            "dedupKey": f"{aircraft_id}|pose-feedback|movement-blocked",
            "poseFeedback": True,
            "requested": dict(feedback.get("requested") or {}),
            "actual": dict(feedback.get("actual") or {}),
            "error_m": error_m,
            "threshold_m": threshold_m,
        },
    }


class VisualizationManager:
    def __init__(self, config: VMConfig) -> None:
        self._lock = threading.RLock()
        self._config = config
        self._bridge = AirSimBridge(config.airsim)
        self._io = DtamIO(config.dtam)
        self._events: Deque[HubEvent] = deque(maxlen=MAX_EVENTS)
        self._stop_event = threading.Event()
        self._periodic_thread: Optional[threading.Thread] = None
        self._vehicle_status_thread: Optional[threading.Thread] = None
        self._collision_thread: Optional[threading.Thread] = None
        self._vehicle_status_event = threading.Event()
        self._vehicle_status_lock = threading.RLock()
        self._pending_vehicle_status: Optional[Dict[str, Any]] = None
        self._vehicle_status_rx_count = 0
        self._vehicle_status_applied_count = 0
        self._vehicle_status_dropped_count = 0
        self._vehicle_status_last_apply_s = 0.0
        self._vehicle_status_last_error = ""
        self._vehicle_status_last_target_hz = float(config.runtime_optimization.vehicle_status_apply_hz)
        self._vehicle_status_last_vehicle_count = 0
        self._collision_lock = threading.RLock()
        self._collision_dedup: Dict[str, float] = {}
        self._collision_poll_count = 0
        self._collision_event_count = 0
        self._collision_duplicate_count = 0
        self._collision_tx_count = 0
        self._collision_tx_ok_count = 0
        self._collision_last_poll_s = 0.0
        self._collision_last_error = ""
        self._collision_last_event: Optional[Dict[str, Any]] = None
        self._collision_last_send: Dict[str, Any] = {}
        self._collision_last_error_emit_ts = 0.0
        history_size = max(10, min(5000, int(getattr(config.metrics, "history_size", 120) or 120)))
        self._vehicle_status_apply_samples: Deque[float] = deque(maxlen=history_size)
        self._vehicle_status_apply_timestamps: Deque[float] = deque(maxlen=history_size)
        self._collision_poll_samples: Deque[float] = deque(maxlen=history_size)
        self._collision_poll_timestamps: Deque[float] = deque(maxlen=history_size)
        self._collision_last_targets_count = 0
        self._camera_snapshot_lock = threading.RLock()
        self._camera_snapshot_count = 0
        self._camera_snapshot_error_count = 0
        self._camera_snapshot_tx_count = 0
        self._camera_snapshot_tx_ok_count = 0
        self._camera_snapshot_capture_samples: Deque[float] = deque(maxlen=history_size)
        self._camera_snapshot_send_samples: Deque[float] = deque(maxlen=history_size)
        self._camera_snapshot_timestamps: Deque[float] = deque(maxlen=history_size)
        self._camera_snapshot_last_meta: Dict[str, Any] = {}
        self._metrics_last_log_ts = 0.0
        self._metrics_log_path = self._resolve_metrics_log_path()
        self._started_at = 0.0
        self.on_event: Optional[Callable[[HubEvent], None]] = None
        self._streaming = config.streaming
        self._unreal_proc: Optional[subprocess.Popen[bytes]] = None
        self._pixel_server_proc: Optional[subprocess.Popen[bytes]] = None
        self._last_unreal_pixel_streaming = False
        self._camera_streams = CameraStreamService(self.capture_direct_camera_frame, idle_timeout_s=20.0)
        self._vpo_camera_streams = CameraStreamService(self.capture_vpo_camera_frame, idle_timeout_s=15.0)
        # Unreal renders mission guides directly from mission_guides.json.
        # Keep AirSim marker output disabled unless explicitly requested for debugging.
        self._mission_guides_visible = False
        self._mission_guide_key_down = False
        self._last_mission_guide_toggle_ts = 0.0
    # -----------------------------------------------------------------------------
    def start(self) -> None:
        with self._lock:
            if self._periodic_thread is not None:
                return
            self._started_at = time.time()
            self._stop_event.clear()
            self._vehicle_status_event.clear()
            # AirSim is launched later by the Operations Console. Keep the VM
            # HTTP server ready first; /api/airsim/connect performs RPC connect.
            self._vehicle_status_thread = threading.Thread(
                target=self._vehicle_status_loop,
                name="dtam-vm-4001-latest",
                daemon=True,
            )
            self._vehicle_status_thread.start()
            if self._config.collision.enabled:
                self._collision_thread = threading.Thread(
                    target=self._collision_loop,
                    name="dtam-vm-collision",
                    daemon=True,
                )
                self._collision_thread.start()
            try:
                self._io.start(on_rx=self._on_rx)
            except Exception as exc:
                logger.exception("DTAM SDK I/O start failed; VM will continue in degraded mode")
                try:
                    with self._io._lock:  # type: ignore[attr-defined]
                        self._io._stats.running = False  # type: ignore[attr-defined]
                        self._io._stats.last_error = f"{type(exc).__name__}: {exc}"  # type: ignore[attr-defined]
                except Exception:
                    pass
            self._periodic_thread = threading.Thread(
                target=self._periodic_loop,
                name="dtam-vm-periodic",
                daemon=True,
            )
            self._periodic_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._vehicle_status_event.set()
        th = None
        vehicle_th = None
        collision_th = None
        with self._lock:
            th = self._periodic_thread
            self._periodic_thread = None
            vehicle_th = self._vehicle_status_thread
            self._vehicle_status_thread = None
            collision_th = self._collision_thread
            self._collision_thread = None
        if th is not None and th.is_alive():
            th.join(timeout=2.0)
        if vehicle_th is not None and vehicle_th.is_alive():
            vehicle_th.join(timeout=2.0)
        if collision_th is not None and collision_th.is_alive():
            collision_th.join(timeout=2.0)
        cleanup_steps = [
            ("dtam-io", self._io.close),
            ("camera-streams", self._camera_streams.stop_all),
            ("vpo-camera-streams", self._vpo_camera_streams.stop_all),
            ("airsim-bridge", self._bridge.disconnect),
            ("pixel-streaming", self._terminate_pixel_streaming_server),
            ("unreal-process", self._terminate_unreal_process),
        ]
        for name, step in cleanup_steps:
            try:
                step()
            except Exception:
                logger.exception("VisualizationManager cleanup step failed: %s", name)
    # Inbound: DTAM to AirSim conversion
    def _on_rx(self, mid: str, payload: Dict[str, Any], raw: Any) -> None:
        try:
            if mid == "4001":
                self._queue_vehicle_status_frame(payload)
            elif mid == "1002":
                result = self._bridge.apply_simulation_setup(payload)
                self._emit(_hub_event(
                    kind="translate", mid=mid,
                    summary=f"1002 -> weather/wind ({len(result.get('applied', []))} params)",
                    detail=result,
                ))
                play_state = str(payload.get("playState") or "").strip().lower()
                if play_state in ("play", "playing", "run", "running", "resume") or (
                    not play_state and payload.get("playbackSpeed") is not None
                ):
                    self._emit_mission_guides(mid)
            elif mid == "1003":
                result = self._bridge.apply_scenario_setup(payload)
                self._emit(_hub_event(
                    kind="translate", mid=mid,
                    summary=f"1003 -> vehicle_map ({len(result.get('applied', []))} entries)",
                    detail=result,
                ))
            elif mid == "2002":
                result = self._bridge.on_dtam_execute(payload)
                self._emit(_hub_event(
                    kind="translate", mid=mid,
                    summary="2002 -> AirSim reset",
                    detail=result,
                ))
                self._emit_mission_guides(mid)
            elif mid == "3001":
                result = (
                    self._bridge.apply_scheduled_flight_guide(payload)
                    if self._mission_guides_visible
                    else {"applied": 0, "skipped": 1, "visible": False, "errors": []}
                )
                self._emit(_hub_event(
                    kind="translate", mid=mid,
                    summary=f"3001 -> mission guide x{result.get('applied', 0)}",
                    detail=result,
                ))
                # Simple storage/dynamics selection does not require extra VM-side work.
                self._emit(HubEvent(
                    ts=time.time(), kind="rx", mid=mid,
                    summary=f"1001 received (operationMode={payload.get('operationMode')})",
                    detail=payload,
                ))
            elif mid == "0003":
                self._emit(HubEvent(
                    ts=time.time(), kind="rx", mid=mid,
                    summary=f"0003 simTime={payload.get('simTime')}",
                    detail={"timestamp": payload.get("timestamp"), "simTime": payload.get("simTime")},
                ))
            elif mid == "5002":
                result = self.control_camera(
                    aircraft_id=str(payload.get("aircraftId") or payload.get("vehicleId") or ""),
                    vehicle_name=str(payload.get("vehicleName") or payload.get("airsimVehicleName") or ""),
                    camera_name=str(payload.get("cameraName") or payload.get("camera_name") or "front_center"),
                    yaw_delta_deg=_as_float(payload.get("yawDeltaDeg") or payload.get("yaw_delta_deg")),
                    pitch_delta_deg=_as_float(payload.get("pitchDeltaDeg") or payload.get("pitch_delta_deg")),
                    focal_length_delta=_as_float(payload.get("focalLengthDelta") or payload.get("focal_length_delta")),
                )
                self._emit(HubEvent(
                    ts=time.time(), kind="translate", mid=mid,
                    summary=f"5002 camera ok={bool(result.get('ok'))}",
                    detail=result,
                ))
            elif mid == "5003":
                result = self._bridge.apply_abnormal_situation_command(payload)
                self._emit(HubEvent(
                    ts=time.time(), kind="translate", mid=mid,
                    summary=f"5003 abnormal {payload.get('abnormalType') or payload.get('eventType') or 'event'} ok={bool(result.get('ok'))}",
                    detail=result,
                ))
            else:
                self._emit(HubEvent(
                    ts=time.time(), kind="rx", mid=mid,
                    summary=f"{mid} received",
                    detail={"keys": list(payload.keys())} if isinstance(payload, dict) else {"value": str(payload)},
                ))
        except Exception as exc:
            self._emit(HubEvent(
                ts=time.time(), kind="error", mid=mid,
                summary=f"translate failed: {type(exc).__name__}: {exc}",
                detail={},
            ))
            logger.exception("translate failed for %s", mid)

    def _queue_vehicle_status_frame(self, payload: Dict[str, Any]) -> None:
        """Keep only the latest 4001 frame for AirSim RPC application.

        AirSim RPC calls can occasionally take longer than the 4001 publish
        period. Applying every stale socket frame makes controls look delayed
        because Unreal replays old poses.  The manager therefore treats 4001 as
        latest-state telemetry: receive fast, replace pending old frames, and
        let a worker apply the newest snapshot.
        """
        with self._vehicle_status_lock:
            if self._pending_vehicle_status is not None:
                self._vehicle_status_dropped_count += 1
            self._pending_vehicle_status = dict(payload or {})
            self._vehicle_status_rx_count += 1
        self._vehicle_status_event.set()

    def _vehicle_status_loop(self) -> None:
        last_emit_ts = 0.0
        while not self._stop_event.is_set():
            if not self._vehicle_status_event.wait(timeout=0.25):
                continue

            while not self._stop_event.is_set():
                with self._vehicle_status_lock:
                    payload = self._pending_vehicle_status
                    self._pending_vehicle_status = None
                    self._vehicle_status_event.clear()

                if not payload:
                    break

                started = time.monotonic()
                result: Dict[str, Any]
                try:
                    result = self._bridge.apply_vehicle_status_frame(
                        payload,
                        pose_feedback_check=bool(self._config.collision.pose_feedback_check_enabled),
                        pose_feedback_error_threshold_m=float(
                            self._config.collision.pose_feedback_error_threshold_m
                        ),
                        pose_feedback_sample_hz=float(self._config.collision.pose_feedback_sample_hz),
                        telemetry_hz=float(self._config.runtime_optimization.telemetry_hz),
                        visual_state_hz=float(self._config.runtime_optimization.visual_state_hz),
                    )
                except Exception as exc:
                    result = {
                        "applied": 0,
                        "skipped": 0,
                        "errors": [f"{type(exc).__name__}: {exc}"],
                    }
                    logger.exception("4001 AirSim apply failed")
                elapsed_s = max(0.0, time.monotonic() - started)
                vehicle_count = int(((result.get("perf") or {}) if isinstance(result, dict) else {}).get("vehicle_count") or 0)
                target_hz = self._vehicle_status_target_hz(vehicle_count)
                with self._vehicle_status_lock:
                    self._vehicle_status_applied_count += 1
                    self._vehicle_status_last_apply_s = elapsed_s
                    self._vehicle_status_last_target_hz = target_hz
                    self._vehicle_status_last_vehicle_count = vehicle_count
                    self._vehicle_status_apply_samples.append(elapsed_s)
                    self._vehicle_status_apply_timestamps.append(time.time())
                    errors = result.get("errors") if isinstance(result, dict) else []
                    self._vehicle_status_last_error = "; ".join(map(str, errors or []))
                    dropped = self._vehicle_status_dropped_count
                    rx_count = self._vehicle_status_rx_count

                now = time.time()
                if (
                    now - last_emit_ts >= VEHICLE_STATUS_EVENT_PERIOD_S
                    or bool(result.get("errors"))
                ):
                    detail = dict(result)
                    detail.update({
                        "rx_frames": rx_count,
                        "dropped_stale_frames": dropped,
                        "apply_ms": round(elapsed_s * 1000.0, 3),
                        "target_hz": target_hz,
                        "vehicle_count": vehicle_count,
                        "mode": "latest-only",
                    })
                    self._emit(_hub_event(
                        kind="translate", mid="4001",
                        summary=(
                            f"4001 latest -> simSetVehiclePose "
                            f"x{result.get('applied', 0)} drop={dropped} "
                            f"mode={result.get('collision_mode', '-')}"
                        ),
                        detail=detail,
                    ))
                    last_emit_ts = now

                for feedback in list(result.get("pose_feedback") or []):
                    if isinstance(feedback, dict) and feedback.get("blocked_suspected"):
                        if bool(self._config.collision.pose_feedback_publish_to_server):
                            collision_payload = _pose_feedback_to_4103_payload(
                                feedback,
                                default_recommended_action=(
                                    self._config.collision.pose_feedback_recommended_action
                                    or "none"
                                ),
                            )
                            if collision_payload is not None:
                                self._publish_collision_payload(
                                    collision_payload,
                                    phase="pose-feedback-blocked-sweep",
                                )
                        self._emit(_hub_event(
                            kind="warning",
                            mid="4001-pose-feedback",
                            summary=(
                                f"AirSim sweep may have blocked {feedback.get('aircraftId')}: "
                                f"pose error {feedback.get('error_m')} m"
                            ),
                            detail=feedback,
                        ))

                delay_s = (1.0 / max(1.0, float(target_hz))) - elapsed_s
                if delay_s > 0.0 and self._stop_event.wait(delay_s):
                    return
                if not self._vehicle_status_event.is_set():
                    break

    def _vehicle_status_pipeline_stats(self) -> Dict[str, Any]:
        with self._vehicle_status_lock:
            apply_stats = _duration_stats_ms(self._vehicle_status_apply_samples)
            return {
                "mode": "latest-only",
                "target_hz": float(self._vehicle_status_last_target_hz),
                "base_target_hz": float(self._config.runtime_optimization.vehicle_status_apply_hz),
                "last_vehicle_count": int(self._vehicle_status_last_vehicle_count),
                "telemetry_hz": float(self._config.runtime_optimization.telemetry_hz),
                "visual_state_hz": float(self._config.runtime_optimization.visual_state_hz),
                "effective_hz": _effective_hz(self._vehicle_status_apply_timestamps),
                "pending": self._pending_vehicle_status is not None,
                "rx_frames": int(self._vehicle_status_rx_count),
                "applied_frames": int(self._vehicle_status_applied_count),
                "dropped_stale_frames": int(self._vehicle_status_dropped_count),
                "last_apply_ms": round(float(self._vehicle_status_last_apply_s) * 1000.0, 3),
                "avg_apply_ms": apply_stats["avg_ms"],
                "max_apply_ms": apply_stats["max_ms"],
                "apply_samples": apply_stats["samples"],
                "last_error": self._vehicle_status_last_error,
            }

    def _vehicle_status_target_hz(self, vehicle_count: int = 0) -> float:
        base_hz = max(1.0, min(60.0, float(self._config.runtime_optimization.vehicle_status_apply_hz or VEHICLE_STATUS_APPLY_HZ)))
        count = max(0, int(vehicle_count or 0))
        if count <= 0:
            return base_hz
        for tier in list(self._config.runtime_optimization.vehicle_status_apply_hz_by_vehicle_count or []):
            if not isinstance(tier, dict):
                continue
            try:
                min_count = int(tier.get("min", 0))
                max_count = int(tier.get("max", 999))
                hz = float(tier.get("hz", base_hz))
            except (TypeError, ValueError):
                continue
            if min_count <= count <= max_count:
                return max(1.0, min(60.0, hz))
        return base_hz

    def _publish_collision_payload(
        self,
        payload: Dict[str, Any],
        *,
        phase: str,
        now: Optional[float] = None,
    ) -> bool:
        """De-duplicate and publish one normalized 4103 collision payload."""
        if not isinstance(payload, dict):
            return False
        if not self._config.collision.enabled:
            return False
        event_ts = time.time() if now is None else float(now)
        if not self._should_emit_collision_event(payload, event_ts):
            return False

        cfg = self._config.collision
        send_result: Dict[str, Any] = {
            "ok": False,
            "mid": "4103",
            "skipped": True,
            "reason": "publish_to_server disabled",
        }
        if cfg.publish_to_server:
            send_result = self._io.send_vehicle_collision_event(payload)
            with self._collision_lock:
                self._collision_tx_count += 1
                if send_result.get("ok"):
                    self._collision_tx_ok_count += 1
                self._collision_last_send = dict(send_result)

        with self._collision_lock:
            self._collision_event_count += 1
            self._collision_last_event = dict(payload)

        self._emit(_hub_event(
            kind="tx" if send_result.get("ok") else ("error" if cfg.publish_to_server else "airsim"),
            mid="4103",
            summary=(
                f"4103 collision -> server ok={bool(send_result.get('ok'))}: "
                f"{payload.get('aircraftId')} with "
                f"{payload.get('objectName') or payload.get('objectId')}"
            ),
            detail={
                "payload": payload,
                "server_published": bool(send_result.get("ok")),
                "send_result": send_result,
                "phase": phase,
            },
        ))
        return bool(send_result.get("ok")) or not cfg.publish_to_server

    def _collision_loop(self) -> None:
        """Poll AirSim collision state and expose normalized 4103-shaped events internally."""
        while not self._stop_event.is_set():
            cfg = self._config.collision
            period_s = 1.0 / max(0.2, min(60.0, float(cfg.poll_hz or 5.0)))
            started = time.monotonic()
            result: Dict[str, Any]
            try:
                result = self._bridge.poll_collision_events(
                    default_recommended_action=cfg.default_recommended_action,
                )
            except Exception as exc:
                result = {
                    "connected": False,
                    "polled": 0,
                    "events": [],
                    "errors": [f"{type(exc).__name__}: {exc}"],
                    "targets": [],
                }
                logger.exception("AirSim collision polling failed")

            elapsed_s = max(0.0, time.monotonic() - started)
            errors = [str(item) for item in result.get("errors", []) if str(item)]
            events = [item for item in result.get("events", []) if isinstance(item, dict)]

            with self._collision_lock:
                self._collision_poll_count += 1
                self._collision_last_poll_s = elapsed_s
                self._collision_poll_samples.append(elapsed_s)
                self._collision_poll_timestamps.append(time.time())
                self._collision_last_targets_count = len(result.get("targets") or [])
                self._collision_last_error = "; ".join(errors)

            now = time.time()
            for payload in events:
                self._publish_collision_payload(
                    payload,
                    phase="session-3-server-forwarding",
                    now=now,
                )

            if errors and now - self._collision_last_error_emit_ts >= 5.0:
                self._collision_last_error_emit_ts = now
                self._emit(_hub_event(
                    kind="error",
                    mid="4103",
                    summary=f"collision polling warning: {errors[0]}",
                    detail={
                        "errors": errors[:5],
                        "connected": bool(result.get("connected")),
                        "targets": result.get("targets", []),
                    },
                ))

            delay_s = period_s - elapsed_s
            if self._stop_event.wait(timeout=max(0.02, delay_s)):
                break

    def _should_emit_collision_event(self, payload: Dict[str, Any], now: float) -> bool:
        cfg = self._config.collision
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        key = str(
            metadata.get("dedupKey")
            or payload.get("eventId")
            or (
                f"{payload.get('aircraftId')}|"
                f"{payload.get('collisionTimeNanos')}|"
                f"{payload.get('objectName') or payload.get('objectId')}"
            )
        )
        window_s = max(0.0, float(cfg.dedup_window_sec or 0.0))
        with self._collision_lock:
            # Keep the cache small and time-bounded.
            stale_keys = [
                old_key
                for old_key, seen_ts in self._collision_dedup.items()
                if now - seen_ts > max(window_s * 3.0, 5.0)
            ]
            for old_key in stale_keys:
                self._collision_dedup.pop(old_key, None)

            last_seen = self._collision_dedup.get(key)
            if last_seen is not None and now - last_seen < window_s:
                self._collision_duplicate_count += 1
                return False
            self._collision_dedup[key] = now
            return True

    def _collision_stats(self) -> Dict[str, Any]:
        cfg = self._config.collision
        with self._collision_lock:
            poll_stats = _duration_stats_ms(self._collision_poll_samples)
            return {
                "enabled": bool(cfg.enabled),
                "target_hz": float(cfg.poll_hz),
                "effective_hz": _effective_hz(self._collision_poll_timestamps),
                "dedup_window_sec": float(cfg.dedup_window_sec),
                "publish_to_server": bool(cfg.publish_to_server),
                "publish_no_collision": bool(cfg.publish_no_collision),
                "default_recommended_action": str(cfg.default_recommended_action or "hold"),
                "pose_feedback_check_enabled": bool(cfg.pose_feedback_check_enabled),
                "pose_feedback_publish_to_server": bool(cfg.pose_feedback_publish_to_server),
                "pose_feedback_recommended_action": str(cfg.pose_feedback_recommended_action or "none"),
                "pose_feedback_error_threshold_m": float(cfg.pose_feedback_error_threshold_m),
                "pose_feedback_sample_hz": float(cfg.pose_feedback_sample_hz),
                "server_published": bool(cfg.publish_to_server),
                "publish_phase": "session-5-physical-mode-diagnostics",
                "polls": int(self._collision_poll_count),
                "events": int(self._collision_event_count),
                "duplicates_suppressed": int(self._collision_duplicate_count),
                "tx_count": int(self._collision_tx_count),
                "tx_ok_count": int(self._collision_tx_ok_count),
                "last_targets_count": int(self._collision_last_targets_count),
                "last_poll_ms": round(float(self._collision_last_poll_s) * 1000.0, 3),
                "avg_poll_ms": poll_stats["avg_ms"],
                "max_poll_ms": poll_stats["max_ms"],
                "poll_samples": poll_stats["samples"],
                "last_error": self._collision_last_error,
                "last_event": dict(self._collision_last_event or {}),
                "last_send": dict(self._collision_last_send or {}),
                "thread_running": self._collision_thread is not None and self._collision_thread.is_alive(),
            }
    # Periodic tasks: 0002 heartbeat and 4101 camera
    def _periodic_loop(self) -> None:
        last_status_ts = 0.0
        last_camera_ts = 0.0
        last_metrics_ts = 0.0
        while not self._stop_event.is_set():
            now = time.time()
            # 0002 Module Status 1 Hz (default)
            status_period = 1.0 / max(0.1, float(self._streaming.module_status_hz))
            if now - last_status_ts >= status_period:
                # MSG 0002 ICD only allows status=1.
                # Publish AirSim connection details separately through VM state/UI.
                connected = self._bridge.ping() if self._bridge.status().host else False
                status_code = 1
                res = self._io.send_module_status(status_code)
                self._emit(_hub_event(
                    kind="tx", mid="0002",
                    summary=f"0002 -> status={status_code} airsim_connected={connected}",
                    detail=res,
                ))
                last_status_ts = now
            # 4101 Camera Image (optional)
            # 4101 Camera Image (optional)
            if self._streaming.camera_enabled:
                # 4101 is a low-rate ICD snapshot path.  Real-time video must
                # use the direct 4102/media-plane stream; otherwise base64 JSON
                # frames can congest the StateServer control/telemetry path.
                camera_hz = min(
                    ICD_CAMERA_SNAPSHOT_MAX_HZ,
                    max(0.1, float(self._streaming.camera_hz)),
                )
                cam_period = 1.0 / camera_hz
                if now - last_camera_ts >= cam_period:
                    last_camera_ts = now
                    self._capture_and_send_camera()

            metrics_cfg = self._config.metrics
            metrics_period = max(1.0, float(metrics_cfg.log_interval_sec or 0.0))
            if metrics_cfg.enabled and metrics_cfg.log_interval_sec > 0 and now - last_metrics_ts >= metrics_period:
                last_metrics_ts = now
                self._write_performance_metric_line(now)

            if self._stop_event.wait(timeout=0.05):
                break

    def _capture_and_send_camera(self) -> None:
        now = time.time()
        cfg = self._streaming
        capture_started = time.perf_counter()
        data, meta = self._bridge.capture_camera_frame(
            camera_name=cfg.camera_name,
            image_type=cfg.camera_image_type,
            vehicle_name=cfg.camera_vehicle,
            quality=cfg.camera_quality,
        )
        capture_s = max(0.0, time.perf_counter() - capture_started)
        if not data:
            self._record_camera_snapshot(
                capture_s=capture_s,
                send_s=0.0,
                ok=False,
                tx_ok=False,
                meta=dict(meta or {}),
            )
            self._emit(HubEvent(
                ts=now, kind="error", mid="4101",
                summary=f"camera capture failed: {meta.get('error')}",
                detail=meta,
            ))
            return
        from datetime import datetime, timezone
        iso = datetime.fromtimestamp(now, tz=timezone.utc)
        iso_ts = iso.strftime("%Y-%m-%dT%H:%M:%S.") + f"{iso.microsecond // 1000:03d}Z"
        header = {
            "message_id": 4101,
            "message_name": "Camera Image Frame",
            "timestamp": iso_ts,
            "vehicle_id": cfg.camera_vehicle or "UAM0001",
            "camera_name": cfg.camera_name,
            "image_type": cfg.camera_image_type,
            "sequence": int(now * 1000) & 0xFFFFFFFF,
            "width": 0,
            "height": 0,
            "channels": 3,
            "pixel_format": "jpeg",
            "encoding": "jpeg",
            "payload_size": len(data),
        }
        send_started = time.perf_counter()
        res = self._io.send_camera_image(header, data)
        send_s = max(0.0, time.perf_counter() - send_started)
        self._record_camera_snapshot(
            capture_s=capture_s,
            send_s=send_s,
            ok=True,
            tx_ok=bool(res.get("ok")),
            meta={**dict(meta or {}), "payload_size": len(data), "tx": dict(res or {})},
        )
        self._emit(_hub_event(
            kind="tx", mid="4101",
            summary=f"4101 -> {len(data)} B",
            detail=res,
        ))

    def _record_camera_snapshot(
        self,
        *,
        capture_s: float,
        send_s: float,
        ok: bool,
        tx_ok: bool,
        meta: Dict[str, Any],
    ) -> None:
        with self._camera_snapshot_lock:
            self._camera_snapshot_count += 1
            if not ok:
                self._camera_snapshot_error_count += 1
            if ok:
                self._camera_snapshot_tx_count += 1
            if tx_ok:
                self._camera_snapshot_tx_ok_count += 1
            self._camera_snapshot_capture_samples.append(max(0.0, float(capture_s)))
            self._camera_snapshot_send_samples.append(max(0.0, float(send_s)))
            self._camera_snapshot_timestamps.append(time.time())
            safe_meta = dict(meta or {})
            safe_meta.pop("frame", None)
            safe_meta.pop("image_b64", None)
            self._camera_snapshot_last_meta = safe_meta

    def _camera_snapshot_stats(self) -> Dict[str, Any]:
        with self._camera_snapshot_lock:
            capture_stats = _duration_stats_ms(self._camera_snapshot_capture_samples)
            send_stats = _duration_stats_ms(self._camera_snapshot_send_samples)
            return {
                "enabled": bool(self._streaming.camera_enabled),
                "target_hz": min(ICD_CAMERA_SNAPSHOT_MAX_HZ, max(0.1, float(self._streaming.camera_hz))),
                "effective_hz": _effective_hz(self._camera_snapshot_timestamps),
                "captures": int(self._camera_snapshot_count),
                "errors": int(self._camera_snapshot_error_count),
                "tx_count": int(self._camera_snapshot_tx_count),
                "tx_ok_count": int(self._camera_snapshot_tx_ok_count),
                "avg_capture_ms": capture_stats["avg_ms"],
                "max_capture_ms": capture_stats["max_ms"],
                "avg_send_ms": send_stats["avg_ms"],
                "max_send_ms": send_stats["max_ms"],
                "samples": capture_stats["samples"],
                "last_meta": dict(self._camera_snapshot_last_meta or {}),
            }

    def _resolve_metrics_log_path(self) -> Path:
        configured = str(getattr(self._config.metrics, "log_path", "") or "").strip()
        if configured:
            return Path(configured).expanduser()
        return FRAMEWORK_ROOT / ".dtam_runtime" / "logs" / "visualization_performance.jsonl"

    def _write_performance_metric_line(self, now: float) -> None:
        try:
            payload = {
                "timestamp": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
                "uptime_s": round(now - self._started_at, 3) if self._started_at else 0.0,
                "vehicle_status_pipeline": self._vehicle_status_pipeline_stats(),
                "collision": self._collision_stats(),
                "camera_snapshot": self._camera_snapshot_stats(),
                "media_streams": self._camera_streams.stats(),
                "vpo_media_streams": self._vpo_camera_streams.stats(),
                "unreal_profile_mode": str(self._config.unreal.profile_mode or "off"),
            }
            self._metrics_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._metrics_log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        except Exception:
            logger.debug("failed to write visualization performance metrics", exc_info=True)

    # Public control API
    def launch_unreal(self, *, pixel_streaming: bool = False) -> Dict[str, Any]:
        with self._lock:
            if self._unreal_proc is not None and self._unreal_proc.poll() is None:
                return self.unreal_status()

            if _is_tcp_port_open(self._config.airsim.host, self._config.airsim.port):
                status = self.unreal_status()
                status["ok"] = True
                status["running"] = True
                status["external_runtime"] = True
                status["message"] = "AirSim RPC is already available; reusing the existing Unreal runtime."
                if pixel_streaming and self._config.pixel_streaming.enabled:
                    status["pixel_streaming_note"] = (
                        "An Unreal runtime is already running. If it was not launched with "
                        "-PixelStreamingURL, restart Unreal from TestStream's Unreal 실행 button."
                    )
                self._emit(HubEvent(
                    ts=time.time(), kind="airsim", mid="",
                    summary="Unreal launch skipped: existing AirSim RPC runtime detected",
                    detail=status,
                ))
                return status

            pixel_requested = bool(pixel_streaming and self._config.pixel_streaming.enabled)
            pixel_status = None
            if pixel_requested:
                pixel_status = self._ensure_pixel_streaming_server()

            executable = self._resolve_unreal_executable()
            if executable is None:
                status = self.unreal_status()
                status["ok"] = False
                status["error"] = "DTAMVisualization.exe not found"
                self._emit(HubEvent(
                    ts=time.time(), kind="error", mid="",
                    summary="Unreal launch failed: executable not found",
                    detail=status,
                ))
                return status

            working_dir = self._resolve_unreal_working_dir(executable)
            runtime_config_paths = self._prepare_unreal_runtime_configs(executable)
            args = [str(executable), *self._effective_unreal_args(pixel_streaming=pixel_requested)]
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            log_path = FRAMEWORK_ROOT / ".dtam_runtime" / "logs" / "visualization_unreal.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path.open("a", encoding="utf-8", errors="replace")
            log_file.write(
                f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] launch unreal\n"
                f"  executable={executable}\n"
                f"  cwd={working_dir}\n"
                f"  args={args}\n"
                f"  runtime_config_paths={runtime_config_paths}\n"
            )
            log_file.flush()
            try:
                self._unreal_proc = subprocess.Popen(
                    args,
                    cwd=str(working_dir),
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                )
            finally:
                log_file.close()
            time.sleep(0.75)
            self._last_unreal_pixel_streaming = pixel_requested
            status = self.unreal_status()
            exit_code = status.get("exit_code")
            status["ok"] = exit_code is None
            if exit_code is not None:
                status["error"] = f"Unreal process exited immediately with code {exit_code}"
            status["log_path"] = str(log_path)
            if pixel_status is not None:
                status["pixel_server"] = pixel_status
            self._emit(HubEvent(
                ts=time.time(), kind="airsim", mid="",
                summary=f"Unreal launch pid={status.get('pid')}",
                detail=status,
            ))
            return status

    def _prepare_unreal_runtime_configs(self, executable: Path) -> List[str]:
        """Write late-bound packaged-runtime overrides before DT World starts.

        The packaged DT World EXE reads cooked defaults from its staged project
        directory, not only the source tree's DefaultGame.ini.  When the
        stage-local Saved/Config/Windows/Game.ini is missing, Cesium
        stream-camera tile loading can fall back to the old cooked default
        (disabled), so the vehicle appears in an empty sky even though
        KP2A_Map loaded correctly.
        """
        values = self._unreal_runtime_cesium_launch_values()
        paths: List[Path] = [
            FRAMEWORK_ROOT / "VisualizationModule_Source" / "Unreal" / "Environments" / "DTAMVisualization" / "Config" / "DefaultGame.ini",
            UNREAL_ROOT / "Environments" / "DTAMVisualization" / "Config" / "DefaultGame.ini",
        ]
        for staged_dir in self._candidate_unreal_staged_project_dirs(executable):
            paths.extend([
                staged_dir / "Saved" / "Config" / "Windows" / "Game.ini",
                staged_dir / "Config" / "DefaultGame.ini",
            ])

        written: List[str] = []
        seen: set[str] = set()
        for path in paths:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            try:
                self._write_unreal_ini_section_values(
                    path,
                    "[/Script/DTAMVisualization.DTAMVisualizationCesiumSettings]",
                    values,
                )
                written.append(key)
            except Exception:
                logger.debug("failed to prepare Unreal runtime config %s", path, exc_info=True)
        return written

    def _candidate_unreal_staged_project_dirs(self, executable: Path) -> List[Path]:
        dirs: List[Path] = [
            UNREAL_ROOT
            / "Environments"
            / "DTAMVisualization"
            / "Saved"
            / "StagedBuilds"
            / "Windows"
            / "DTAMVisualization"
        ]

        try:
            exe = executable.resolve()
        except Exception:
            exe = executable
        parent = exe.parent
        if (parent / "DTAMVisualization" / "Binaries" / "Win64").exists():
            dirs.append(parent / "DTAMVisualization")
        if parent.name.lower() == "win64" and parent.parent.name.lower() == "binaries":
            dirs.append(parent.parent.parent)

        unique: List[Path] = []
        seen: set[str] = set()
        for item in dirs:
            key = str(item)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _unreal_runtime_cesium_launch_values(self) -> Dict[str, str]:
        rendering = self._config.rendering_performance
        stream_max_cameras = max(2, int(getattr(rendering, "stream_camera_tile_loading_max_cameras", 2)))
        refresh_seconds = float(getattr(rendering, "stream_camera_tile_loading_refresh_s", 0.25))
        refresh_seconds = max(0.10, min(0.50, refresh_seconds))
        return {
            "MaximumScreenSpaceError": f"{float(rendering.maximum_screen_space_error):.1f}",
            "MaximumSimultaneousTileLoads": str(int(rendering.maximum_simultaneous_tile_loads)),
            "MaximumCachedMegabytes": str(int(rendering.maximum_cached_megabytes)),
            "LoadingDescendantLimit": str(int(rendering.loading_descendant_limit)),
            "CulledScreenSpaceError": f"{float(rendering.culled_screen_space_error):.1f}",
            "bForbidHoles": "True",
            "bEnableFogCulling": "False",
            "bEnforceCulledScreenSpaceError": "False",
            "bEnableDistanceFog": "False",
            "DistanceFogDensity": "0",
            "DistanceFogStartDistanceMeters": "5000.0",
            "DistanceFogMaxOpacity": "0.00",
            # Packaged AirSim cameras are BP_PIPCamera_* rather than the
            # front_center/fpv names used by the hints, so all stream cameras
            # must be eligible and capped here.
            "bEnableStreamCameraTileLoading": "True",
            "bStreamCameraTileLoadingUseAllAirSimCameras": "True",
            "StreamCameraTileLoadingMaxCameras": str(stream_max_cameras),
            "StreamCameraTileLoadingRefreshSeconds": f"{refresh_seconds:.2f}",
            "StreamCameraTileLoadingFallbackWidth": "640.0",
            "StreamCameraTileLoadingFallbackHeight": "360.0",
            "StreamCameraTileLoadingFallbackFovDegrees": "90.0",
            "bSkyLightRealTimeCapture": "True" if rendering.sky_light_realtime_capture else "False",
        }

    def start_pixel_streaming_server(self) -> Dict[str, Any]:
        status = self._ensure_pixel_streaming_server()
        self._emit(HubEvent(
            ts=time.time(), kind="airsim", mid="",
            summary=f"Pixel Streaming server start running={status.get('running')}",
            detail=status,
        ))
        return status

    def _ensure_pixel_streaming_server(self) -> Dict[str, Any]:
        ps = self._config.pixel_streaming
        if not ps.enabled:
            return {"ok": False, "enabled": False}
        if _is_tcp_port_open("127.0.0.1", ps.player_port):
            return {"ok": True, "running": True, "external_runtime": True, "player_url": ps.player_url}
        if self._pixel_server_proc is not None and self._pixel_server_proc.poll() is None:
            return {
                "ok": True,
                "running": True,
                "pid": self._pixel_server_proc.pid,
                "player_url": ps.player_url,
            }

        signalling_dir = Path(str(ps.signalling_dir or ""))
        start_script = signalling_dir / "platform_scripts" / "cmd" / "start.bat"
        if not start_script.is_file():
            return {
                "ok": False,
                "running": False,
                "error": "Pixel Streaming SignallingWebServer start.bat not found",
                "signalling_dir": str(signalling_dir),
            }

        log_path = FRAMEWORK_ROOT / ".dtam_runtime" / "logs" / "pixel_streaming_server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("a", encoding="utf-8", errors="replace")
        args = [
            "cmd.exe",
            "/c",
            str(start_script),
            "--publicip",
            "127.0.0.1",
            "--player_port",
            str(ps.player_port),
            "--streamer_port",
            str(ps.streamer_port),
            "--homepage",
            "player.html",
        ]
        log_file.write(
            f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] launch pixel streaming signalling\n"
            f"  cwd={signalling_dir}\n"
            f"  args={args}\n"
        )
        log_file.flush()
        try:
            self._pixel_server_proc = subprocess.Popen(
                args,
                cwd=str(signalling_dir),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        finally:
            log_file.close()
        ready = self._wait_for_pixel_streaming_player(timeout_s=120.0)
        return {
            "ok": ready,
            "running": ready,
            "pid": self._pixel_server_proc.pid,
            "player_url": ps.player_url,
            "streamer_url": ps.streamer_url,
            "log_path": str(log_path),
            "message": (
                "Pixel Streaming player server is ready."
                if ready
                else "Pixel Streaming server process started, but player port did not open before timeout."
            ),
        }

    def _wait_for_pixel_streaming_player(self, *, timeout_s: float = 120.0) -> bool:
        ps = self._config.pixel_streaming
        deadline = time.time() + max(1.0, float(timeout_s))
        while time.time() < deadline:
            if _is_tcp_port_open("127.0.0.1", ps.player_port):
                return True
            process = self._pixel_server_proc
            if process is not None and process.poll() is not None:
                return False
            time.sleep(0.5)
        return _is_tcp_port_open("127.0.0.1", ps.player_port)

    def _terminate_pixel_streaming_server(self) -> None:
        with self._lock:
            process = self._pixel_server_proc
            self._pixel_server_proc = None
        if process is None or process.poll() is not None:
            return
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8.0,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
            return
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)

    def _terminate_unreal_process(self) -> None:
        with self._lock:
            process = self._unreal_proc
            self._unreal_proc = None
        if process is None or process.poll() is not None:
            return
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8.0,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
            return
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)

    def _effective_unreal_args(self, *, pixel_streaming: Optional[bool] = None) -> list[str]:
        args: list[str] = []
        for item in self._config.unreal.args:
            text = str(item).strip()
            if text and text not in args:
                args.append(text)

        if not any(self._is_unreal_map_arg(item) for item in args):
            args.insert(0, UNREAL_DEFAULT_MAP)

        profile_args, profile_exec_cmds = self._unreal_profile_options()
        for item in profile_args:
            text = str(item).strip()
            if text and text not in args:
                args.append(text)
        if profile_exec_cmds:
            args = self._append_unreal_exec_cmds(args, profile_exec_cmds)
        if bool(getattr(self._config.rendering_performance, "apply_on_launch", True)):
            args = self._append_unreal_exec_cmds(args, self._rendering_exec_cmds())

        use_pixel_streaming = (
            bool(pixel_streaming)
            if pixel_streaming is not None
            else bool(self._config.pixel_streaming.enabled and self._config.pixel_streaming.auto_start_server)
        )
        if use_pixel_streaming:
            pixel_args = [
                f"-PixelStreamingURL={self._config.pixel_streaming.streamer_url}",
                "-AudioMixer",
            ]
            for arg in pixel_args:
                if arg not in args:
                    args.append(arg)

        # Keep the packaged runtime on the default RHI and avoid forcing Nanite
        # off. Cesium's large 3D Tiles scene becomes extremely slow without
        # Nanite, so startup crash mitigation is handled through AirSim settings
        # (InitialInstanceSegmentation=False) instead of renderer-wide switches.
        args = [arg for arg in args if arg.strip() != "-ExecCmds=r.Nanite 0"]
        # Disable Unreal's built-in MoviePlayer startup movie.  The packaged
        # DT World pak can still contain an older StartupMovies entry, which
        # plays the MP4 once without our "Loading DT World..." overlay and then
        # hands off through a black frame.  DTAM owns loading UX through the
        # in-viewport Slate overlay, so force MoviePlayer off for the
        # Development runtime that VisualizationModule launches.
        for required in ("-windowed", "-NoSplash", "-NoLoadingScreen"):
            if required not in args:
                args.append(required)
        return args

    @staticmethod
    def _is_unreal_map_arg(arg: Any) -> bool:
        text = str(arg).strip()
        if not text or text.startswith("-"):
            return False
        return text.startswith("/") or text.endswith(".umap")

    def _unreal_profile_options(self) -> tuple[list[str], list[str]]:
        mode = str(self._config.unreal.profile_mode or "off").strip().lower()
        if mode in ("", "off", "none", "false", "0"):
            return [], []

        profile_args = [str(item).strip() for item in self._config.unreal.profile_args if str(item).strip()]
        profile_exec_cmds = [
            str(item).strip()
            for item in self._config.unreal.profile_exec_cmds
            if str(item).strip()
        ]

        if mode in ("stats", "full") and not profile_exec_cmds:
            profile_exec_cmds.extend([
                "stat unit",
                "stat fps",
                "stat game",
                "stat gpu",
                "stat streaming",
                "stat RHI",
            ])
        if mode in ("trace", "full"):
            for item in ("-trace=cpu,gpu,frame,bookmark,loadtime", "-statnamedevents"):
                if item not in profile_args:
                    profile_args.append(item)
        return profile_args, profile_exec_cmds

    def _rendering_exec_cmds(self) -> list[str]:
        rendering = self._config.rendering_performance
        level = max(0, min(3, int(rendering.scalability_level)))
        texture_level = max(1, min(3, level + 1))
        screen_percentage = max(50, min(100, int(rendering.screen_percentage)))
        frame_rate_limit = max(20, min(60, int(rendering.frame_rate_limit)))
        return [
            f"t.MaxFPS {frame_rate_limit}",
            "r.VSync 0",
            f"r.ScreenPercentage {screen_percentage}",
            f"sg.ViewDistanceQuality {level}",
            "sg.ShadowQuality 0",
            f"sg.PostProcessQuality {level}",
            f"sg.EffectsQuality {level}",
            "sg.FoliageQuality 0",
            f"sg.ReflectionQuality {level}",
            f"sg.GlobalIlluminationQuality {level}",
            f"sg.AntiAliasingQuality {level}",
            f"sg.TextureQuality {texture_level}",
            f"sg.ShadingQuality {level}",
            f"sg.LandscapeQuality {level}",
            "r.Shadow.Virtual.Enable 0",
            "r.ShadowQuality 0",
            "r.MotionBlurQuality 0",
            "r.DepthOfFieldQuality 0",
            "r.SceneColorFringeQuality 0",
            "r.AmbientOcclusionLevels 0",
            "r.SSR.Quality 0",
            "r.RefractionQuality 0",
            "r.BloomQuality 1",
            "r.Tonemapper.Quality 3",
        ]

    @staticmethod
    def _parse_rendering_bool(value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("1", "true", "yes", "on"):
                return True
            if normalized in ("0", "false", "no", "off"):
                return False
        return None

    @staticmethod
    def _append_unreal_exec_cmds(args: list[str], extra_cmds: list[str]) -> list[str]:
        safe_cmds = [str(cmd).strip() for cmd in extra_cmds if str(cmd).strip()]
        if not safe_cmds:
            return args
        out = list(args)
        exec_index = next(
            (index for index, arg in enumerate(out) if str(arg).startswith("-ExecCmds=")),
            -1,
        )
        if exec_index < 0:
            out.append("-ExecCmds=" + ",".join(safe_cmds))
            return out

        existing_arg = str(out[exec_index])
        existing = existing_arg[len("-ExecCmds="):]
        existing_cmds = [cmd.strip() for cmd in existing.split(",") if cmd.strip()]
        existing_lower = {cmd.lower() for cmd in existing_cmds}
        existing_keys = {
            VisualizationManager._unreal_exec_cmd_replace_key(cmd): index
            for index, cmd in enumerate(existing_cmds)
            if VisualizationManager._unreal_exec_cmd_replace_key(cmd)
        }
        for cmd in safe_cmds:
            cmd_key = VisualizationManager._unreal_exec_cmd_replace_key(cmd)
            if cmd_key and cmd_key in existing_keys:
                existing_cmds[existing_keys[cmd_key]] = cmd
                existing_lower = {item.lower() for item in existing_cmds}
                continue
            if cmd.lower() in existing_lower:
                continue
            if cmd_key:
                existing_keys[cmd_key] = len(existing_cmds)
            existing_cmds.append(cmd)
            existing_lower.add(cmd.lower())
        out[exec_index] = "-ExecCmds=" + ",".join(existing_cmds)
        return out

    @staticmethod
    def _unreal_exec_cmd_replace_key(command: str) -> Optional[str]:
        """Return a replacement key for simple CVar commands.

        ``stat fps`` and similar commands share the first token, so only CVar
        families that are safe to replace by name use this key.
        """
        first = str(command or "").strip().split(" ", 1)[0].strip().lower()
        if first.startswith(("r.", "sg.", "t.")):
            return first
        return None

    def unreal_status(self) -> Dict[str, Any]:
        process = self._unreal_proc
        exit_code = process.poll() if process is not None else None
        own_running = bool(process is not None and exit_code is None)
        external_runtime = not own_running and _is_tcp_port_open(self._config.airsim.host, self._config.airsim.port)
        executable = self._resolve_unreal_executable()
        ps = self._config.pixel_streaming
        return {
            "running": own_running or external_runtime,
            "pid": process.pid if own_running else None,
            "exit_code": exit_code,
            "executable": str(executable) if executable is not None else "",
            "args": self._effective_unreal_args(pixel_streaming=self._last_unreal_pixel_streaming),
            "profile_mode": str(self._config.unreal.profile_mode or "off"),
            "rendering_performance": self.rendering_settings(),
            "external_runtime": external_runtime,
            "log_path": str(FRAMEWORK_ROOT / ".dtam_runtime" / "logs" / "visualization_unreal.log"),
            "performance_log_path": str(self._metrics_log_path),
            "airsim_rpc": {
                "host": self._config.airsim.host,
                "port": self._config.airsim.port,
                "open": own_running or external_runtime,
            },
            "pixel_streaming": {
                "enabled": ps.enabled,
                "auto_start_server": ps.auto_start_server,
                "player_url": ps.player_url,
                "streamer_url": ps.streamer_url,
                "player_port": ps.player_port,
                "streamer_port": ps.streamer_port,
                "player_open": _is_tcp_port_open(_url_host(ps.player_url), ps.player_port),
                "streamer_open": _is_tcp_port_open(_url_host(ps.streamer_url), ps.streamer_port),
                "signalling_dir": ps.signalling_dir,
            },
        }

    def _resolve_unreal_executable(self) -> Optional[Path]:
        configured = str(self._config.unreal.executable or "").strip()
        packaged = (
            UNREAL_ROOT
            / "Environments"
            / "DTAMVisualization"
            / "Saved"
            / "StagedBuilds"
            / "Windows"
            / "DTAMVisualization.exe"
        )
        self._repair_staged_unreal_launcher(packaged)
        development = (
            UNREAL_ROOT
            / "Environments"
            / "DTAMVisualization"
            / "Binaries"
            / "Win64"
            / "DTAMVisualization.exe"
        )
        if configured:
            configured_path = Path(configured).expanduser()
            if configured_path.is_file():
                configured_resolved = configured_path.resolve()
                # The old config often points at the project Binaries/Win64 exe.
                # For Operations Console launches, prefer the packaged runtime
                # launcher because it has the cooked content/runtime layout.
                if (
                    packaged.is_file()
                    and development.is_file()
                    and configured_resolved == development.resolve()
                ):
                    return packaged.resolve()
                return configured_resolved

        candidates: List[Path] = [packaged, development]
        existing = [path.resolve() for path in candidates if path.is_file()]
        if not existing:
            return None

        def _priority(path: Path) -> tuple[int, float]:
            resolved = str(path)
            if "\\Saved\\StagedBuilds\\Windows\\" in resolved:
                category = 0
            elif "\\Binaries\\Win64\\" in resolved:
                category = 1
            else:
                category = 2
            return (category, -path.stat().st_mtime)

        return min(existing, key=_priority)

    def _repair_staged_unreal_launcher(self, packaged: Path) -> None:
        """Restore the tiny packaged launcher if it was overwritten by the dev exe.

        The packaged root launcher sits at ``Saved/StagedBuilds/Windows`` and
        forwards to ``DTAMVisualization/Binaries/Win64``.  Copying the large
        development binary over this file makes Unreal search for
        ``../../DTAMVisualization.uproject`` from the staged folder and fail
        before the map loads.  Keep this guard here so future local binary
        refreshes do not break OperationModule's DT World button again.
        """
        try:
            if not packaged.is_file() or packaged.stat().st_size < 10 * 1024 * 1024:
                return
            project_root = UNREAL_ROOT / "Environments" / "DTAMVisualization"
            staging_stub = project_root / "Intermediate" / "Staging" / "DTAMVisualization.exe"
            inner_binary = packaged.parent / "DTAMVisualization" / "Binaries" / "Win64" / "DTAMVisualization.exe"
            if staging_stub.is_file() and inner_binary.is_file():
                shutil.copy2(staging_stub, packaged)
                logger.warning("Repaired staged Unreal launcher stub: %s <- %s", packaged, staging_stub)
        except Exception:
            logger.exception("Failed to repair staged Unreal launcher stub")

    def _resolve_unreal_working_dir(self, executable: Path) -> Path:
        packaged = (
            UNREAL_ROOT
            / "Environments"
            / "DTAMVisualization"
            / "Saved"
            / "StagedBuilds"
            / "Windows"
            / "DTAMVisualization.exe"
        )
        try:
            if packaged.is_file() and executable.resolve() == packaged.resolve():
                return packaged.parent
        except OSError:
            pass

        configured = str(self._config.unreal.working_dir or "").strip()
        if configured:
            return Path(configured).expanduser()

        resolved = str(executable.resolve())
        if "\\Binaries\\Win64\\" in resolved:
            return UNREAL_ROOT / "Environments" / "DTAMVisualization"
        return executable.parent

    def connect_airsim(self, host: Optional[str] = None, port: Optional[int] = None) -> Dict[str, Any]:
        status = self._bridge.connect(host=host, port=port)
        self._emit(_hub_event(
            kind="airsim", mid="connect",
            summary=f"AirSim connect -> {status.host}:{status.port} ok={status.connected}",
            detail=status.to_dict(),
        ))
        return status.to_dict()

    def disconnect_airsim(self) -> Dict[str, Any]:
        status = self._bridge.disconnect()
        return status.to_dict()

    def reconfigure_dtam(self, **kwargs: Any) -> Dict[str, Any]:
        ep = self._io.reconfigure(**kwargs)
        return ep.__dict__

    def update_streaming(
        self,
        *,
        module_status_hz: Optional[float] = None,
        camera_enabled: Optional[bool] = None,
        camera_name: Optional[str] = None,
        camera_image_type: Optional[int] = None,
        camera_hz: Optional[float] = None,
        camera_quality: Optional[int] = None,
        camera_vehicle: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            if module_status_hz is not None:
                self._streaming.module_status_hz = float(module_status_hz)
            if camera_enabled is not None:
                self._streaming.camera_enabled = bool(camera_enabled)
            if camera_name is not None:
                self._streaming.camera_name = str(camera_name)
            if camera_image_type is not None:
                self._streaming.camera_image_type = int(camera_image_type)
            if camera_hz is not None:
                self._streaming.camera_hz = min(
                    ICD_CAMERA_SNAPSHOT_MAX_HZ,
                    max(0.1, float(camera_hz)),
                )
            if camera_quality is not None:
                self._streaming.camera_quality = int(camera_quality)
            if camera_vehicle is not None:
                self._streaming.camera_vehicle = str(camera_vehicle)
            return self._streaming.__dict__.copy()

    def runtime_optimization_settings(self) -> Dict[str, Any]:
        opt = self._config.runtime_optimization
        return {
            "vehicle_status_apply_hz": float(opt.vehicle_status_apply_hz),
            "vehicle_status_apply_hz_by_vehicle_count": [
                dict(item) for item in list(opt.vehicle_status_apply_hz_by_vehicle_count or [])
                if isinstance(item, dict)
            ],
            "telemetry_hz": float(opt.telemetry_hz),
            "visual_state_hz": float(opt.visual_state_hz),
            "direct_camera_default_fps": float(opt.direct_camera_default_fps),
            "direct_camera_max_fps": float(opt.direct_camera_max_fps),
            "teststream_default_fps": float(opt.teststream_default_fps),
            "collision_poll_hz": float(self._config.collision.poll_hz),
            "pose_feedback_check_enabled": bool(self._config.collision.pose_feedback_check_enabled),
            "pose_feedback_publish_to_server": bool(self._config.collision.pose_feedback_publish_to_server),
            "pose_feedback_recommended_action": str(self._config.collision.pose_feedback_recommended_action or "none"),
            "pose_feedback_sample_hz": float(self._config.collision.pose_feedback_sample_hz),
        }

    def rendering_settings(self) -> Dict[str, Any]:
        rendering = self._config.rendering_performance
        return {
            "preset": str(rendering.preset or "balanced"),
            "maximum_screen_space_error": float(rendering.maximum_screen_space_error),
            "maximum_simultaneous_tile_loads": int(rendering.maximum_simultaneous_tile_loads),
            "maximum_cached_megabytes": int(rendering.maximum_cached_megabytes),
            "loading_descendant_limit": int(rendering.loading_descendant_limit),
            "culled_screen_space_error": float(rendering.culled_screen_space_error),
            "distance_fog_density": float(rendering.distance_fog_density),
            "distance_fog_start_distance_m": float(rendering.distance_fog_start_distance_m),
            "distance_fog_max_opacity": float(rendering.distance_fog_max_opacity),
            "frame_rate_limit": int(rendering.frame_rate_limit),
            "screen_percentage": int(rendering.screen_percentage),
            "scalability_level": int(rendering.scalability_level),
            "stream_camera_tile_loading": bool(rendering.stream_camera_tile_loading),
            "stream_camera_tile_loading_max_cameras": int(rendering.stream_camera_tile_loading_max_cameras),
            "stream_camera_tile_loading_refresh_s": float(rendering.stream_camera_tile_loading_refresh_s),
            "sky_light_realtime_capture": bool(rendering.sky_light_realtime_capture),
            "apply_on_launch": bool(rendering.apply_on_launch),
            "launch_exec_cmds": self._rendering_exec_cmds(),
            "runtime_apply_supported": True,
            "runtime_apply_scope": "renderer-cvars+cesium-runtime-command",
            "cesium_runtime_note": (
                "The VM API applies renderer CVars immediately and can call the Unreal "
                "dtam.ApplyRenderingSettings command for Cesium tile/fog/SkyLight runtime values. "
                "The command requires a rebuilt DT World executable that contains the Session 5 C++ bridge."
            ),
        }

    def update_rendering_settings(
        self,
        values: Optional[Dict[str, Any]] = None,
        *,
        preset: Optional[str] = None,
        apply_runtime: bool = False,
        apply_cesium_runtime: Optional[bool] = None,
        runtime_scope: str = "all",
        persistent: bool = False,
    ) -> Dict[str, Any]:
        values = dict(values or {})
        rendering = self._config.rendering_performance
        editable_fields = {
            "maximum_screen_space_error",
            "maximum_simultaneous_tile_loads",
            "maximum_cached_megabytes",
            "loading_descendant_limit",
            "culled_screen_space_error",
            "distance_fog_density",
            "distance_fog_start_distance_m",
            "distance_fog_max_opacity",
            "frame_rate_limit",
            "screen_percentage",
            "scalability_level",
            "stream_camera_tile_loading",
            "stream_camera_tile_loading_max_cameras",
            "stream_camera_tile_loading_refresh_s",
            "sky_light_realtime_capture",
            "apply_on_launch",
        }

        with self._lock:
            preset_value = str(preset if preset is not None else values.get("preset", "") or "").strip().lower()
            if preset_value:
                preset_defaults = rendering_preset_defaults(preset_value)
                rendering.preset = str(preset_defaults["preset"])
                if rendering.preset != "custom":
                    for key, value in preset_defaults.items():
                        if key != "preset" and hasattr(rendering, key):
                            setattr(rendering, key, value)

            changed_custom_field = False
            ignored_fields: List[Dict[str, str]] = []
            for key in editable_fields:
                if key not in values or values.get(key) is None:
                    continue
                raw_value = values.get(key)
                if key in {
                    "stream_camera_tile_loading",
                    "sky_light_realtime_capture",
                    "apply_on_launch",
                }:
                    parsed_bool = self._parse_rendering_bool(raw_value)
                    if parsed_bool is None:
                        ignored_fields.append({"field": key, "reason": "invalid boolean"})
                        continue
                    setattr(rendering, key, parsed_bool)
                    changed_custom_field = True
                elif key in {
                    "maximum_simultaneous_tile_loads",
                    "maximum_cached_megabytes",
                    "loading_descendant_limit",
                    "frame_rate_limit",
                    "screen_percentage",
                    "scalability_level",
                    "stream_camera_tile_loading_max_cameras",
                }:
                    limits = {
                        "maximum_simultaneous_tile_loads": (1, 16),
                        "maximum_cached_megabytes": (512, 8192),
                        "loading_descendant_limit": (1, 8),
                        "frame_rate_limit": (20, 60),
                        "screen_percentage": (50, 100),
                        "scalability_level": (0, 3),
                        "stream_camera_tile_loading_max_cameras": (1, 8),
                    }[key]
                    try:
                        parsed_int = int(raw_value)
                    except (TypeError, ValueError):
                        ignored_fields.append({"field": key, "reason": "invalid integer"})
                        continue
                    setattr(rendering, key, max(limits[0], min(limits[1], parsed_int)))
                    changed_custom_field = True
                else:
                    limits_f = {
                        "maximum_screen_space_error": (32.0, 256.0),
                        "culled_screen_space_error": (128.0, 2048.0),
                        "distance_fog_density": (0.0, 0.005),
                        "distance_fog_start_distance_m": (100.0, 5000.0),
                        "distance_fog_max_opacity": (0.0, 1.0),
                        "stream_camera_tile_loading_refresh_s": (0.1, 10.0),
                    }[key]
                    try:
                        parsed_float = float(raw_value)
                    except (TypeError, ValueError):
                        ignored_fields.append({"field": key, "reason": "invalid number"})
                        continue
                    setattr(rendering, key, max(limits_f[0], min(limits_f[1], parsed_float)))
                    changed_custom_field = True

            if changed_custom_field and not preset_value:
                rendering.preset = "custom"

            settings = self.rendering_settings()
            save_path = ""
            unreal_config_paths: List[str] = []
            save_error = ""
            if persistent:
                try:
                    save_path = str(save_config(self._config))
                    unreal_config_paths = self._persist_rendering_to_unreal_configs()
                except Exception as exc:
                    save_error = str(exc)

        runtime_scope_normalized = str(runtime_scope or "all").strip().lower()
        runtime_scope_error = ""
        if runtime_scope_normalized not in ("renderer", "cesium", "all"):
            runtime_scope_error = (
                f"invalid runtime_scope={runtime_scope!r}; expected renderer, cesium, or all"
            )
        should_apply_renderer = bool(apply_runtime) and runtime_scope_normalized in ("renderer", "all")
        should_apply_cesium = (
            bool(apply_runtime)
            and runtime_scope_normalized in ("cesium", "all")
            and (bool(apply_cesium_runtime) if apply_cesium_runtime is not None else True)
        )
        apply_result: Dict[str, Any] = {
            "requested": bool(apply_runtime),
            "runtime_scope": runtime_scope_normalized,
            "applied": False,
            "error": runtime_scope_error,
            "renderer": {"requested": should_apply_renderer, "applied": False},
            "cesium": {"requested": should_apply_cesium, "applied": False},
        }
        if apply_runtime and not runtime_scope_error:
            renderer_result = (
                self._apply_renderer_console_commands()
                if should_apply_renderer
                else {"requested": False, "applied": False, "skipped": True}
            )
            cesium_result = (
                self._apply_cesium_runtime_settings()
                if should_apply_cesium
                else {"requested": False, "applied": False, "skipped": True}
            )
            requested_any = should_apply_renderer or should_apply_cesium
            apply_result = {
                "requested": True,
                "runtime_scope": runtime_scope_normalized,
                "applied": requested_any and (
                    (not should_apply_renderer or bool(renderer_result.get("applied")))
                    and (not should_apply_cesium or bool(cesium_result.get("applied")))
                ),
                "skipped": not requested_any,
                "error": "",
                "renderer": renderer_result,
                "cesium": cesium_result,
            }

        operation_ok = not save_error
        if apply_runtime:
            operation_ok = operation_ok and bool(apply_result.get("applied"))
        warnings = []
        if ignored_fields:
            warnings.append("Some rendering fields were ignored because they failed validation.")
        if runtime_scope_error:
            warnings.append(runtime_scope_error)
        if apply_runtime and not apply_result.get("applied"):
            warnings.append("Runtime rendering apply was requested but did not complete successfully.")
        if save_error:
            warnings.append(f"Failed to persist rendering settings: {save_error}")

        out = {
            "ok": operation_ok,
            "persistent": bool(persistent),
            "save_path": save_path,
            "save_error": save_error,
            "unreal_config_paths": unreal_config_paths,
            "ignored_fields": ignored_fields,
            "warnings": warnings,
            "apply_runtime": apply_result,
            **settings,
        }
        self._emit(_hub_event(
            kind="airsim",
            mid="rendering-performance",
            summary=(
                "rendering settings updated "
                f"preset={out['preset']} fps={out['frame_rate_limit']} "
                f"scale={out['screen_percentage']}%"
            ),
            detail=out,
        ))
        return out

    def _apply_rendering_console_commands(self) -> Dict[str, Any]:
        return self._apply_renderer_console_commands()

    def _apply_renderer_console_commands(self) -> Dict[str, Any]:
        commands = self._rendering_exec_cmds()
        results = [self._bridge.run_console_command(command) for command in commands]
        ok_count = sum(1 for item in results if item.get("ok"))
        return {
            "requested": True,
            "applied": ok_count == len(results),
            "ok_count": ok_count,
            "total": len(results),
            "commands": results,
            "note": "Runtime renderer apply affects safe Unreal CVars only.",
        }

    def _cesium_runtime_command(self) -> str:
        rendering = self._config.rendering_performance
        args = {
            "Preset": str(rendering.preset or "custom"),
            "MaximumScreenSpaceError": f"{float(rendering.maximum_screen_space_error):.3f}",
            "MaximumSimultaneousTileLoads": str(int(rendering.maximum_simultaneous_tile_loads)),
            "MaximumCachedMegabytes": str(int(rendering.maximum_cached_megabytes)),
            "LoadingDescendantLimit": str(int(rendering.loading_descendant_limit)),
            "CulledScreenSpaceError": f"{float(rendering.culled_screen_space_error):.3f}",
            "bForbidHoles": "true",
            "bEnableFrustumCulling": "true",
            "bEnableFogCulling": "false",
            "bEnforceCulledScreenSpaceError": "false",
            "bEnableStreamCameraTileLoading": "true" if rendering.stream_camera_tile_loading else "false",
            "StreamCameraTileLoadingMaxCameras": str(int(rendering.stream_camera_tile_loading_max_cameras)),
            "StreamCameraTileLoadingRefreshSeconds": f"{float(rendering.stream_camera_tile_loading_refresh_s):.3f}",
            "bEnableDistanceFog": "false",
            "DistanceFogDensity": "0.00000000",
            "DistanceFogStartDistanceMeters": "5000.000",
            "DistanceFogMaxOpacity": "0.000",
            "FrameRateLimit": str(int(rendering.frame_rate_limit)),
            "ScreenPercentage": str(int(rendering.screen_percentage)),
            "ScalabilityLevel": str(int(rendering.scalability_level)),
            "bSkyLightRealTimeCapture": "true" if rendering.sky_light_realtime_capture else "false",
        }
        return "dtam.ApplyRenderingSettings " + " ".join(
            f"{key}={value}" for key, value in args.items()
        )

    def _apply_cesium_runtime_settings(self) -> Dict[str, Any]:
        command = self._cesium_runtime_command()
        result = self._bridge.run_console_command(command)
        return {
            "requested": True,
            "applied": bool(result.get("ok")),
            "command": command,
            "result": result,
            "note": (
                "Applies Cesium tile/fog/SkyLight settings through the Unreal "
                "dtam.ApplyRenderingSettings console command. Requires the Session 5 C++ bridge in the DT World EXE."
            ),
        }

    def _persist_rendering_to_unreal_configs(self) -> List[str]:
        values = self._unreal_runtime_cesium_launch_values()
        paths = [
            FRAMEWORK_ROOT / "VisualizationModule_Source" / "Unreal" / "Environments" / "DTAMVisualization" / "Config" / "DefaultGame.ini",
            UNREAL_ROOT / "Environments" / "DTAMVisualization" / "Config" / "DefaultGame.ini",
            UNREAL_ROOT / "Environments" / "DTAMVisualization" / "Saved" / "StagedBuilds" / "Windows" / "DTAMVisualization" / "Saved" / "Config" / "Windows" / "Game.ini",
            UNREAL_ROOT / "Environments" / "DTAMVisualization" / "Saved" / "StagedBuilds" / "Windows" / "DTAMVisualization" / "Config" / "DefaultGame.ini",
        ]
        written: List[str] = []
        for path in paths:
            try:
                self._write_unreal_ini_section_values(
                    path,
                    "[/Script/DTAMVisualization.DTAMVisualizationCesiumSettings]",
                    values,
                )
                written.append(str(path))
            except Exception:
                logger.debug("failed to persist rendering settings to %s", path, exc_info=True)
        return written

    @staticmethod
    def _write_unreal_ini_section_values(path: Path, section: str, values: Dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = path.read_text(encoding="utf-8-sig") if path.exists() else ""
        lines = text.splitlines()
        section_index = next((i for i, line in enumerate(lines) if line.strip().lower() == section.lower()), -1)
        if section_index < 0:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(section)
            section_index = len(lines) - 1
        section_end = len(lines)
        for i in range(section_index + 1, len(lines)):
            stripped = lines[i].strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section_end = i
                break

        key_to_index: Dict[str, int] = {}
        for i in range(section_index + 1, section_end):
            stripped = lines[i].strip()
            if "=" not in stripped or stripped.startswith(";"):
                continue
            key = stripped.split("=", 1)[0].strip().lower()
            key_to_index[key] = i

        insert_at = section_end
        for key, value in values.items():
            index = key_to_index.get(key.lower())
            line = f"{key}={value}"
            if index is None:
                lines.insert(insert_at, line)
                insert_at += 1
            else:
                lines[index] = line
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def update_runtime_optimization(
        self,
        *,
        vehicle_status_apply_hz: Optional[float] = None,
        vehicle_status_apply_hz_by_vehicle_count: Optional[List[Dict[str, Any]]] = None,
        telemetry_hz: Optional[float] = None,
        visual_state_hz: Optional[float] = None,
        direct_camera_default_fps: Optional[float] = None,
        direct_camera_max_fps: Optional[float] = None,
        teststream_default_fps: Optional[float] = None,
        collision_poll_hz: Optional[float] = None,
        pose_feedback_check_enabled: Optional[bool] = None,
        pose_feedback_publish_to_server: Optional[bool] = None,
        pose_feedback_recommended_action: Optional[str] = None,
        pose_feedback_sample_hz: Optional[float] = None,
    ) -> Dict[str, Any]:
        opt = self._config.runtime_optimization
        with self._lock:
            if vehicle_status_apply_hz is not None:
                opt.vehicle_status_apply_hz = max(1.0, min(60.0, float(vehicle_status_apply_hz)))
            if vehicle_status_apply_hz_by_vehicle_count is not None:
                cleaned: List[Dict[str, Any]] = []
                for item in list(vehicle_status_apply_hz_by_vehicle_count or []):
                    if not isinstance(item, dict):
                        continue
                    try:
                        min_count = max(0, int(item.get("min", 0)))
                        max_count = max(min_count, int(item.get("max", 999)))
                        hz = max(1.0, min(60.0, float(item.get("hz", opt.vehicle_status_apply_hz))))
                    except (TypeError, ValueError):
                        continue
                    cleaned.append({"min": min_count, "max": max_count, "hz": hz})
                if cleaned:
                    opt.vehicle_status_apply_hz_by_vehicle_count = cleaned
            if telemetry_hz is not None:
                opt.telemetry_hz = max(0.0, min(60.0, float(telemetry_hz)))
            if visual_state_hz is not None:
                opt.visual_state_hz = max(0.0, min(60.0, float(visual_state_hz)))
            if direct_camera_default_fps is not None:
                opt.direct_camera_default_fps = max(0.2, min(30.0, float(direct_camera_default_fps)))
            if direct_camera_max_fps is not None:
                opt.direct_camera_max_fps = max(0.2, min(30.0, float(direct_camera_max_fps)))
            if opt.direct_camera_default_fps > opt.direct_camera_max_fps:
                opt.direct_camera_default_fps = opt.direct_camera_max_fps
            if teststream_default_fps is not None:
                opt.teststream_default_fps = max(0.2, min(30.0, float(teststream_default_fps)))
            if collision_poll_hz is not None:
                self._config.collision.poll_hz = max(0.2, min(60.0, float(collision_poll_hz)))
            if pose_feedback_check_enabled is not None:
                self._config.collision.pose_feedback_check_enabled = bool(pose_feedback_check_enabled)
            if pose_feedback_publish_to_server is not None:
                self._config.collision.pose_feedback_publish_to_server = bool(pose_feedback_publish_to_server)
            if pose_feedback_recommended_action is not None:
                action = str(pose_feedback_recommended_action or "none").strip().lower()
                self._config.collision.pose_feedback_recommended_action = action or "none"
            if pose_feedback_sample_hz is not None:
                self._config.collision.pose_feedback_sample_hz = max(0.1, min(30.0, float(pose_feedback_sample_hz)))
            settings = self.runtime_optimization_settings()

        self._emit(_hub_event(
            kind="airsim",
            mid="runtime-optimization",
            summary=(
                "runtime optimization updated "
                f"apply={settings['vehicle_status_apply_hz']}Hz "
                f"telemetry={settings['telemetry_hz']}Hz visual={settings['visual_state_hz']}Hz"
            ),
            detail=settings,
        ))
        return {"ok": True, "persistent": False, **settings}

    def direct_camera_default_fps(self, requested_fps: Optional[float] = None) -> float:
        opt = self._config.runtime_optimization
        default_fps = max(0.2, min(30.0, float(opt.direct_camera_default_fps or 20.0)))
        max_fps = max(0.2, min(30.0, float(opt.direct_camera_max_fps or 30.0)))
        if requested_fps is None:
            return min(default_fps, max_fps)
        return max(0.2, min(max_fps, float(requested_fps or default_fps)))

    def update_collision_mode(
        self,
        *,
        ignore_collisions: Optional[bool] = None,
        collision_poll_hz: Optional[float] = None,
        pose_feedback_check_enabled: Optional[bool] = None,
        pose_feedback_publish_to_server: Optional[bool] = None,
        pose_feedback_recommended_action: Optional[str] = None,
        pose_feedback_error_threshold_m: Optional[float] = None,
        pose_feedback_sample_hz: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Runtime AirSim collision/sweep diagnostics settings.

        ``ignore_collisions=True`` keeps the legacy teleport-style 4001 replay.
        ``False`` asks AirSim/Unreal to use sweep movement in
        ``simSetVehiclePose``.  The pose feedback check is diagnostic-only and
        does not call ``simGetCollisionInfo`` so it cannot steal 4103 events
        from the dedicated collision polling loop.
        """
        bridge_status: Dict[str, Any] = {}
        with self._lock:
            if ignore_collisions is not None:
                self._config.airsim.ignore_collisions = bool(ignore_collisions)
                bridge_status = self._bridge.set_ignore_collisions(bool(ignore_collisions))
            if collision_poll_hz is not None:
                self._config.collision.poll_hz = max(0.2, min(60.0, float(collision_poll_hz)))
            if pose_feedback_check_enabled is not None:
                self._config.collision.pose_feedback_check_enabled = bool(pose_feedback_check_enabled)
            if pose_feedback_publish_to_server is not None:
                self._config.collision.pose_feedback_publish_to_server = bool(pose_feedback_publish_to_server)
            if pose_feedback_recommended_action is not None:
                action = str(pose_feedback_recommended_action or "none").strip().lower()
                self._config.collision.pose_feedback_recommended_action = action or "none"
            if pose_feedback_error_threshold_m is not None:
                self._config.collision.pose_feedback_error_threshold_m = max(
                    0.05,
                    float(pose_feedback_error_threshold_m),
                )
            if pose_feedback_sample_hz is not None:
                self._config.collision.pose_feedback_sample_hz = max(
                    0.1,
                    min(30.0, float(pose_feedback_sample_hz)),
                )

            out = {
                "ok": True,
                "ignore_collisions": bool(self._config.airsim.ignore_collisions),
                "collision_mode": "teleport" if self._config.airsim.ignore_collisions else "sweep",
                "collision_poll_hz": float(self._config.collision.poll_hz),
                "pose_feedback_check_enabled": bool(self._config.collision.pose_feedback_check_enabled),
                "pose_feedback_publish_to_server": bool(self._config.collision.pose_feedback_publish_to_server),
                "pose_feedback_recommended_action": str(self._config.collision.pose_feedback_recommended_action or "none"),
                "pose_feedback_error_threshold_m": float(self._config.collision.pose_feedback_error_threshold_m),
                "pose_feedback_sample_hz": float(self._config.collision.pose_feedback_sample_hz),
                "bridge": bridge_status,
                "persistent": False,
            }

        self._emit(_hub_event(
            kind="airsim",
            mid="collision-mode",
            summary=f"AirSim collision mode -> {out['collision_mode']}",
            detail=out,
        ))
        return out

    def update_vehicle_map(self, mapping: Dict[str, str]) -> Dict[str, str]:
        self._bridge.update_vehicle_map(mapping)
        return self._bridge.get_vehicle_map()

    def list_airsim_vehicles(self) -> Dict[str, Any]:
        catalog = self._bridge.list_vehicles()
        catalog["unreal"] = self.unreal_status()
        return catalog

    def capture_camera_once(self) -> Dict[str, Any]:
        """Capture the current camera frame and send it as 4101."""
        self._capture_and_send_camera()
        return {"ok": True}

    def capture_direct_camera_frame(
        self,
        *,
        aircraft_id: str = "",
        camera_name: str = "front_center",
        image_type: int = 0,
        vehicle_name: str = "",
        quality: int = 60,
    ) -> tuple[bytes, Dict[str, Any]]:
        """Capture one JPEG frame without sending MSG 4101.

        This is the media-plane source for on-demand MJPEG streaming. Keeping it
        separate from ``_capture_and_send_camera`` prevents high-rate video from
        being forwarded through IntegrationHub.
        """
        safe_quality = max(10, min(95, int(quality or 60)))
        if not str(vehicle_name or "").strip() and str(aircraft_id or "").strip():
            vehicle_name = self._bridge.resolve_vehicle_name(aircraft_id)
        return self._bridge.capture_camera_frame(
            camera_name=str(camera_name or "front_center"),
            image_type=int(image_type or 0),
            vehicle_name=str(vehicle_name or ""),
            quality=safe_quality,
        )

    def capture_vpo_camera_frame(
        self,
        *,
        aircraft_id: str = "",
        camera_name: str = "",
        image_type: int = 0,
        vehicle_name: str = "",
        quality: int = 70,
        camera_id: str = "",
    ) -> tuple[bytes, Dict[str, Any]]:
        """Capture one fixed VPO vertiport CCTV frame without publishing MSG 4101."""
        del aircraft_id, image_type, vehicle_name
        safe_camera_id = str(camera_id or camera_name or "").strip()
        safe_quality = max(10, min(95, int(quality or 70)))
        return self._bridge.capture_vpo_camera_frame(safe_camera_id, quality=safe_quality)

    def ensure_direct_camera_stream(
        self,
        *,
        aircraft_id: str = "UAM0001",
        vehicle_name: str = "",
        camera_name: str = "front_center",
        image_type: int = 0,
        fps: Optional[float] = None,
        quality: int = 60,
    ) -> CameraStreamWorker:
        """Start or reuse a cached producer for direct MJPEG media-plane output."""
        safe_fps = self.direct_camera_default_fps(fps)
        safe_quality = max(10, min(95, int(quality or 60)))
        spec = CameraStreamSpec(
            aircraft_id=str(aircraft_id or "UAM0001"),
            vehicle_name=str(vehicle_name or ""),
            camera_name=str(camera_name or "front_center"),
            image_type=int(image_type or 0),
            fps=safe_fps,
            quality=safe_quality,
        )
        return self._camera_streams.ensure_stream(spec)

    def camera_stream_stats(self) -> Dict[str, Any]:
        return self._camera_streams.stats()

    def ensure_vpo_camera_stream(
        self,
        *,
        camera_id: str,
        fps: float = 8.0,
        quality: int = 65,
    ) -> CameraStreamWorker:
        """Start or reuse a cached producer for one fixed VPO SceneCapture camera."""
        safe_camera_id = str(camera_id or "").strip()
        safe_fps = max(0.2, min(12.0, float(fps or 8.0)))
        safe_quality = max(10, min(95, int(quality or 65)))
        spec = CameraStreamSpec(
            aircraft_id="VPO",
            vehicle_name="",
            camera_name=safe_camera_id,
            image_type=0,
            fps=safe_fps,
            quality=safe_quality,
        )
        return self._vpo_camera_streams.ensure_stream(spec)

    def vpo_camera_stream_stats(self) -> Dict[str, Any]:
        return self._vpo_camera_streams.stats()

    def camera_stream_descriptor(
        self,
        *,
        base_url: str,
        vehicle_id: str = "UAM0001",
        vehicle_name: str = "",
        camera_name: str = "front_center",
        image_type: int = 0,
        fps: Optional[float] = None,
        quality: int = 60,
        status: str = "available",
        note: str = "",
    ) -> Dict[str, Any]:
        safe_fps = self.direct_camera_default_fps(fps)
        safe_quality = max(10, min(95, int(quality or 60)))
        safe_vehicle_id = str(vehicle_id or "UAM0001")
        safe_camera = str(camera_name or "front_center")
        safe_vehicle_name = str(vehicle_name or "")
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

        if self._config.pixel_streaming.enabled:
            ps = self._config.pixel_streaming
            stream_id = f"{safe_vehicle_id}-{safe_camera}-pixelstreaming"
            return {
                "message_id": 4102,
                "message_name": "Camera Stream Descriptor",
                "timestamp": timestamp,
                "stream_id": stream_id,
                "vehicle_id": safe_vehicle_id,
                "airsim_vehicle_name": safe_vehicle_name,
                "camera_name": safe_camera,
                "stream_type": "webrtc",
                "transport": "webrtc",
                "codec": "h264",
                "encoding": "pixel-streaming",
                "url": ps.player_url,
                "embed_url": ps.player_url,
                "player_url": ps.player_url,
                "streamer_url": ps.streamer_url,
                "control_mid": "5002",
                "fps": 0,
                "quality": 0,
                "width": 0,
                "height": 0,
                "status": str(status or "available"),
                "expires_at": None,
                "source": "unreal",
                "media_plane": "unreal-pixel-streaming",
                "note": note or "Unreal Pixel Streaming media plane. Video frames are encoded inside Unreal and delivered by WebRTC; ICD 4102 only announces the player URL.",
            }

        stream_id = f"{safe_vehicle_id}-{safe_camera}-type{int(image_type or 0)}-mjpeg"
        query = urlencode({
            "vehicle_id": safe_vehicle_id,
            "vehicle_name": safe_vehicle_name,
            "camera_name": safe_camera,
            "image_type": int(image_type or 0),
            "fps": safe_fps,
            "quality": safe_quality,
        })
        return {
            "message_id": 4102,
            "message_name": "Camera Stream Descriptor",
            "timestamp": timestamp,
            "stream_id": stream_id,
            "vehicle_id": safe_vehicle_id,
            "airsim_vehicle_name": safe_vehicle_name,
            "camera_name": safe_camera,
            "image_type": int(image_type or 0),
            "stream_type": "mjpeg",
            "transport": "http",
            "codec": "mjpeg",
            "encoding": "jpeg",
            "url": f"{base_url.rstrip('/')}/api/media/stream?{query}",
            "control_mid": "5002",
            "fps": safe_fps,
            "quality": safe_quality,
            "width": DEFAULT_DIRECT_CAMERA_WIDTH if safe_camera == "front_center" and int(image_type or 0) == 0 else 0,
            "height": DEFAULT_DIRECT_CAMERA_HEIGHT if safe_camera == "front_center" and int(image_type or 0) == 0 else 0,
            "status": str(status or "available"),
            "expires_at": None,
            "source": "airsim",
            "media_plane": "direct-mjpeg",
            "cache_policy": "latest-frame-only",
            "note": note or "Direct VisualizationModule MJPEG media stream from one AirSim/Cosys-AirSim producer and an in-memory latest-frame cache.",
        }

    def vpo_camera_stream_descriptor(
        self,
        *,
        base_url: str,
        camera_id: str,
        vertiport_id: str = "",
        vertiport_name: str = "",
        fps: float = 8.0,
        quality: int = 65,
        status: str = "available",
        note: str = "",
    ) -> Dict[str, Any]:
        safe_camera_id = str(camera_id or "").strip()
        safe_vertiport_id = str(vertiport_id or "").strip()
        safe_fps = max(0.2, min(12.0, float(fps or 8.0)))
        safe_quality = max(10, min(95, int(quality or 65)))
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        stream_owner = safe_vertiport_id or "VPO"
        stream_id = f"{stream_owner}-{safe_camera_id}-vpo-mjpeg"
        query = urlencode({
            "camera_id": safe_camera_id,
            "fps": safe_fps,
            "quality": safe_quality,
        })
        return {
            "message_id": 4102,
            "message_name": "Camera Stream Descriptor",
            "timestamp": timestamp,
            "stream_id": stream_id,
            "vehicle_id": stream_owner,
            "airsim_vehicle_name": "",
            "camera_name": safe_camera_id,
            "camera_id": safe_camera_id,
            "vertiport_id": safe_vertiport_id,
            "vertiport_name": str(vertiport_name or ""),
            "stream_type": "mjpeg",
            "transport": "http",
            "codec": "mjpeg",
            "encoding": "jpeg",
            "url": f"{base_url.rstrip('/')}/api/vpo/camera-stream?{query}",
            "control_mid": "",
            "fps": safe_fps,
            "quality": safe_quality,
            "width": 960,
            "height": 540,
            "status": str(status or "available"),
            "expires_at": None,
            "source": "unreal_scene_capture",
            "media_plane": "direct-vpo-mjpeg",
            "cache_policy": "latest-frame-only",
            "note": note or "On-demand VPO vertiport CCTV stream. The HTTP MJPEG bytes bypass IntegrationHub; ICD 4102 only announces this media URL.",
        }

    def publish_camera_stream_descriptor(self, descriptor: Dict[str, Any]) -> Dict[str, Any]:
        res = self._io.send_camera_stream_descriptor(descriptor)
        self._emit(_hub_event(
            kind="tx", mid="4102",
            summary=f"4102 -> {descriptor.get('stream_id') or descriptor.get('url')}",
            detail=res,
        ))
        return res

    def control_camera(
        self,
        *,
        aircraft_id: str = "",
        camera_name: str,
        vehicle_name: str = "",
        yaw_delta_deg: float = 0.0,
        pitch_delta_deg: float = 0.0,
        focal_length_delta: float = 0.0,
    ) -> Dict[str, Any]:
        if not str(vehicle_name or "").strip() and str(aircraft_id or "").strip():
            vehicle_name = self._bridge.resolve_vehicle_name(aircraft_id)
        result = self._bridge.adjust_camera_view(
            camera_name=camera_name,
            vehicle_name=vehicle_name,
            yaw_delta_deg=yaw_delta_deg,
            pitch_delta_deg=pitch_delta_deg,
            focal_length_delta=focal_length_delta,
        )
        self._emit(HubEvent(
            ts=time.time(),
            kind="airsim" if result.get("ok") else "error",
            mid="camera-control",
            summary=(
                f"camera {camera_name} yaw={float(yaw_delta_deg):+.1f} "
                f"pitch={float(pitch_delta_deg):+.1f} focal={float(focal_length_delta):+.1f}"
            ),
            detail=result,
        ))
        return result

    # Error helpers
    def performance_snapshot(self, *, include_streams: bool = True) -> Dict[str, Any]:
        """Return compact performance counters for Session 1 profiling."""
        out: Dict[str, Any] = {
            "enabled": bool(self._config.metrics.enabled),
            "log_interval_sec": float(self._config.metrics.log_interval_sec),
            "history_size": int(self._config.metrics.history_size),
            "log_path": str(self._metrics_log_path),
            "vehicle_status_pipeline": self._vehicle_status_pipeline_stats(),
            "collision": self._collision_stats(),
            "camera_snapshot": self._camera_snapshot_stats(),
            "runtime_optimization": self.runtime_optimization_settings(),
            "rendering_performance": self.rendering_settings(),
            "unreal": {
                "profile_mode": str(self._config.unreal.profile_mode or "off"),
                "profile_args": list(self._config.unreal.profile_args or []),
                "profile_exec_cmds": list(self._config.unreal.profile_exec_cmds or []),
            },
        }
        if include_streams:
            out["media_streams"] = self._camera_streams.stats()
            out["vpo_media_streams"] = self._vpo_camera_streams.stats()
        return out

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            events = [e.to_dict() for e in self._events]
        return {
            "started_at": self._started_at,
            "uptime_s": time.time() - self._started_at if self._started_at else 0.0,
            "airsim": self._bridge.status().to_dict(),
            "airsim_config": {
                "host": self._config.airsim.host,
                "port": self._config.airsim.port,
                "vehicle_prefix": self._config.airsim.vehicle_prefix,
                "ignore_collisions": self._config.airsim.ignore_collisions,
                "vehicle_map": self._bridge.get_vehicle_map(),
            },
            "dtam": self._io.stats(),
            "vehicle_status_pipeline": self._vehicle_status_pipeline_stats(),
            "collision": self._collision_stats(),
            "camera_snapshot": self._camera_snapshot_stats(),
            "dtam_endpoint": self._io.endpoint().__dict__,
            "streaming": self._streaming.__dict__,
            "runtime_optimization": self.runtime_optimization_settings(),
            "media_streams": self._camera_streams.stats(),
            "vpo_media_streams": self._vpo_camera_streams.stats(),
            "unreal": self.unreal_status(),
            "performance": self.performance_snapshot(include_streams=False),
            "mission_guides": {
                "visible": self._mission_guides_visible,
                "path": str(MISSION_GUIDE_PATH),
                "toggle_key": "U",
            },
            "events": events,
        }

    def health_snapshot(self) -> Dict[str, Any]:
        """Return a compact status payload for readiness/runtime polling.

        The full ``snapshot`` endpoint intentionally includes GUI event history
        and the last received DTAM payloads.  During live operation those fields
        can contain large 4001/5001 messages, so OperationModule readiness
        checks should use this lightweight variant instead of blocking on the
        full GUI state serialization.
        """
        with self._lock:
            event_count = len(self._events)
        dtam_stats = self._io.stats(include_payload=False)
        return {
            "ok": True,
            "started_at": self._started_at,
            "uptime_s": time.time() - self._started_at if self._started_at else 0.0,
            "airsim": self._bridge.status().to_dict(),
            "dtam": dtam_stats,
            "vehicle_status_pipeline": self._vehicle_status_pipeline_stats(),
            "collision": self._collision_stats(),
            "camera_snapshot": self._camera_snapshot_stats(),
            "runtime_optimization": self.runtime_optimization_settings(),
            "unreal": self.unreal_status(),
            "mission_guides": {
                "visible": self._mission_guides_visible,
                "path": str(MISSION_GUIDE_PATH),
                "toggle_key": "U",
            },
            "events_count": event_count,
        }

    # Event broadcast
    def _emit(self, evt: HubEvent) -> None:
        with self._lock:
            self._events.append(evt)
        hook = self.on_event
        if hook is not None:
            try:
                hook(evt)
            except Exception:
                logger.exception("on_event hook raised")

    def _emit_mission_guides(self, mid: str) -> None:
        if not self._mission_guides_visible:
            result = {"applied": 0, "skipped": 0, "visible": False, "errors": []}
        else:
            result = self._bridge.apply_mission_guides_from_file(MISSION_GUIDE_PATH)
        self._emit(_hub_event(
            kind="airsim", mid=mid or "mission-guide",
            summary=f"mission guide -> simPlotLineStrip x{result.get('applied', 0)}",
            detail=result,
        ))

    def set_mission_guides_visible(self, visible: bool) -> Dict[str, Any]:
        self._mission_guides_visible = bool(visible)
        if self._mission_guides_visible:
            result = self._bridge.apply_mission_guides_from_file(MISSION_GUIDE_PATH)
            action = "show"
        else:
            result = self._bridge.clear_mission_guides()
            action = "hide"
        detail = {"visible": self._mission_guides_visible, **result}
        self._emit(HubEvent(
            ts=time.time(),
            kind="airsim" if not result.get("errors") else "error",
            mid="mission-guide",
            summary=f"mission guide {action}",
            detail=detail,
        ))
        return detail

    def toggle_mission_guides(self) -> Dict[str, Any]:
        return self.set_mission_guides_visible(not self._mission_guides_visible)

    def _poll_mission_guide_toggle(self, now: float) -> None:
        down = _is_key_down(MISSION_GUIDE_TOGGLE_VK)
        if not down:
            self._mission_guide_key_down = False
            return
        if self._mission_guide_key_down or now - self._last_mission_guide_toggle_ts < 0.35:
            return

        self._mission_guide_key_down = True
        self._last_mission_guide_toggle_ts = now
        self.toggle_mission_guides()

def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _is_key_down(vk_code: int) -> bool:
    try:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        return bool(user32.GetAsyncKeyState(int(vk_code)) & 0x8000)
    except Exception:
        return False


def _is_tcp_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((str(host), int(port)), timeout=0.2):
            return True
    except OSError:
        return False


def _url_host(url: str) -> str:
    parsed = urlparse(str(url or ""))
    return parsed.hostname or "127.0.0.1"

__all__ = ["VisualizationManager", "HubEvent"]
