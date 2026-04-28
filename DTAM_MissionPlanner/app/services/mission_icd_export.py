from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .converter_tool import get_vertiport_spawn_point
from .route_planner import RoutePlanner


ALLOWED_PHASES = {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"}
PHASE_MIN_DURATION_SEC = {
    "A": 45.0,
    "B": 40.0,
    "C": 55.0,
    "D": 65.0,
    "E": 75.0,
    "F": 90.0,
    "G": 55.0,
    "H": 65.0,
    "I": 50.0,
    "J": 35.0,
    "K": 45.0,
}


@dataclass(frozen=True)
class ResourcePoint:
    label: str
    category: str
    lat: float
    lon: float
    alt_m: float


def build_mission_icd_export(
    payload: Dict[str, Any],
    route_planner: Optional[RoutePlanner],
    resource_csv_path: Path,
    default_altitude_m: float,
) -> Dict[str, Any]:
    mode = str(payload.get("mode") or "route").strip().lower()
    options = payload.get("options") or {}
    context = _build_export_context(options)
    warnings: List[str] = []

    if mode == "route":
        if route_planner is None:
            raise ValueError("Route planner not loaded.")
        record = _build_route_record(
            payload,
            route_planner,
            resource_csv_path,
            default_altitude_m,
            context,
            warnings,
        )
    elif mode == "free":
        record = _build_free_record(payload, context, warnings)
    else:
        raise ValueError(f"Unsupported mission export mode: {mode}")

    errors = validate_mission_icd_record(record)
    filename = _build_filename(record)
    return {
        "mode": mode,
        "filename": filename,
        "record": record,
        "validation": {
            "valid": not errors,
            "errors": errors,
        },
        "warnings": warnings,
    }


def save_mission_icd_export(record: Dict[str, Any], export_dir: Path) -> Path:
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = _build_filename(record)
    path = export_dir / filename
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def validate_mission_icd_record(record: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    for key in ("flightPlanNumber", "aircraftId", "departure", "enRoute", "arrival"):
        if key not in record:
            errors.append(f"Missing top-level field: {key}")

    enroute = record.get("enRoute")
    if not isinstance(enroute, list) or not enroute:
        errors.append("enRoute must be a non-empty array.")
        return errors

    expected_seq = 1
    prev_end: Optional[Dict[str, Any]] = None
    for segment in enroute:
        seq = segment.get("seq")
        phase = segment.get("phase")
        if seq != expected_seq:
            errors.append(f"Segment seq must be continuous from 1. Expected {expected_seq}, got {seq}.")
        expected_seq += 1

        if phase not in ALLOWED_PHASES:
            errors.append(f"Unsupported phase code: {phase}")

        for field in ("startLLA", "endLLA", "targetSpeed"):
            if field not in segment:
                errors.append(f"Segment {seq} missing field: {field}")

        if prev_end is not None and segment.get("startLLA") != prev_end:
            errors.append(f"Segment continuity broken between seq {seq - 1} and seq {seq}.")
        prev_end = segment.get("endLLA")

        has_turn_fields = "turnDirection" in segment or "centerLLA" in segment
        if phase in {"D", "H"}:
            if "turnDirection" not in segment or "centerLLA" not in segment:
                errors.append(f"Turn segment {seq} requires turnDirection and centerLLA.")
        elif has_turn_fields:
            errors.append(f"Only D/H segments may include turnDirection or centerLLA (seq {seq}).")

    return errors


def _build_export_context(options: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now()
    std = _normalize_hms(options.get("std")) or now.strftime("%H:%M:%S")
    flight_plan_number = _coerce_int(options.get("flightPlanNumber"))
    if flight_plan_number is None:
        flight_plan_number = int(now.strftime("%m%d%H%M"))
    return {
        "flightPlanNumber": flight_plan_number,
        "aircraftId": str(options.get("aircraftId") or "UAM0001").strip() or "UAM0001",
        "std": std,
        "cruiseSpeedMps": _coerce_float(options.get("cruiseSpeedMps")) or 30.0,
    }


def _build_route_record(
    payload: Dict[str, Any],
    route_planner: RoutePlanner,
    resource_csv_path: Path,
    default_altitude_m: float,
    context: Dict[str, Any],
    warnings: List[str],
) -> Dict[str, Any]:
    route_data = payload.get("routeData") or {}
    path = list(route_data.get("path") or [])
    if len(path) < 2:
        raise ValueError("Route data must include at least a departure and arrival node.")

    departure_name = str(payload.get("departureName") or path[0])
    arrival_name = str(payload.get("arrivalName") or path[-1])
    if departure_name not in route_planner.ports or arrival_name not in route_planner.ports:
        raise ValueError("Selected departure/arrival vertiports are not available in the planner.")

    waypoint_map = {
        str(item.get("name") or ""): item
        for item in (route_data.get("waypoints") or [])
        if item.get("name")
    }
    resources = _load_resource_catalog(resource_csv_path)

    dep_port = route_planner.ports[departure_name]
    arr_port = route_planner.ports[arrival_name]
    dep_fallback_ground = _coerce_float(waypoint_map.get(departure_name, {}).get("ground_m")) or 0.0
    arr_fallback_ground = _coerce_float(waypoint_map.get(arrival_name, {}).get("ground_m")) or 0.0

    dep_gate = _pick_resource_point(resources, departure_name, "GATE")
    dep_fato = _pick_resource_point(resources, departure_name, "FATO")
    arr_gate = _pick_resource_point(resources, arrival_name, "GATE")
    arr_fato = _pick_resource_point(resources, arrival_name, "FATO")

    dep_gate_lla = _resource_or_port_lla(dep_gate, dep_port, dep_fallback_ground, warnings, "departure gate")
    dep_fato_lla = _resource_or_port_lla(dep_fato, dep_port, dep_fallback_ground, warnings, "departure FATO")
    arr_fato_lla = _resource_or_port_lla(arr_fato, arr_port, arr_fallback_ground, warnings, "arrival FATO")
    arr_gate_lla = _resource_or_port_lla(arr_gate, arr_port, arr_fallback_ground, warnings, "arrival gate")
    arrival_touchdown = _resolve_arrival_touchdown(
        route_data,
        arrival_name,
        arr_port,
        arr_fallback_ground,
        warnings,
    )

    dep_ground_alt = float(dep_fato_lla["alt"])
    arr_ground_alt = float(arrival_touchdown["alt"] if arrival_touchdown else arr_fato_lla["alt"])
    cruise_alt = _derive_cruise_altitude(route_data, default_altitude_m, dep_ground_alt, arr_ground_alt)
    dep_vertical_alt = _stage_altitude(dep_ground_alt, cruise_alt, 60.0)
    dep_turn_alt = max(dep_vertical_alt, _stage_altitude(dep_ground_alt, cruise_alt, 180.0))
    arr_turn_alt = max(_stage_altitude(arr_ground_alt, cruise_alt, 180.0), _stage_altitude(arr_ground_alt, cruise_alt, 60.0))
    arr_approach_alt = min(arr_turn_alt, max(arr_ground_alt, _stage_altitude(arr_ground_alt, cruise_alt, 60.0)))

    path_nodes = path[1:-1]
    corridor_nodes = [
        _node_lla(route_planner, node_name, cruise_alt)
        for node_name in path_nodes
    ]

    next_node_name = path[1] if len(path) > 1 else None
    prev_node_name = path[-2] if len(path) > 1 else None
    dep_turn = _build_departure_turn(route_planner, departure_name, next_node_name, dep_turn_alt)
    arr_turn = _build_arrival_turn(route_planner, prev_node_name, arrival_name, arr_turn_alt)

    segments: List[Dict[str, Any]] = []
    seq = 1

    current = dict(dep_gate_lla)
    seq = _append_segment(segments, seq, "A", current, dict(dep_fato_lla), _phase_speed("A", context["cruiseSpeedMps"]))
    current = dict(dep_fato_lla)
    dep_vertical_end = _lla(current["lat"], current["lon"], dep_vertical_alt)
    seq = _append_segment(segments, seq, "B", current, dep_vertical_end, _phase_speed("B", context["cruiseSpeedMps"]))
    current = dep_vertical_end

    first_corridor = corridor_nodes[0] if corridor_nodes else _lla(arr_port.lat, arr_port.lon, cruise_alt)
    dep_transition_target = dep_turn["startLLA"] if dep_turn else _lla(first_corridor["lat"], first_corridor["lon"], dep_turn_alt)
    seq = _append_segment(segments, seq, "C", current, dep_transition_target, _phase_speed("C", context["cruiseSpeedMps"]))
    current = dep_transition_target

    if dep_turn:
        dep_turn_segment = dict(dep_turn)
        dep_turn_segment.update({
            "seq": seq,
            "phase": "D",
            "targetSpeed": _phase_speed("D", context["cruiseSpeedMps"]),
        })
        segments.append(dep_turn_segment)
        seq += 1
        current = dict(dep_turn_segment["endLLA"])

    climb_target = _lla(first_corridor["lat"], first_corridor["lon"], cruise_alt)
    seq = _append_segment(segments, seq, "E", current, climb_target, _phase_speed("E", context["cruiseSpeedMps"]))
    current = climb_target

    for corridor_node in corridor_nodes[1:]:
        cruise_target = _lla(corridor_node["lat"], corridor_node["lon"], cruise_alt)
        seq = _append_segment(segments, seq, "F", current, cruise_target, _phase_speed("F", context["cruiseSpeedMps"]))
        current = cruise_target

    arrival_transition_target = arr_turn["startLLA"] if arr_turn else _lla(
        (arrival_touchdown or arr_fato_lla)["lat"],
        (arrival_touchdown or arr_fato_lla)["lon"],
        arr_turn_alt,
    )
    seq = _append_segment(segments, seq, "G", current, arrival_transition_target, _phase_speed("G", context["cruiseSpeedMps"]))
    current = arrival_transition_target

    if arr_turn:
        arr_turn_segment = dict(arr_turn)
        arr_turn_segment.update({
            "seq": seq,
            "phase": "H",
            "targetSpeed": _phase_speed("H", context["cruiseSpeedMps"]),
        })
        segments.append(arr_turn_segment)
        seq += 1
        current = dict(arr_turn_segment["endLLA"])

    arrival_landing_ref = arrival_touchdown or arr_fato_lla
    final_approach_target = _lla(arrival_landing_ref["lat"], arrival_landing_ref["lon"], arr_approach_alt)
    seq = _append_segment(segments, seq, "I", current, final_approach_target, _phase_speed("I", context["cruiseSpeedMps"]))
    current = final_approach_target

    landing_target = _lla(arrival_landing_ref["lat"], arrival_landing_ref["lon"], arr_ground_alt)
    seq = _append_segment(segments, seq, "J", current, landing_target, _phase_speed("J", context["cruiseSpeedMps"]))
    current = landing_target

    _append_segment(segments, seq, "K", current, dict(arr_gate_lla), _phase_speed("K", context["cruiseSpeedMps"]))

    return _finalize_record(
        context,
        departure_name,
        arrival_name,
        _icd_resource_label(dep_gate.label if dep_gate else None, "G"),
        _icd_resource_label(dep_fato.label if dep_fato else None, "F"),
        _icd_resource_label(arr_gate.label if arr_gate else None, "G"),
        _icd_resource_label(arr_fato.label if arr_fato else None, "F"),
        segments,
    )


def _build_free_record(
    payload: Dict[str, Any],
    context: Dict[str, Any],
    warnings: List[str],
) -> Dict[str, Any]:
    free_waypoints = payload.get("freeWaypoints") or []
    if len(free_waypoints) < 2:
        raise ValueError("Free mission requires at least two waypoints.")

    normalized = []
    for item in free_waypoints:
        lat = _coerce_float(item.get("lat"))
        lon = _coerce_float(item.get("lon"))
        alt = _coerce_float(item.get("alt_m"))
        if lat is None or lon is None or alt is None:
            continue
        normalized.append({
            "name": str(item.get("name") or ""),
            "lat": lat,
            "lon": lon,
            "alt": alt,
            "ground_m": _coerce_float(item.get("ground_m")) or 0.0,
        })

    if len(normalized) < 2:
        raise ValueError("Free mission waypoints are incomplete.")

    warnings.append("Free mission export uses generic ICD phases without vertiport turn metadata.")

    departure_name = str(payload.get("departureName") or normalized[0].get("name") or "FREE_DEP")
    arrival_name = str(payload.get("arrivalName") or normalized[-1].get("name") or "FREE_ARR")
    dep_ground = normalized[0]["ground_m"]
    arr_ground = normalized[-1]["ground_m"]

    segments: List[Dict[str, Any]] = []
    seq = 1

    current = _lla(normalized[0]["lat"], normalized[0]["lon"], dep_ground)
    takeoff_end = _lla(normalized[0]["lat"], normalized[0]["lon"], normalized[0]["alt"])
    seq = _append_segment(segments, seq, "B", current, takeoff_end, _phase_speed("B", context["cruiseSpeedMps"]))
    current = takeoff_end

    for index, waypoint in enumerate(normalized[1:], start=1):
        phase = "F"
        if index == 1:
            phase = "C"
        elif index == len(normalized) - 1:
            phase = "I"
        target = _lla(waypoint["lat"], waypoint["lon"], waypoint["alt"])
        seq = _append_segment(segments, seq, phase, current, target, _phase_speed(phase, context["cruiseSpeedMps"]))
        current = target

    landing_target = _lla(normalized[-1]["lat"], normalized[-1]["lon"], arr_ground)
    _append_segment(segments, seq, "J", current, landing_target, _phase_speed("J", context["cruiseSpeedMps"]))

    return _finalize_record(
        context,
        departure_name,
        arrival_name,
        "G1",
        "F1",
        "G1",
        "F1",
        segments,
    )


def _finalize_record(
    context: Dict[str, Any],
    departure_name: str,
    arrival_name: str,
    dep_gate_label: str,
    dep_fato_label: str,
    arr_gate_label: str,
    arr_fato_label: str,
    segments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    std_dt = _today_at(context["std"])
    durations = [_estimate_segment_duration_sec(segment) for segment in segments]
    elapsed = timedelta(seconds=0)

    eobt = std_dt + timedelta(seconds=60)
    etot = std_dt
    eldt = std_dt
    eibt = std_dt

    for segment, duration in zip(segments, durations):
        elapsed += timedelta(seconds=duration)
        phase = segment["phase"]
        if phase == "B":
            etot = std_dt + elapsed
        if phase == "J":
            eldt = std_dt + elapsed
        if phase == "K":
            eibt = std_dt + elapsed

    if eibt <= std_dt:
        eibt = std_dt + elapsed
    if eldt <= std_dt:
        eldt = eibt
    sta = max(eibt, eldt)

    return {
        "flightPlanNumber": context["flightPlanNumber"],
        "aircraftId": context["aircraftId"],
        "departure": {
            "vertiport": departure_name,
            "std": std_dt.strftime("%H:%M:%S"),
            "depGateNumber": dep_gate_label,
            "eobt": eobt.strftime("%H:%M:%S"),
            "depFatoNumber": dep_fato_label,
            "etot": etot.strftime("%H:%M:%S"),
        },
        "enRoute": segments,
        "arrival": {
            "vertiport": arrival_name,
            "sta": sta.strftime("%H:%M:%S"),
            "arrGateNumber": arr_gate_label,
            "eibt": eibt.strftime("%H:%M:%S"),
            "arrFatoNumber": arr_fato_label,
            "eldt": eldt.strftime("%H:%M:%S"),
        },
    }


@lru_cache(maxsize=1)
def _load_resource_catalog(path: Path) -> Dict[str, Dict[str, List[ResourcePoint]]]:
    rows = _read_csv_rows(path)
    catalog: Dict[str, Dict[str, List[ResourcePoint]]] = {}
    for row in rows:
        vertiport = str(row.get("Vertiport") or "").strip()
        label = str(row.get("Label") or "").strip()
        category = str(row.get("Category") or "").strip().upper()
        lat = _coerce_float(row.get("pt_lat_deg"))
        lon = _coerce_float(row.get("pt_lon_deg"))
        alt_m = _coerce_float(row.get("pt_h_m"))
        if not vertiport or not label or not category or lat is None or lon is None:
            continue
        catalog.setdefault(vertiport, {}).setdefault(category, []).append(
            ResourcePoint(
                label=label,
                category=category,
                lat=lat,
                lon=lon,
                alt_m=alt_m or 0.0,
            )
        )

    for per_vertiport in catalog.values():
        for category, points in per_vertiport.items():
            per_vertiport[category] = sorted(points, key=lambda item: _label_sort_key(item.label))
    return catalog


def _read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    for encoding in ("utf-8-sig", "cp949", "utf-8", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Could not decode CSV file: {path}")


def _pick_resource_point(
    catalog: Dict[str, Dict[str, List[ResourcePoint]]],
    vertiport_name: str,
    category: str,
) -> Optional[ResourcePoint]:
    points = catalog.get(vertiport_name, {}).get(category.upper(), [])
    return points[0] if points else None


def _resource_or_port_lla(
    resource: Optional[ResourcePoint],
    port: Any,
    fallback_ground_m: float,
    warnings: List[str],
    label: str,
) -> Dict[str, float]:
    if resource is not None:
        return _lla(resource.lat, resource.lon, resource.alt_m)
    warnings.append(f"Using {port.name} center as fallback for {label}.")
    return _lla(port.lat, port.lon, fallback_ground_m)


def _resolve_arrival_touchdown(
    route_data: Dict[str, Any],
    arrival_name: str,
    arr_port: Any,
    fallback_ground_m: float,
    warnings: List[str],
) -> Optional[Dict[str, float]]:
    touchdown = route_data.get("arrivalTouchdown") or {}
    lat = _coerce_float(touchdown.get("lat"))
    lon = _coerce_float(touchdown.get("lon"))
    alt = _coerce_float(touchdown.get("alt_m"))
    spawn_id = str(touchdown.get("spawn_point_id") or touchdown.get("spawnPointId") or "").strip().upper()
    if lat is not None and lon is not None:
        return _lla(lat, lon, alt if alt is not None else fallback_ground_m)

    try:
        spawn = get_vertiport_spawn_point(
            vertiport_name=arrival_name,
            vertiport_lat=float(arr_port.lat),
            vertiport_lon=float(arr_port.lon),
            vertiport_ground_m=fallback_ground_m,
            spawn_point_id=spawn_id or "S26",
        )
    except Exception:
        spawn = None

    if spawn is None:
        warnings.append(f"Arrival touchdown spawn S26 is unavailable for {arrival_name}; using arrival FATO.")
        return None

    return _lla(
        float(spawn["lat"]),
        float(spawn["lon"]),
        float(spawn.get("alt_m") or fallback_ground_m),
    )


def _derive_cruise_altitude(
    route_data: Dict[str, Any],
    default_altitude_m: float,
    dep_ground_alt: float,
    arr_ground_alt: float,
) -> float:
    candidates = [default_altitude_m, dep_ground_alt + 60.0, arr_ground_alt + 60.0]
    for item in route_data.get("waypoints") or []:
        alt = _coerce_float(item.get("alt_m"))
        if alt and alt > 0:
            candidates.append(alt)
    for item in route_data.get("points") or []:
        alt = _coerce_float(item.get("alt_m"))
        if alt and alt > 0:
            candidates.append(alt)
    return max(candidates)


def _node_lla(route_planner: RoutePlanner, name: str, alt_m: float) -> Dict[str, float]:
    if name in route_planner.ports:
        port = route_planner.ports[name]
        return _lla(port.lat, port.lon, alt_m)
    waypoint = route_planner.waypoints[name]
    return _lla(waypoint.lat, waypoint.lon, alt_m)


def _build_departure_turn(
    route_planner: RoutePlanner,
    departure_name: str,
    next_node_name: Optional[str],
    alt_m: float,
) -> Optional[Dict[str, Any]]:
    if not next_node_name or departure_name not in route_planner.ports:
        return None
    port = route_planner.ports[departure_name]
    radius = port.otr_km if port.otr_km > 0 else port.inr_km
    if radius <= 0:
        return None
    points_xy = route_planner._departure_arc_points(departure_name, next_node_name, 5)  # type: ignore[attr-defined]
    if len(points_xy) < 2:
        return None
    start_lon, start_lat = route_planner.projection.to_lonlat(*points_xy[0])
    end_lon, end_lat = route_planner.projection.to_lonlat(*points_xy[-1])
    return {
        "startLLA": _lla(start_lat, start_lon, alt_m),
        "endLLA": _lla(end_lat, end_lon, alt_m),
        "turnDirection": _map_turn_direction(port.turn_dir),
        "centerLLA": _lla(port.lat, port.lon, alt_m),
    }


def _build_arrival_turn(
    route_planner: RoutePlanner,
    prev_node_name: Optional[str],
    arrival_name: str,
    alt_m: float,
) -> Optional[Dict[str, Any]]:
    if not prev_node_name or arrival_name not in route_planner.ports:
        return None
    port = route_planner.ports[arrival_name]
    radius = port.inr_km if port.inr_km > 0 else port.otr_km
    if radius <= 0:
        return None
    points_xy = route_planner._arrival_arc_points(prev_node_name, arrival_name, 5)  # type: ignore[attr-defined]
    if len(points_xy) < 2:
        return None
    start_lon, start_lat = route_planner.projection.to_lonlat(*points_xy[0])
    end_lon, end_lat = route_planner.projection.to_lonlat(*points_xy[-1])
    return {
        "startLLA": _lla(start_lat, start_lon, alt_m),
        "endLLA": _lla(end_lat, end_lon, alt_m),
        "turnDirection": _map_turn_direction(port.turn_dir),
        "centerLLA": _lla(port.lat, port.lon, alt_m),
    }


def _append_segment(
    segments: List[Dict[str, Any]],
    seq: int,
    phase: str,
    start: Dict[str, float],
    end: Dict[str, float],
    speed_mps: float,
) -> int:
    segments.append({
        "seq": seq,
        "phase": phase,
        "startLLA": dict(start),
        "endLLA": dict(end),
        "targetSpeed": round(speed_mps, 1),
    })
    return seq + 1


def _lla(lat: float, lon: float, alt: float) -> Dict[str, float]:
    return {
        "lat": round(float(lat), 6),
        "lon": round(float(lon), 6),
        "alt": round(float(alt), 1),
    }


def _stage_altitude(ground_alt_m: float, cruise_alt_m: float, step_above_ground_m: float) -> float:
    return max(ground_alt_m, min(cruise_alt_m, ground_alt_m + step_above_ground_m))


def _phase_speed(phase: str, cruise_speed_mps: float) -> float:
    if phase in {"A", "K"}:
        return min(8.0, max(4.0, cruise_speed_mps * 0.25))
    if phase in {"B", "J"}:
        return min(12.0, max(6.0, cruise_speed_mps * 0.35))
    if phase in {"C", "I"}:
        return min(max(cruise_speed_mps * 0.55, 14.0), cruise_speed_mps)
    if phase in {"D", "H"}:
        return min(max(cruise_speed_mps * 0.7, 18.0), cruise_speed_mps)
    if phase in {"E", "G"}:
        return min(max(cruise_speed_mps * 0.8, 20.0), cruise_speed_mps)
    return max(cruise_speed_mps, 20.0)


def _estimate_segment_duration_sec(segment: Dict[str, Any]) -> float:
    start = segment["startLLA"]
    end = segment["endLLA"]
    speed_mps = max(_coerce_float(segment.get("targetSpeed")) or 1.0, 1.0)
    horizontal_m = _haversine_m(
        float(start["lon"]),
        float(start["lat"]),
        float(end["lon"]),
        float(end["lat"]),
    )
    vertical_m = abs(float(end["alt"]) - float(start["alt"]))
    distance_m = math.hypot(horizontal_m, vertical_m)
    phase = str(segment.get("phase") or "")
    return max(PHASE_MIN_DURATION_SEC.get(phase, 30.0), distance_m / speed_mps)


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2.0 * radius_m * math.atan2(math.sqrt(a), math.sqrt(max(1.0 - a, 0.0)))


def _map_turn_direction(turn_dir: Any) -> str:
    value = str(turn_dir or "").strip().upper()
    if value in {"L", "LEFT", "CCW"}:
        return "CCW"
    return "CW"


def _today_at(hms: str) -> datetime:
    hour, minute, second = [int(part) for part in hms.split(":")]
    now = datetime.now()
    return now.replace(hour=hour, minute=minute, second=second, microsecond=0)


def _normalize_hms(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"\d{2}:\d{2}", text):
        return f"{text}:00"
    if re.fullmatch(r"\d{2}:\d{2}:\d{2}", text):
        return text
    return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _label_sort_key(label: str) -> tuple[int, str]:
    match = re.search(r"(\d+)$", label)
    if match:
        return int(match.group(1)), label
    return 9999, label


def _build_filename(record: Dict[str, Any]) -> str:
    flight_plan_number = record.get("flightPlanNumber", "mission")
    aircraft_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(record.get("aircraftId") or "UAM0001"))
    return f"mission_icd_v1_{flight_plan_number}_{aircraft_id}.json"


def _icd_resource_label(label: Optional[str], prefix: str) -> str:
    text = str(label or "").strip().upper()
    match = re.search(r"(\d+)$", text)
    if match:
        return f"{prefix}{match.group(1)}"
    return f"{prefix}1"
