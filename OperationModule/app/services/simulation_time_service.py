"""OperationModule simulation clock used by the console header and 1002 flow.

The Operation console's displayed "server time" is DTAM simulation time, not
the host PC wall-clock.  It starts at 06:30:00 KST and advances only while the
1002 play state is ``play``.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any


SEOUL_TZ = ZoneInfo("Asia/Seoul")
DEFAULT_SIMULATION_START_TIME = "06:30:00"
DEFAULT_SIMULATION_START_SECONDS = 6 * 60 * 60 + 30 * 60
SECONDS_PER_DAY = 24 * 60 * 60


def _seconds_to_hhmmss(seconds: float) -> str:
    total = int(float(seconds)) % SECONDS_PER_DAY
    hours, remainder = divmod(total, 3600)
    minutes, sec = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


def _parse_hhmmss(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) not in {2, 3}:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2]) if len(parts) == 3 else 0
    except (TypeError, ValueError):
        return None
    if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
        return None
    return float(hours * 3600 + minutes * 60 + seconds)


def _extract_seconds(payload: dict[str, Any]) -> tuple[float | None, str]:
    if not isinstance(payload, dict):
        return None, ""
    for key in ("simSecondsOfDay", "sim_seconds_of_day"):
        if key in payload:
            try:
                value = float(payload[key])
                if value >= 0:
                    return value % SECONDS_PER_DAY, key
            except (TypeError, ValueError):
                pass
    for key in ("simTimeOfDay", "simulationTime", "simTime", "currentTime"):
        value = _parse_hhmmss(payload.get(key))
        if value is not None:
            return value, key
    return None, ""


class OperationSimulationClock:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._base_date = datetime.now(SEOUL_TZ).date()
        self._anchor_seconds = float(DEFAULT_SIMULATION_START_SECONDS)
        self._anchor_wall = time.monotonic()
        self._play_state = "pause"
        self._playback_speed = 1.0
        self._last_source = "default"

    def _current_seconds_locked(self) -> float:
        seconds = float(self._anchor_seconds)
        if self._play_state == "play":
            seconds += max(0.0, time.monotonic() - self._anchor_wall) * max(0.0, self._playback_speed)
        return seconds

    def apply_1002(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply a 1002 simulation setup payload to the Operation clock."""

        raw = dict(payload or {})
        requested_seconds, source_key = _extract_seconds(raw)
        start_seconds = _parse_hhmmss(raw.get("simulationStartTime")) or DEFAULT_SIMULATION_START_SECONDS
        play_state = str(raw.get("playState") or "pause").strip().lower()
        if play_state not in {"play", "pause", "reset"}:
            play_state = "pause"
        try:
            speed = float(raw.get("playbackSpeed", 1.0))
        except (TypeError, ValueError):
            speed = 1.0
        speed = max(0.0, speed)

        with self._lock:
            current_seconds = self._current_seconds_locked()
            previous_state = self._play_state
            next_seconds = current_seconds
            if play_state == "reset":
                next_seconds = start_seconds
                play_state = "pause"
                source_key = "reset"
            elif play_state == "play":
                # Starting from pause should honor the requested 1002 time
                # (normally 06:30:00).  While already playing, speed changes
                # must not snap the clock back to an old UI value.
                if previous_state != "play" and requested_seconds is not None:
                    next_seconds = requested_seconds
            else:
                # Pause should freeze at the best current value.  If the UI
                # sends an explicit current simulation time, use it; otherwise
                # keep the internally advanced value.
                if requested_seconds is not None and previous_state != "play":
                    next_seconds = requested_seconds

            self._anchor_seconds = float(next_seconds)
            self._anchor_wall = time.monotonic()
            self._play_state = play_state
            self._playback_speed = speed
            self._last_source = source_key or "1002"
            return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            seconds = self._current_seconds_locked()
            day_offset = int(seconds // SECONDS_PER_DAY)
            seconds_of_day = seconds % SECONDS_PER_DAY
            hms = _seconds_to_hhmmss(seconds_of_day)
            sim_date = self._base_date + timedelta(days=day_offset)
            hours, remainder = divmod(int(seconds_of_day), 3600)
            minutes, sec = divmod(remainder, 60)
            dt = datetime(
                sim_date.year,
                sim_date.month,
                sim_date.day,
                hours,
                minutes,
                sec,
                tzinfo=SEOUL_TZ,
            )
            return {
                "timezone": "Asia/Seoul",
                "iso": dt.isoformat(),
                "display": dt.strftime("%Y-%m-%d %H:%M:%S KST"),
                "simTimeOfDay": hms,
                "simSecondsOfDay": float(seconds_of_day),
                "playState": self._play_state,
                "playbackSpeed": float(self._playback_speed),
                "source": self._last_source,
            }


operation_simulation_clock = OperationSimulationClock()


def apply_operation_simulation_setup(payload: dict[str, Any]) -> dict[str, Any]:
    return operation_simulation_clock.apply_1002(payload)


def get_operation_server_time() -> dict[str, Any]:
    return operation_simulation_clock.snapshot()
