from __future__ import annotations

import csv
import io
from collections.abc import Callable
from typing import Optional, TypeVar


ScheduleT = TypeVar("ScheduleT")


def flightplan_sort_key(item: object) -> tuple[int, int, str, str, str, int]:
    start_offset_s = _to_int(_field(item, "start_offset_s", 0), 0)
    planned_takeoff_offset_s = _to_int(
        _field(item, "planned_takeoff_offset_s", start_offset_s),
        start_offset_s,
    )
    schedule_id = _to_int(_field(item, "schedule_id", 0), 0)
    return (
        start_offset_s,
        planned_takeoff_offset_s,
        str(_field(item, "aircraft_id", "") or ""),
        str(_field(item, "source_file", "") or ""),
        str(_field(item, "local_id", "") or ""),
        schedule_id,
    )


def normalize_flightplan_schedule(schedule: list[ScheduleT]) -> list[ScheduleT]:
    normalized = list(schedule)
    normalized.sort(key=flightplan_sort_key)
    return normalized


def build_flightplan_state(
    schedule: list[object],
    enabled: bool,
    name: str = "",
) -> dict[str, object]:
    aircraft_ids = {
        str(_field(item, "aircraft_id", "") or "").strip()
        for item in schedule
        if str(_field(item, "aircraft_id", "") or "").strip()
    }
    return {
        "enabled": bool(enabled and schedule),
        "name": str(name or "").strip(),
        "legs": int(len(schedule)),
        "aircraft": int(len(aircraft_ids)),
    }


