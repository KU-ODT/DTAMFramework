from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from typing import TypeVar


ScheduleT = TypeVar("ScheduleT")


def build_random_schedule(
    port_names: Sequence[str],
    count: int,
    window_s: int,
    make_schedule: Callable[[int, int, str, str], ScheduleT],
) -> list[ScheduleT]:
    if count <= 0:
        return []
    if len(port_names) < 2:
        return []
    if window_s <= 0:
        return []

    schedule: list[ScheduleT] = []
    max_offset = max(0, int(window_s) - 1)
    schedule_id = 1
    names = list(port_names)

    for _ in range(int(count)):
        origin = random.choice(names)
        destination = random.choice(names)
        while destination == origin:
            destination = random.choice(names)
        start_offset = random.randint(0, max_offset) if max_offset > 0 else 0
        schedule.append(
            make_schedule(
                int(schedule_id),
                int(start_offset),
                str(origin),
                str(destination),
            )
        )
        schedule_id += 1

    schedule.sort(key=lambda item: int(getattr(item, "start_offset_s", 0)))
    return schedule
