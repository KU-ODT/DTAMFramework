"""Telemetry receiver/cache for the VFDS/KP2A dispatch server.

The VFDS server broadcasts one JSON object per aircraft on
``/api/v1/ws/live`` and also exposes the latest cache through
``GET /api/v1/telemetry``.  This module keeps the VehicleModule side
dependency-light: WebSocket support is optional and polling remains the
guaranteed fallback.
"""

from __future__ import annotations

import json
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .vfds_client import VfdsMissionClient


class VfdsTelemetryReceiver:
    def __init__(
        self,
        client: VfdsMissionClient,
        *,
        poll_period_s: float = 0.25,
        stale_after_s: float = 2.0,
        prefer_websocket: bool = True,
    ) -> None:
        self.client = client
        self.poll_period_s = max(0.05, float(poll_period_s))
        self.stale_after_s = max(0.25, float(stale_after_s))
        self.prefer_websocket = bool(prefer_websocket)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._latest: Dict[str, Dict[str, Any]] = {}
        self._last_error = ""
        self._last_source = ""
        self._last_poll_result: Dict[str, Any] = {}
        self._last_source_ts_s: Dict[str, float] = {}
        self._ignore_before_source_ts_s: Dict[str, float] = {}
        self._global_ignore_before_source_ts_s = 0.0
        self._ws_connected = False
        self._ws_available = False
        self._base_backoff_s = 0.25
        self._max_backoff_s = 5.0
        self._ws_backoff_s = self._base_backoff_s
        self._poll_backoff_s = self._base_backoff_s
        self._next_ws_attempt_s = 0.0
        self._next_poll_attempt_s = 0.0
        self.received_count = 0
        self.dropped_count = 0
        self.poll_count = 0
        self.ws_message_count = 0
        self.error_count = 0

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, name="dtam-vfds-telemetry", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        with self._lock:
            if self._thread is thread:
                self._thread = None
            self._ws_connected = False

    def clear(self, aircraft_id: str = "") -> None:
        vehicle_key = str(aircraft_id or "").strip()
        with self._lock:
            if not vehicle_key or vehicle_key.lower() in {"all", "*"}:
                self._latest.clear()
                self._last_source_ts_s.clear()
            else:
                self._latest.pop(vehicle_key, None)
                self._last_source_ts_s.pop(vehicle_key, None)

    def mark_reset(self, aircraft_id: str = "", *, source_epoch_s: Optional[float] = None) -> None:
        """Clear cache and drop telemetry whose source timestamp predates reset.

        VFDS's `/api/v1/telemetry` snapshot can still contain the last frame from
        the previous run immediately after DTAM reset/delete.  Clearing the local
        cache alone is not enough because the next poll would ingest that stale
        remote snapshot with a fresh arrival time.  This marker rejects records
        whose own `ts` is older than the reset wall-clock epoch.
        """
        threshold = float(source_epoch_s if source_epoch_s is not None else time.time())
        vehicle_key = str(aircraft_id or "").strip()
        with self._lock:
            if not vehicle_key or vehicle_key.lower() in {"all", "*"}:
                self._latest.clear()
                self._last_source_ts_s.clear()
                self._global_ignore_before_source_ts_s = max(
                    self._global_ignore_before_source_ts_s,
                    threshold,
                )
            else:
                self._latest.pop(vehicle_key, None)
                self._last_source_ts_s.pop(vehicle_key, None)
                self._ignore_before_source_ts_s[vehicle_key] = max(
                    self._ignore_before_source_ts_s.get(vehicle_key, 0.0),
                    threshold,
                )

    def ingest(self, payload: Any, *, source: str = "manual") -> int:
        """Ingest VFDS telemetry JSON.  Returns number of aircraft records stored."""
        count = 0
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception as exc:
                self._record_error(f"JSONDecodeError: {exc}")
                return 0
        records = self._extract_records(payload)
        now = time.monotonic()
        with self._lock:
            for record in records:
                if not isinstance(record, dict):
                    continue
                aircraft_id = str(
                    record.get("aircraftId")
                    or record.get("aircraft_id")
                    or record.get("vehicleId")
                    or ""
                ).strip()
                if not aircraft_id:
                    continue
                source_ts_s = _source_ts_to_epoch(record.get("ts"))
                ignore_before_s = max(
                    self._global_ignore_before_source_ts_s,
                    self._ignore_before_source_ts_s.get(aircraft_id, 0.0),
                )
                if (
                    source_ts_s is not None
                    and ignore_before_s > 0.0
                    and source_ts_s < ignore_before_s - 1e-6
                ):
                    self.dropped_count += 1
                    continue
                previous_ts_s = self._last_source_ts_s.get(aircraft_id)
                if (
                    source_ts_s is not None
                    and previous_ts_s is not None
                    and source_ts_s < previous_ts_s - 1e-6
                ):
                    self.dropped_count += 1
                    continue
                stored = deepcopy(record)
                stored["_received_wall_s"] = now
                stored["_source"] = str(source or "unknown")
                if source_ts_s is not None:
                    stored["_source_ts_s"] = source_ts_s
                    self._last_source_ts_s[aircraft_id] = source_ts_s
                self._latest[aircraft_id] = stored
                count += 1
            if count:
                self.received_count += count
                self._last_source = str(source or "unknown")
                self._last_error = ""
        return count

    def latest(self, aircraft_id: str, *, max_age_s: Optional[float] = None) -> Optional[Dict[str, Any]]:
        vehicle_key = str(aircraft_id or "").strip()
        max_age = self.stale_after_s if max_age_s is None else max(0.0, float(max_age_s))
        now = time.monotonic()
        with self._lock:
            sample = self._latest.get(vehicle_key)
            if not isinstance(sample, dict):
                return None
            age = now - float(sample.get("_received_wall_s") or 0.0)
            if age > max_age:
                return None
            copy = deepcopy(sample)
            copy["_age_s"] = age
            return copy

    def snapshot(self) -> Dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            latest_age = {
                aircraft_id: max(0.0, now - float(sample.get("_received_wall_s") or 0.0))
                for aircraft_id, sample in self._latest.items()
            }
            return {
                "running": bool(self._thread is not None and self._thread.is_alive()),
                "prefer_websocket": bool(self.prefer_websocket),
                "ws_available": bool(self._ws_available),
                "ws_connected": bool(self._ws_connected),
                "poll_period_s": float(self.poll_period_s),
                "stale_after_s": float(self.stale_after_s),
                "ws_backoff_s": float(self._ws_backoff_s),
                "poll_backoff_s": float(self._poll_backoff_s),
                "next_ws_attempt_in_s": max(0.0, self._next_ws_attempt_s - now),
                "next_poll_attempt_in_s": max(0.0, self._next_poll_attempt_s - now),
                "aircraft": sorted(self._latest.keys()),
                "latest_age_s": latest_age,
                "global_ignore_before_source_ts_s": float(self._global_ignore_before_source_ts_s),
                "ignore_before_source_ts_s": dict(self._ignore_before_source_ts_s),
                "received_count": int(self.received_count),
                "dropped_count": int(self.dropped_count),
                "poll_count": int(self.poll_count),
                "ws_message_count": int(self.ws_message_count),
                "error_count": int(self.error_count),
                "last_error": self._last_error,
                "last_source": self._last_source,
                "last_poll_result": dict(self._last_poll_result),
            }

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            now = time.monotonic()
            if (
                self.prefer_websocket
                and now >= self._next_ws_attempt_s
                and self._run_websocket_until_error()
            ):
                continue
            now = time.monotonic()
            if now >= self._next_poll_attempt_s:
                self._poll_once()
            wait_s = self.poll_period_s
            if self.prefer_websocket and self._next_ws_attempt_s > now:
                wait_s = min(wait_s, max(0.05, self._next_ws_attempt_s - now))
            if self._next_poll_attempt_s > now:
                wait_s = min(max(wait_s, 0.05), max(0.05, self._next_poll_attempt_s - now))
            if self._stop_event.wait(wait_s):
                break

    def _run_websocket_until_error(self) -> bool:
        try:
            import websocket  # type: ignore
        except Exception:
            with self._lock:
                self._ws_available = False
                self._next_ws_attempt_s = time.monotonic() + self._max_backoff_s
            return False

        with self._lock:
            self._ws_available = True
        ws = None
        try:
            ws = websocket.create_connection(self.client.websocket_url(), timeout=1.0)
            with self._lock:
                self._ws_connected = True
                self._last_error = ""
                self._ws_backoff_s = self._base_backoff_s
            while not self._stop_event.is_set():
                try:
                    message = ws.recv()
                    if message:
                        self.ws_message_count += 1
                        self.ingest(message, source="ws")
                except Exception as exc:
                    # Keep VFDS's receive loop alive when no telemetry arrives.
                    if type(exc).__name__ == "WebSocketTimeoutException":
                        try:
                            ws.send("ping")
                            continue
                        except Exception:
                            pass
                    raise
            return True
        except Exception as exc:
            self._record_error(f"ws: {type(exc).__name__}: {exc}")
            self._schedule_ws_backoff()
            return False
        finally:
            with self._lock:
                self._ws_connected = False
            try:
                if ws is not None:
                    ws.close()
            except Exception:
                pass

    def _poll_once(self) -> None:
        try:
            result = self.client.get_telemetry_snapshot()
            with self._lock:
                self.poll_count += 1
                self._last_poll_result = result.to_dict()
            if result.ok:
                self._reset_poll_backoff()
                self.ingest(result.body, source="poll")
            elif result.error:
                self._record_error(f"poll: {result.error}")
                self._schedule_poll_backoff()
        except Exception as exc:
            self._record_error(f"poll: {type(exc).__name__}: {exc}")
            self._schedule_poll_backoff()

    def _record_error(self, message: str) -> None:
        with self._lock:
            self.error_count += 1
            self._last_error = str(message or "unknown")

    def _schedule_ws_backoff(self) -> None:
        with self._lock:
            delay = min(self._max_backoff_s, max(self._base_backoff_s, self._ws_backoff_s))
            self._next_ws_attempt_s = time.monotonic() + delay
            self._ws_backoff_s = min(self._max_backoff_s, delay * 2.0)

    def _schedule_poll_backoff(self) -> None:
        with self._lock:
            delay = min(self._max_backoff_s, max(self.poll_period_s, self._poll_backoff_s))
            self._next_poll_attempt_s = time.monotonic() + delay
            self._poll_backoff_s = min(self._max_backoff_s, delay * 2.0)

    def _reset_poll_backoff(self) -> None:
        with self._lock:
            self._poll_backoff_s = self._base_backoff_s
            self._next_poll_attempt_s = 0.0

    @staticmethod
    def _extract_records(payload: Any) -> list[Dict[str, Any]]:
        if isinstance(payload, dict):
            if isinstance(payload.get("aircraft"), list):
                return [item for item in payload["aircraft"] if isinstance(item, dict)]
            if isinstance(payload.get("data"), dict):
                return VfdsTelemetryReceiver._extract_records(payload["data"])
            if payload.get("aircraftId") or payload.get("aircraft_id") or payload.get("vehicleId"):
                return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []


def _source_ts_to_epoch(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    except Exception:
        return None