def parse_flightplan_payload(
    payload: dict[str, object] | None,
    *,
    default_gate_wait_s: int,
    default_ground_taxi_s: int,
    default_fato_prep_s: int,
    default_turnaround_s: int,
    sim_start_seconds: int,
    make_schedule: Callable[..., ScheduleT],
) -> tuple[list[ScheduleT], dict[str, object]] | None:
    if not isinstance(payload, dict):
        return None
    if "flightplan" not in payload:
        return None

    raw = payload.get("flightplan")
    if raw is None:
        return [], {"enabled": False, "name": "", "legs": 0, "aircraft": 0}
    if not isinstance(raw, dict):
        return [], {"enabled": False, "name": "", "legs": 0, "aircraft": 0}

    raw_name = str(raw.get("name") or "").strip()
    files = raw.get("files")
    if not isinstance(files, list):
        return [], {"enabled": False, "name": raw_name, "legs": 0, "aircraft": 0}

    schedules: list[ScheduleT] = []
    seen_ids: set[int] = set()
    schedule_id = 1
    skipped_rows = 0
    sorted_files: list[dict[str, object]] = []
    for entry in files:
        if isinstance(entry, dict):
            sorted_files.append(entry)
    sorted_files.sort(
        key=lambda item: (
            str(item.get("relativePath") or "").strip().lower(),
            str(item.get("name") or item.get("fileName") or "").strip().lower(),
        )
    )

    for entry in sorted_files:
        filename = str(entry.get("name") or entry.get("fileName") or "").strip()
        relative_path = str(entry.get("relativePath") or "").strip()
        source_file = relative_path or filename
        text = entry.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            reader = csv.DictReader(io.StringIO(text))
        except csv.Error:
            continue
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            continue
        column_lookup: dict[str, str] = {}
        for field in fieldnames:
            key = _normalize_header_key(field)
            if key and key not in column_lookup:
                column_lookup[key] = field
        col_local_id = column_lookup.get("localid")
        col_aircraft_id = column_lookup.get("id")
        col_origin = column_lookup.get("from")
        col_destination = column_lookup.get("to")
        col_dep_fato_no = column_lookup.get("depfatono")
        col_dep_gate_no = column_lookup.get("depgateno")
        col_arr_fato_no = column_lookup.get("arrfatono")
        col_arr_gate_no = column_lookup.get("arrgateno")
        col_std = column_lookup.get("std")
        col_dep_gate_in = column_lookup.get("depgatein")
        col_dep_gate_out = column_lookup.get("depgateout")
        col_dep_fato_in = column_lookup.get("depfatoin")
        col_dep_fato_out = column_lookup.get("depfatoout")
        if not col_aircraft_id or not col_origin or not col_destination:
            continue
        if not col_dep_gate_in and not col_dep_fato_out and not col_std:
            continue
        for row in reader:
            aircraft_id = str(row.get(col_aircraft_id, "")).strip()
            origin = str(row.get(col_origin, "")).strip()
            destination = str(row.get(col_destination, "")).strip()
            if not aircraft_id or not origin or not destination:
                skipped_rows += 1
                continue

            dep_gate_in_s = _parse_clock_to_seconds(row.get(col_dep_gate_in)) if col_dep_gate_in else None
            dep_gate_out_s = _parse_clock_to_seconds(row.get(col_dep_gate_out)) if col_dep_gate_out else None
            dep_fato_in_s = _parse_clock_to_seconds(row.get(col_dep_fato_in)) if col_dep_fato_in else None
            dep_fato_out_s = _parse_clock_to_seconds(row.get(col_dep_fato_out)) if col_dep_fato_out else None
            std_s = _parse_clock_to_seconds(row.get(col_std)) if col_std else None

            if dep_gate_in_s is None:
                if dep_fato_out_s is not None:
                    dep_gate_in_s = (
                        dep_fato_out_s
                        - (default_gate_wait_s + default_ground_taxi_s + default_fato_prep_s)
                    ) % (24 * 3600)
                elif std_s is not None:
                    dep_gate_in_s = (
                        std_s - (default_ground_taxi_s + default_fato_prep_s)
                    ) % (24 * 3600)
            if dep_fato_out_s is None:
                dep_fato_out_s = std_s
            if dep_gate_in_s is None:
                skipped_rows += 1
                continue
            if dep_gate_out_s is None:
                dep_gate_out_s = (dep_gate_in_s + default_gate_wait_s) % (24 * 3600)
            if dep_fato_in_s is None:
                dep_fato_in_s = (dep_gate_out_s + default_ground_taxi_s) % (24 * 3600)
            if dep_fato_out_s is None:
                dep_fato_out_s = (dep_fato_in_s + default_fato_prep_s) % (24 * 3600)

            gate_wait_s = _clock_diff_s(dep_gate_in_s, dep_gate_out_s)
            taxi_wait_s = _clock_diff_s(dep_gate_out_s, dep_fato_in_s)
            fato_wait_s = _clock_diff_s(dep_fato_in_s, dep_fato_out_s)
            if gate_wait_s is None or gate_wait_s <= 0:
                gate_wait_s = default_gate_wait_s
            if taxi_wait_s is None or taxi_wait_s <= 0:
                taxi_wait_s = default_ground_taxi_s
            if fato_wait_s is None or fato_wait_s <= 0:
                fato_wait_s = default_fato_prep_s

            preflight_wait_s = int(gate_wait_s + taxi_wait_s + fato_wait_s)
            if preflight_wait_s <= 0:
                preflight_wait_s = (
                    default_gate_wait_s + default_ground_taxi_s + default_fato_prep_s
                )

            start_offset_s = _clock_to_sim_offset_s(dep_gate_in_s, sim_start_seconds)
            planned_takeoff_offset_s = start_offset_s + preflight_wait_s

            if schedule_id in seen_ids:
                schedule_id = max(seen_ids) + 1 if seen_ids else 1
            seen_ids.add(schedule_id)
            schedules.append(
                make_schedule(
                    schedule_id=int(schedule_id),
                    risk="0",
                    start_offset_s=int(start_offset_s),
                    origin=origin,
                    destination=destination,
                    aircraft_id=aircraft_id,
                    local_id=str(row.get(col_local_id, "")).strip() if col_local_id else "",
                    dep_fato_no=str(row.get(col_dep_fato_no, "")).strip() if col_dep_fato_no else "",
                    dep_gate_no=str(row.get(col_dep_gate_no, "")).strip() if col_dep_gate_no else "",
                    arr_fato_no=str(row.get(col_arr_fato_no, "")).strip() if col_arr_fato_no else "",
                    arr_gate_no=str(row.get(col_arr_gate_no, "")).strip() if col_arr_gate_no else "",
                    source_file=source_file,
                    planned_takeoff_offset_s=int(planned_takeoff_offset_s),
                    preflight_wait_s=int(preflight_wait_s),
                    turnaround_s=int(default_turnaround_s),
                )
            )
            schedule_id += 1

    schedules = normalize_flightplan_schedule(schedules)
    aircraft_ids = {
        str(_field(item, "aircraft_id", "") or "").strip()
        for item in schedules
        if str(_field(item, "aircraft_id", "") or "").strip()
    }
    state = {
        "enabled": bool(schedules),
        "name": raw_name,
        "legs": int(len(schedules)),
        "aircraft": int(len(aircraft_ids)),
        "skipped_rows": int(skipped_rows),
    }
    return schedules, state


def _to_int(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def _field(item: object, name: str, default: object) -> object:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _normalize_header_key(value: object) -> str:
    text = str(value or "").replace("\ufeff", "").strip().lower()
    return "".join(ch for ch in text if ch.isalnum())


def _parse_clock_to_seconds(value: object) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
    except ValueError:
        return None
    if hour < 0 or hour >= 24:
        return None
    if minute < 0 or minute >= 60:
        return None
    if second < 0 or second >= 60:
        return None
    return hour * 3600 + minute * 60 + second


def _clock_diff_s(start_s: Optional[int], end_s: Optional[int]) -> Optional[int]:
    if start_s is None or end_s is None:
        return None
    diff = int(end_s) - int(start_s)
    if diff < 0:
        diff += 24 * 3600
    return diff


def _clock_to_sim_offset_s(clock_s: int, sim_start_seconds: int) -> int:
    offset = int(clock_s) - int(sim_start_seconds)
    return max(0, offset)
