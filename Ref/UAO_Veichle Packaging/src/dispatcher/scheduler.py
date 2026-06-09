"""
Mission schedule helpers.

The dispatcher records mission arm/start times as soon as a mission arrives.
The generated mission script handles the actual simulation-time waits so
vehicle telemetry can start flowing immediately after submit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.validator.models import MissionPlan
from .sim_time import format_hhmmss, parse_hhmmss


@dataclass(frozen=True)
class MissionSchedule:
    scheduled_at: datetime
    dispatch_at: datetime
    delay_sec: float
    lead_sec: float
    source_field: str
    scheduled_time: str
    dispatch_time: str


def _get_nested_attr(obj: object, path: str) -> str:
    current = obj
    for part in path.split("."):
        current = getattr(current, part)
    if not isinstance(current, str):
        raise TypeError(f"Mission schedule field '{path}' must be a HH:MM:SS string")
    return current


def schedule_for_mission(
    mission: MissionPlan,
    *,
    now: datetime | None = None,
    timezone_name: str = "Asia/Seoul",
    time_field: str = "departure.std",
    lead_sec: float = 0.0,
) -> MissionSchedule:
    tz = ZoneInfo(timezone_name)
    now = now.astimezone(tz) if now else datetime.now(tz)
    value = _get_nested_attr(mission, time_field)
    schedule_seconds = parse_hhmmss(value)
    hh = schedule_seconds // 3600
    mm = (schedule_seconds % 3600) // 60
    ss = schedule_seconds % 60
    scheduled_clock = time(hour=hh, minute=mm, second=ss, tzinfo=tz)
    scheduled_at = datetime.combine(now.date(), scheduled_clock)
    dispatch_at = scheduled_at - timedelta(seconds=max(0.0, lead_sec))
    if dispatch_at.date() < scheduled_at.date():
        dispatch_at = datetime.combine(now.date(), time(0, 0, 0, tzinfo=tz))
    delay_sec = max(0.0, (dispatch_at - now).total_seconds())
    return MissionSchedule(
        scheduled_at=scheduled_at,
        dispatch_at=dispatch_at,
        delay_sec=delay_sec,
        lead_sec=max(0.0, lead_sec),
        source_field=time_field,
        scheduled_time=format_hhmmss(schedule_seconds),
        dispatch_time=dispatch_at.strftime("%H:%M:%S"),
    )


def schedule_seconds_for_mission(
    mission: MissionPlan,
    *,
    time_field: str = "departure.std",
    lead_sec: float = 0.0,
) -> tuple[int, int, str]:
    value = _get_nested_attr(mission, time_field)
    scheduled_seconds = parse_hhmmss(value)
    dispatch_seconds = max(0, scheduled_seconds - int(max(0.0, lead_sec)))
    return scheduled_seconds, dispatch_seconds, value
