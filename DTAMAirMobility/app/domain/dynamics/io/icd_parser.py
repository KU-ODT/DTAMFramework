"""UAM Flight Simulator — ICD v1 JSON parser and validator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..core.types import (
    Arrival,
    Departure,
    EnRouteSegment,
    FlightPlan,
    LLA,
    Phase,
    TURN_PHASES,
)


class ICDValidationError(Exception):
    """Raised when an ICD record fails validation."""


# ── Helpers ─────────────────────────────────────────────────────
def _require(data: dict, key: str, typ: type, path: str = "") -> Any:
    full = f"{path}.{key}" if path else key
    if key not in data:
        raise ICDValidationError(f"Missing required field: {full}")
    val = data[key]
    if not isinstance(val, typ):
        raise ICDValidationError(
            f"Field {full} expected {typ.__name__}, got {type(val).__name__}"
        )
    return val


def _parse_lla(data: dict, path: str) -> LLA:
    lat = _require(data, "lat", (int, float), path)
    lon = _require(data, "lon", (int, float), path)
    alt = _require(data, "alt", (int, float), path)
    return LLA(lat=float(lat), lon=float(lon), alt=float(alt))


def _optional_number(data: dict, keys: List[str], path: str) -> Optional[float]:
    for key in keys:
        if key not in data:
            continue
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, (int, float)):
            raise ICDValidationError(
                f"Field {path}.{key} expected number, got {type(value).__name__}"
            )
        return float(value)
    return None


def _parse_time(val: str, field_name: str) -> str:
    parts = val.split(":")
    if len(parts) != 3:
        raise ICDValidationError(f"{field_name} must be HH:MM:SS, got '{val}'")
    return val


# ── Parse single flight plan ───────────────────────────────────
def parse_flight_plan(data: dict) -> FlightPlan:
    """Parse and validate a single ICD v1 flight plan JSON record."""

    fp_num = _require(data, "flightPlanNumber", (int,), "")
    ac_id = _require(data, "aircraftId", (str,), "")

    # departure
    dep_raw = _require(data, "departure", (dict,), "")
    dep = Departure(
        vertiport=_require(dep_raw, "vertiport", (str,), "departure"),
        std=_parse_time(_require(dep_raw, "std", (str,), "departure"), "departure.std"),
        dep_gate_number=_require(dep_raw, "depGateNumber", (str,), "departure"),
        eobt=_parse_time(_require(dep_raw, "eobt", (str,), "departure"), "departure.eobt"),
        dep_fato_number=_require(dep_raw, "depFatoNumber", (str,), "departure"),
        etot=_parse_time(_require(dep_raw, "etot", (str,), "departure"), "departure.etot"),
    )

    # arrival
    arr_raw = _require(data, "arrival", (dict,), "")
    arr = Arrival(
        vertiport=_require(arr_raw, "vertiport", (str,), "arrival"),
        sta=_parse_time(_require(arr_raw, "sta", (str,), "arrival"), "arrival.sta"),
        arr_gate_number=_require(arr_raw, "arrGateNumber", (str,), "arrival"),
        eibt=_parse_time(_require(arr_raw, "eibt", (str,), "arrival"), "arrival.eibt"),
        arr_fato_number=_require(arr_raw, "arrFatoNumber", (str,), "arrival"),
        eldt=_parse_time(_require(arr_raw, "eldt", (str,), "arrival"), "arrival.eldt"),
    )

    # enRoute
    en_raw = _require(data, "enRoute", (list,), "")
    if not en_raw:
        raise ICDValidationError("enRoute must have at least one segment")

    segments: List[EnRouteSegment] = []
    for i, seg_raw in enumerate(en_raw):
        prefix = f"enRoute[{i}]"
        seq = _require(seg_raw, "seq", (int,), prefix)
        phase_str = _require(seg_raw, "phase", (str,), prefix)
        try:
            phase = Phase(phase_str)
        except ValueError:
            raise ICDValidationError(
                f"{prefix}.phase: invalid code '{phase_str}'"
            )

        start_lla = _parse_lla(_require(seg_raw, "startLLA", (dict,), prefix),
                               f"{prefix}.startLLA")
        end_lla = _parse_lla(_require(seg_raw, "endLLA", (dict,), prefix),
                             f"{prefix}.endLLA")
        target_speed = _require(seg_raw, "targetSpeed", (int, float), prefix)
        target_heading_deg = _optional_number(
            seg_raw,
            ["targetHeadingDeg", "target_heading_deg", "endHeadingDeg", "yawDeg", "yaw_deg"],
            prefix,
        )

        turn_dir = None
        center_lla = None
        if phase in TURN_PHASES:
            turn_dir = _require(seg_raw, "turnDirection", (str,), prefix)
            if turn_dir not in ("CW", "CCW"):
                raise ICDValidationError(
                    f"{prefix}.turnDirection must be CW or CCW, got '{turn_dir}'"
                )
            center_lla = _parse_lla(
                _require(seg_raw, "centerLLA", (dict,), prefix),
                f"{prefix}.centerLLA",
            )
        else:
            if "turnDirection" in seg_raw or "centerLLA" in seg_raw:
                raise ICDValidationError(
                    f"{prefix}: non-turn phase '{phase_str}' must not have "
                    f"turnDirection/centerLLA"
                )

        segments.append(EnRouteSegment(
            seq=seq,
            phase=phase,
            start_lla=start_lla,
            end_lla=end_lla,
            target_speed=float(target_speed),
            turn_direction=turn_dir,
            center_lla=center_lla,
            target_heading_deg=target_heading_deg,
        ))

    # Validation: seq must be 1-based consecutive
    for i, seg in enumerate(segments):
        if seg.seq != i + 1:
            raise ICDValidationError(
                f"enRoute[{i}].seq should be {i + 1}, got {seg.seq}"
            )

    return FlightPlan(
        flight_plan_number=fp_num,
        aircraft_id=ac_id,
        departure=dep,
        en_route=segments,
        arrival=arr,
    )


# ── Batch / file loading ───────────────────────────────────────
def parse_flight_plans(data: Union[dict, list]) -> List[FlightPlan]:
    """Parse one or more flight plans (single object or array)."""
    if isinstance(data, dict):
        return [parse_flight_plan(data)]
    if isinstance(data, list):
        return [parse_flight_plan(d) for d in data]
    raise ICDValidationError("Expected a JSON object or array")


def load_from_file(path: Union[str, Path]) -> List[FlightPlan]:
    """Load flight plan(s) from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return parse_flight_plans(data)
