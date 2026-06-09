"""CSV export service for the analysis tab.

The frontend runs the fast simulation and sends normalized rows here. This
service only handles durable file layout: flight-plan CSVs, supporting metric
CSVs, and a manifest for the export folder.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.config import ROOT_DIR


FPL_DIR = ROOT_DIR / "FPL"

# Canonical order for all flight-plan CSV exports. Per-vertiport files use the
# same schema as FPL_all.csv to avoid column drift.
FLIGHT_COLUMNS = [
    "scenario_id",
    "scenario_date",
    "fpl_id",
    "aircraft_id",
    "aircraft_type",
    "capacity",
    "passenger_count",
    "load_factor",
    "origin_vertiport_id",
    "origin_vertiport",
    "destination_vertiport_id",
    "destination_vertiport",
    "demand_hour",
    "departure_gate_id",
    "departure_fato_id",
    "arrival_gate_id",
    "arrival_fato_id",
    "gate_out_time",
    "takeoff_time",
    "landing_time",
    "gate_in_time",
    "ready_time",
    "gate_to_takeoff_sec",
    "air_time_sec",
    "landing_to_gate_sec",
    "gate_to_gate_sec",
    "departure_wait_sec",
    "arrival_wait_sec",
    "status",
]
FLIGHT_ROUTE_COLUMNS = [
    "route_path",
    "route_distance_km",
    "segment_count",
]
SEGMENT_COLUMN_RE = re.compile(r"^segment_(\d+)$")


def save_analysis_export(payload: dict[str, Any]) -> dict[str, Any]:
    """Write a single analysis run under FPL/{timestamp}_{scenario}."""
    scenario_id = _safe_text(payload.get("scenarioId") or payload.get("scenario_id") or "scenario")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = _unique_dir(FPL_DIR / f"{timestamp}_{_safe_filename(scenario_id)}")
    export_dir.mkdir(parents=True, exist_ok=False)
    metrics_dir = export_dir / "_metrics"
    metrics_dir.mkdir(exist_ok=True)

    flights = list(payload.get("flights") or [])
    hourly = list(payload.get("hourlyMetrics") or [])
    type_metrics = list(payload.get("typeMetrics") or [])
    bottlenecks = list(payload.get("bottlenecks") or [])
    resource_events = list(payload.get("resourceEvents") or [])
    flight_columns = _flight_columns(flights)

    saved: list[str] = []
    saved.append(_write_csv(export_dir / "FPL_all.csv", flights, flight_columns))

    by_origin: dict[str, list[dict[str, Any]]] = {}
    for row in flights:
        key = str(row.get("origin_vertiport_id") or row.get("origin_vertiport") or "unknown")
        by_origin.setdefault(key, []).append(row)
    used_fpl_filenames = {"FPL_all.csv"}
    vertiport_files: list[str] = []
    for origin_id, rows in sorted(by_origin.items()):
        label = rows[0].get("origin_vertiport") or origin_id
        filename = _unique_filename(f"FPL_{_safe_filename(label)}.csv", used_fpl_filenames)
        path = _write_csv(export_dir / filename, rows, flight_columns)
        saved.append(path)
        vertiport_files.append(path)

    saved.append(_write_csv(metrics_dir / "hourly_vertiport_metrics.csv", hourly))
    saved.append(_write_csv(metrics_dir / "aircraft_type_contribution.csv", type_metrics))
    saved.append(_write_csv(metrics_dir / "bottlenecks.csv", bottlenecks))
    saved.append(_write_csv(metrics_dir / "resource_gantt.csv", resource_events))
    scheduled_flight_files = _write_scheduled_flight_json_files(export_dir, flights)
    saved.extend(scheduled_flight_files)

    manifest = {
        "scenarioId": scenario_id,
        "scenarioDate": payload.get("scenarioDate"),
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "exportDirectory": str(export_dir),
        "primaryFplFile": str(export_dir / "FPL_all.csv"),
        "vertiportFplFiles": vertiport_files,
        "scheduledFlightDirectory": str(export_dir / "ScheduledFlight") if scheduled_flight_files else None,
        "scheduledFlightFiles": scheduled_flight_files,
        "primaryScheduledFlightFile": scheduled_flight_files[0] if scheduled_flight_files else None,
        "files": saved,
        "counts": {
            "flights": len(flights),
            "scheduledFlightJson": len(scheduled_flight_files),
            "hourlyMetrics": len(hourly),
            "typeMetrics": len(type_metrics),
            "bottlenecks": len(bottlenecks),
            "resourceEvents": len(resource_events),
            "vertiportFiles": len(by_origin),
        },
    }
    (export_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    saved.append(str(export_dir / "manifest.json"))
    manifest["files"] = saved
    return manifest


def _flight_columns(flights: list[dict[str, Any]]) -> list[str]:
    segment_columns = sorted(
        {
            key
            for row in flights
            for key in row.keys()
            if SEGMENT_COLUMN_RE.match(str(key))
        },
        key=lambda key: int(SEGMENT_COLUMN_RE.match(str(key)).group(1)),  # type: ignore[union-attr]
    )
    return [*FLIGHT_COLUMNS, *FLIGHT_ROUTE_COLUMNS, *segment_columns]


def _write_scheduled_flight_json_files(export_dir: Path, flights: list[dict[str, Any]]) -> list[str]:
    scheduled_dir = export_dir / "ScheduledFlight"
    used_filenames: set[str] = set()
    saved: list[str] = []
    for row in flights:
        payload = _build_scheduled_flight_payload(row)
        if not payload:
            continue
        scheduled_dir.mkdir(exist_ok=True)
        filename = _unique_filename(
            f"{_safe_filename(payload.get('flightPlanNumber'))}_{_safe_filename(payload.get('aircraftId') or 'UNKNOWN')}.json",
            used_filenames,
        )
        path = scheduled_dir / filename
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        saved.append(str(path))
    return saved


def _build_scheduled_flight_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    source = _json_like(row.get("_scheduledFlight") or row.get("scheduledFlight") or row.get("scheduled_flight"))
    if not isinstance(source, dict):
        source = {}

    en_route = _normalize_en_route(
        source.get("enRoute")
        or row.get("_enRouteSegments")
        or row.get("en_route")
        or _segments_from_columns(row)
    )
    if not en_route:
        return None

    departure_source = _json_like(source.get("departure"))
    if not isinstance(departure_source, dict):
        departure_source = {}
    arrival_source = _json_like(source.get("arrival"))
    if not isinstance(arrival_source, dict):
        arrival_source = {}

    return {
        "flightPlanNumber": _int_value(source.get("flightPlanNumber")) or _flight_plan_number(row),
        "planVersion": max(1, _int_value(source.get("planVersion")) or 1),
        "planStatus": _text(source.get("planStatus") or "active"),
        "aircraftId": _text(source.get("aircraftId") or row.get("aircraft_id")),
        "departure": {
            "vertiport": _text(departure_source.get("vertiport") or row.get("origin_vertiport")),
            "std": _text(departure_source.get("std") or row.get("gate_out_time") or row.get("takeoff_time")),
            "depGateNumber": _facility_number(departure_source.get("depGateNumber") or row.get("departure_gate_id"), "G"),
            "eobt": _text(departure_source.get("eobt") or row.get("gate_out_time")),
            "depFatoNumber": _facility_number(departure_source.get("depFatoNumber") or row.get("departure_fato_id"), "F"),
            "etot": _text(departure_source.get("etot") or row.get("takeoff_time")),
        },
        "enRoute": en_route,
        "arrival": {
            "vertiport": _text(arrival_source.get("vertiport") or row.get("destination_vertiport")),
            "sta": _text(arrival_source.get("sta") or row.get("gate_in_time") or row.get("landing_time")),
            "arrGateNumber": _facility_number(arrival_source.get("arrGateNumber") or row.get("arrival_gate_id"), "G"),
            "eibt": _text(arrival_source.get("eibt") or row.get("gate_in_time")),
            "arrFatoNumber": _facility_number(arrival_source.get("arrFatoNumber") or row.get("arrival_fato_id"), "F"),
            "eldt": _text(arrival_source.get("eldt") or row.get("landing_time")),
        },
    }


def _normalize_en_route(value: Any) -> list[dict[str, Any]]:
    items = _json_like(value)
    if not isinstance(items, list):
        return []
    segments: list[dict[str, Any]] = []
    for item in items:
        segment_source = _json_like(item)
        if not isinstance(segment_source, dict):
            continue
        phase = _text(segment_source.get("phase")).upper()[:1]
        start_lla = _normalize_lla(segment_source.get("startLLA") or segment_source.get("start_lla"))
        end_lla = _normalize_lla(segment_source.get("endLLA") or segment_source.get("end_lla"))
        if not phase or not start_lla or not end_lla:
            continue
        segment = {
            "seq": len(segments) + 1,
            "phase": phase,
            "startLLA": start_lla,
            "endLLA": end_lla,
            "targetSpeed": round(_float_value(segment_source.get("targetSpeed")) or 0.0, 3),
        }
        turn_direction = _text(segment_source.get("turnDirection")).upper()
        center_lla = _normalize_lla(segment_source.get("centerLLA"))
        if turn_direction in {"CW", "CCW"} and center_lla:
            segment["turnDirection"] = turn_direction
            segment["centerLLA"] = center_lla
        segments.append(segment)
    return segments


def _segments_from_columns(row: dict[str, Any]) -> list[Any]:
    columns = sorted(
        (key for key in row.keys() if SEGMENT_COLUMN_RE.match(str(key))),
        key=lambda key: int(SEGMENT_COLUMN_RE.match(str(key)).group(1)),  # type: ignore[union-attr]
    )
    return [row.get(key) for key in columns if row.get(key)]


def _normalize_lla(value: Any) -> dict[str, float] | None:
    data = _json_like(value)
    if isinstance(data, dict):
        lat = _float_value(data.get("lat"))
        lon = _float_value(data.get("lon"))
        alt = _float_value(data.get("alt"))
    elif isinstance(data, list) and len(data) >= 2:
        lat = _float_value(data[0])
        lon = _float_value(data[1])
        alt = _float_value(data[2] if len(data) >= 3 else 0)
    else:
        return None
    if lat is None or lon is None or alt is None:
        return None
    return {"lat": round(lat, 6), "lon": round(lon, 6), "alt": round(alt, 2)}


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> str:
    if columns is None:
        columns = _collect_columns(rows)
    with path.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in columns})
    return str(path)


def _collect_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key in seen:
                continue
            seen.add(key)
            columns.append(key)
    return columns or ["empty"]


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "" if value is None else value


def _json_like(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int_value(value: Any) -> int | None:
    try:
        numeric = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


def _float_value(value: Any) -> float | None:
    try:
        numeric = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return numeric if numeric == numeric else None


def _facility_number(value: Any, prefix: str) -> str:
    text = _text(value)
    if not text:
        return ""
    code = prefix.upper()
    upper = text.upper()
    if re.fullmatch(rf"{re.escape(code)}\d+", upper):
        return upper
    match = re.search(r"\d+", text)
    if match:
        return f"{code}{int(match.group(0))}"
    return text


def _flight_plan_number(row: dict[str, Any]) -> int:
    explicit = _int_value(row.get("flightPlanNumber") or row.get("flight_plan_number"))
    if explicit:
        return explicit
    digits = "".join(re.findall(r"\d+", _text(row.get("fpl_id"))))
    if digits:
        return int(digits)
    sequence = _int_value(row.get("sequence"))
    return sequence or 1


def _safe_text(value: Any) -> str:
    return str(value or "").strip() or "scenario"


def _safe_filename(value: Any) -> str:
    text = _safe_text(value)
    text = re.sub(r'[<>:"/\\|?*]+', "_", text)
    text = re.sub(r"\s+", "_", text)
    return text[:80] or "item"


def _unique_filename(filename: str, used: set[str]) -> str:
    path = Path(filename)
    stem = path.stem
    suffix = path.suffix
    candidate = filename
    index = 2
    while candidate in used:
        candidate = f"{stem}_{index:02d}{suffix}"
        index += 1
    used.add(candidate)
    return candidate


def _unique_dir(base: Path) -> Path:
    if not base.exists():
        return base
    for index in range(2, 1000):
        candidate = Path(f"{base}_{index:02d}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create unique export directory under {base.parent}")
