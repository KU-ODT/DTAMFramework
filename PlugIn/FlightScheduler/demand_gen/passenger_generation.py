from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import random


@dataclass(frozen=True)
class PassengerRecord:
    id: str
    origin: str
    destination: str
    arrival_time: datetime

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "origin": self.origin,
            "destination": self.destination,
            "arrivalTime": self.arrival_time.isoformat(),
            "arrivalTimeLabel": self.arrival_time.strftime("%H:%M:%S"),
            "arrivalHour": self.arrival_time.hour,
        }


def generate_passenger_manifest(
    pairs: list[dict[str, object]],
    scenario_date: date,
    timeline_weights: list[float],
    seed: int | None,
    operation_start: str | None = None,
    operation_end: str | None = None,
) -> dict[str, object]:
    rng = random.Random(seed)
    origin_buckets: dict[str, list[tuple[str, datetime]]] = {}
    for pair in pairs:
        origin = str(pair["origin"])
        destination = str(pair["destination"])
        passenger_count = int(pair["passengers"])
        if passenger_count <= 0:
            continue
        times = sample_arrival_times(
            passenger_count,
            scenario_date,
            timeline_weights,
            rng,
            operation_start=operation_start,
            operation_end=operation_end,
        )
        bucket = origin_buckets.setdefault(origin, [])
        for arrival_time in times:
            bucket.append((destination, arrival_time))

    manifest: list[PassengerRecord] = []
    origin_counts: list[dict[str, object]] = []
    hourly_counts = [0 for _ in range(24)]

    for origin in sorted(origin_buckets):
        items = sorted(origin_buckets[origin], key=lambda item: item[1])
        origin_counts.append({"origin": origin, "count": len(items)})
        for index, (destination, arrival_time) in enumerate(items, start=1):
            record = PassengerRecord(
                id=f"{origin}_{index:05d}",
                origin=origin,
                destination=destination,
                arrival_time=arrival_time,
            )
            manifest.append(record)
            hourly_counts[arrival_time.hour] += 1

    manifest.sort(key=lambda item: (item.arrival_time, item.origin, item.destination, item.id))
    peak_hour = max(range(24), key=lambda hour: hourly_counts[hour]) if manifest else None

    return {
        "records": manifest,
        "originCounts": origin_counts,
        "timeline": {
            "hours": [f"{hour:02d}:00" for hour in range(24)],
            "counts": hourly_counts,
            "peakHourLabel": f"{peak_hour:02d}:00" if peak_hour is not None else None,
            "peakHourCount": hourly_counts[peak_hour] if peak_hour is not None else 0,
        },
    }


def sample_arrival_times(
    count: int,
    scenario_date: date,
    timeline_weights: list[float],
    rng: random.Random,
    *,
    operation_start: str | None = None,
    operation_end: str | None = None,
) -> list[datetime]:
    if count <= 0:
        return []
    day_start = datetime.combine(scenario_date, time())
    weights = list(timeline_weights)
    minute_ranges_by_hour = _full_day_minute_ranges()
    if operation_start is not None and operation_end is not None:
        minute_ranges_by_hour = _window_minute_ranges_by_hour(
            _parse_hhmm(operation_start),
            _parse_hhmm(operation_end),
        )
        weights = [
            weight * (sum(end - start for start, end in minute_ranges_by_hour[hour]) / 60.0)
            for hour, weight in enumerate(timeline_weights)
        ]
        total = sum(weights)
        if total > 0:
            weights = [weight / total for weight in weights]
        else:
            weights = list(timeline_weights)
            minute_ranges_by_hour = _full_day_minute_ranges()

    hours = rng.choices(range(24), weights=weights, k=count)
    times: list[datetime] = []
    for hour in hours:
        minute_ranges = minute_ranges_by_hour[hour] or [(0, 60)]
        range_weights = [end - start for start, end in minute_ranges]
        start_min, end_min = rng.choices(minute_ranges, weights=range_weights, k=1)[0]
        minute = rng.randrange(start_min, end_min)
        second = rng.randrange(60)
        times.append(day_start + timedelta(hours=hour, minutes=minute, seconds=second))
    return times


def _parse_hhmm(value: str) -> int:
    hour_text, minute_text = str(value).strip().split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid time value: {value!r}")
    return (hour * 60) + minute


def _full_day_minute_ranges() -> list[list[tuple[int, int]]]:
    return [[(0, 60)] for _ in range(24)]


def _window_intervals(start_min: int, end_min: int) -> list[tuple[int, int]]:
    if start_min == end_min:
        return [(0, 24 * 60)]
    if start_min < end_min:
        return [(start_min, end_min)]
    return [(start_min, 24 * 60), (0, end_min)]


def _window_minute_ranges_by_hour(start_min: int, end_min: int) -> list[list[tuple[int, int]]]:
    ranges: list[list[tuple[int, int]]] = [[] for _ in range(24)]
    for left, right in _window_intervals(start_min, end_min):
        for hour in range(24):
            hour_start = hour * 60
            hour_end = hour_start + 60
            overlap_start = max(left, hour_start)
            overlap_end = min(right, hour_end)
            if overlap_start < overlap_end:
                ranges[hour].append((overlap_start - hour_start, overlap_end - hour_start))
    return ranges
