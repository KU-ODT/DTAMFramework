"""Simulation time manager and 0003 Common Time Info publisher."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, time as datetime_time, timedelta, timezone
from typing import Any, Optional

# Registration handling

logger = logging.getLogger("sim_state.engine")

class SimulationEngine:
    """Internal helper."""

    START_SECONDS_OF_DAY = 6 * 60 * 60 + 30 * 60  # 06:30:00
    SECONDS_PER_DAY = 24 * 60 * 60

    def __init__(self, hub):
        self.hub = hub
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._lock = threading.RLock()
        self._play_state = "pause"
        self._playback_speed = 1
        self._sim_elapsed_s = 0.0
        self._last_mono = time.monotonic()
        self._sim_base_date = datetime.now(timezone.utc).date()

    def start_clock(self):
        if self._running:
            return
        self._running = True
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._clock_loop, daemon=True)
        self._thread.start()
        logger.info("Simulation clock started (1Hz 0003 emitter)")

    def stop_clock(self):
        self._running = False
        self._stop_evt.set()
        if self._thread:
            self._thread.join()
            self._thread = None

    def apply_control(self, payload: Any) -> None:
        """Apply MSG 1002 playback controls without changing unrelated fields.

        ``playbackSpeed`` updates the current multiplier when present.
        ``playState``/legacy ``action`` accepts play, pause, stop, and reset.
        Reset returns the simulation clock to 06:30:00.
        """
        action = self._normalize_state(
            self._get_val(payload, "playState") or self._get_val(payload, "action")
        )
        speed = self._coerce_playback_speed(self._get_val(payload, "playbackSpeed"))

        with self._lock:
            self._advance_locked()
            if speed is not None:
                self._playback_speed = speed
            if action == "reset":
                self._sim_elapsed_s = 0.0
                self._sim_base_date = datetime.now(timezone.utc).date()
                self._play_state = "reset"
            elif action in ("play", "pause"):
                self._play_state = action
            elif action == "stop":
                self._play_state = "pause"
            self._last_mono = time.monotonic()

        # Keep the publisher alive once playback is controlled so modules can
        # receive frozen pause/reset states as well as advancing play states.
        self.start_clock()
        logger.info(
            "[SIM] 1002 applied: playState=%s playbackSpeed=%sx simTimeOfDay=%s",
            self.play_state,
            self.playback_speed,
            self.snapshot()["simTimeOfDay"],
        )

    def _clock_loop(self):
        while not self._stop_evt.is_set():
            payload = self.snapshot()
            # Registration handling
            # Registration handling
            from IntegrationHub.CoreServerModule.app.model.message import FORWARD_RULES
            targets = FORWARD_RULES.get("0003", ["vehicle", "visual"])
            for t in targets:
                self.hub.push_to_role(t, "0003", payload)
                
            self._stop_evt.wait(1.0)

    @property
    def play_state(self) -> str:
        with self._lock:
            return self._play_state

    @property
    def playback_speed(self) -> int:
        with self._lock:
            return self._playback_speed

    def snapshot(self) -> dict[str, Any]:
        """Build the wire payload for MSG 0003."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._advance_locked(now_mono=time.monotonic())
            total_seconds = self.START_SECONDS_OF_DAY + self._sim_elapsed_s
            seconds_of_day = total_seconds % self.SECONDS_PER_DAY
            day_offset = int(total_seconds // self.SECONDS_PER_DAY)
            play_state = self._play_state
            playback_speed = self._playback_speed
            base_date = self._sim_base_date

        sim_dt = datetime.combine(
            base_date + timedelta(days=day_offset),
            datetime_time(0, 0, 0),
            tzinfo=timezone.utc,
        ) + timedelta(seconds=seconds_of_day)

        return {
            "timestamp": _iso_utc_ms(now),
            "simTime": _iso_utc_ms(sim_dt),
            "simTimeOfDay": _format_time_of_day(seconds_of_day),
            "simSecondsOfDay": round(seconds_of_day, 3),
            "playbackSpeed": playback_speed,
            "playState": play_state,
        }

    def _advance_locked(self, *, now_mono: Optional[float] = None) -> None:
        now_mono = time.monotonic() if now_mono is None else now_mono
        if self._play_state == "play":
            delta = max(0.0, now_mono - self._last_mono)
            self._sim_elapsed_s += delta * float(self._playback_speed)
        self._last_mono = now_mono

    @staticmethod
    def _get_val(obj: Any, key: str) -> Any:
        if hasattr(obj, key):
            return getattr(obj, key)
        if isinstance(obj, dict):
            return obj.get(key)
        return None

    @staticmethod
    def _normalize_state(value: Any) -> str:
        state = str(value or "").strip().lower()
        if state in {"play", "pause", "reset", "stop"}:
            return state
        return ""

    @staticmethod
    def _coerce_playback_speed(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            speed = int(float(value))
        except (TypeError, ValueError):
            return None
        if speed <= 0:
            return None
        return speed


def _iso_utc_ms(value: datetime) -> str:
    value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


def _format_time_of_day(seconds_of_day: float) -> str:
    whole_seconds = int(seconds_of_day) % SimulationEngine.SECONDS_PER_DAY
    hours = whole_seconds // 3600
    minutes = (whole_seconds % 3600) // 60
    seconds = whole_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
