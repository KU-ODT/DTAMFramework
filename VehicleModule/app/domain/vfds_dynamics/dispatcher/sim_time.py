"""
Simulation clock shared by the HTTP receiver and dispatch scheduler.

The simulator sends clock updates as HH:MM:SS.  Mission scheduling uses this
clock instead of wall time when it is provided.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any


_TIME_RE = re.compile(r"^(\d{1,2}):(\d{1,2}):(\d{1,2})$")


class SimulationTimeError(ValueError):
    """Raised when a simulation time payload cannot be parsed."""


@dataclass(frozen=True)
class SimulationTimeSnapshot:
    time: str | None
    seconds: int | None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.time,
            "seconds": self.seconds,
            "available": self.seconds is not None,
            "source": self.source,
        }


def parse_hhmmss(value: str) -> int:
    match = _TIME_RE.match(value.strip())
    if not match:
        raise SimulationTimeError(f"time must be HH:MM:SS, got {value!r}")

    hour, minute, second = (int(part) for part in match.groups())
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise SimulationTimeError(f"time is out of range, got {value!r}")
    return hour * 3600 + minute * 60 + second


def format_hhmmss(seconds: int) -> str:
    seconds = max(0, min(int(seconds), 24 * 3600 - 1))
    hour = seconds // 3600
    minute = (seconds % 3600) // 60
    second = seconds % 60
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def extract_time_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload

    if not isinstance(payload, dict):
        raise SimulationTimeError("payload must be a JSON object or HH:MM:SS string")

    for key in ("time", "simulationTime", "simTime", "currentTime"):
        value = payload.get(key)
        if isinstance(value, str):
            return value

    hour = payload.get("hour", payload.get("hh"))
    minute = payload.get("minute", payload.get("mm"))
    second = payload.get("second", payload.get("ss"))
    if hour is not None and minute is not None and second is not None:
        try:
            return f"{int(hour):02d}:{int(minute):02d}:{int(second):02d}"
        except (TypeError, ValueError) as exc:
            raise SimulationTimeError("hour/minute/second must be integers") from exc

    raise SimulationTimeError(
        "payload must include time, simulationTime, simTime, currentTime, "
        "or hour/minute/second"
    )


class SimulationClock:
    """Async clock updated by external simulation-time messages."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._time_text: str | None = None
        self._seconds: int | None = None
        self._source: str | None = None

    async def update(self, payload: Any) -> SimulationTimeSnapshot:
        time_text = extract_time_text(payload)
        seconds = parse_hhmmss(time_text)
        normalized = format_hhmmss(seconds)
        source = payload.get("source") if isinstance(payload, dict) else None
        if not isinstance(source, str) or not source.strip():
            source = "api"
        async with self._condition:
            self._time_text = normalized
            self._seconds = seconds
            self._source = source.strip()
            self._condition.notify_all()
        return SimulationTimeSnapshot(time=normalized, seconds=seconds, source=self._source)

    async def wait_until(self, target_seconds: int) -> SimulationTimeSnapshot:
        async with self._condition:
            while self._seconds is None or self._seconds < target_seconds:
                await self._condition.wait()
            return SimulationTimeSnapshot(time=self._time_text, seconds=self._seconds, source=self._source)

    def has_reached(self, target_seconds: int) -> bool:
        return self._seconds is not None and self._seconds >= target_seconds

    def snapshot(self) -> SimulationTimeSnapshot:
        return SimulationTimeSnapshot(time=self._time_text, seconds=self._seconds, source=self._source)
