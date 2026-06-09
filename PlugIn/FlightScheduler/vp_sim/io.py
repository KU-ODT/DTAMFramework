from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .analysis import build_simulation_analysis
from .simulation import run_vertiport_simulation
from .validation import (
    normalize_layout,
    normalize_simulation_parameters,
    utc_now,
    validate_layout,
    validate_simulation_parameters,
)


def read_json(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {resolved}")
    return payload


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_layout_bundle(layout_path: str | Path, sim_config_path: str | Path | None = None) -> dict[str, Any]:
    layout_payload = read_json(layout_path)
    sim_config = None
    if sim_config_path:
        sim_config = read_json(sim_config_path)
        if "simulationParameters" in sim_config and isinstance(sim_config["simulationParameters"], dict):
            sim_config = sim_config["simulationParameters"]

    parameters = sim_config if sim_config is not None else layout_payload.get("simulationParameters")
    parameters_error = validate_simulation_parameters(parameters)
    if parameters_error:
        raise ValueError(parameters_error)

    layout = deepcopy(layout_payload)
    layout["simulationParameters"] = normalize_simulation_parameters(parameters)
    layout_error = validate_layout(layout)
    if layout_error:
        raise ValueError(layout_error)
    return normalize_layout(layout)


def parse_time_minutes(value: str) -> int:
    try:
        hours_text, minutes_text = value.split(":", 1)
        hours = int(hours_text)
        minutes = int(minutes_text)
    except (ValueError, AttributeError) as error:
        raise ValueError(f"Time must use HH:MM format: {value}") from error
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise ValueError(f"Time must use HH:MM format: {value}")
    return hours * 60 + minutes


def operating_duration_minutes(start: str = "06:00", end: str = "22:00", duration_minutes: float | None = None) -> float:
    if duration_minutes is not None:
        return max(1.0, float(duration_minutes))
    start_minutes = parse_time_minutes(start)
    end_minutes = parse_time_minutes(end)
    duration = end_minutes - start_minutes if end_minutes > start_minutes else end_minutes + 24 * 60 - start_minutes
    return max(1.0, float(duration))


def count_type(layout: dict[str, Any], entity_type: str) -> int:
    return sum(1 for entity in layout.get("entities", []) if entity.get("type") == entity_type)


def build_analysis_payload(
    layout: dict[str, Any],
    start: str = "06:00",
    end: str = "22:00",
    duration_minutes: float | None = None,
    include_simulation_result: bool = True,
) -> dict[str, Any]:
    duration = operating_duration_minutes(start=start, end=end, duration_minutes=duration_minutes)
    simulation_result = run_vertiport_simulation(layout, {"durationMinutes": duration})
    analysis = build_simulation_analysis(simulation_result, {"startMinutes": parse_time_minutes(start)})
    payload = {
        "meta": {
            "name": "VP_Sim Analysis",
            "generatedAt": utc_now(),
        },
        "operatingWindow": {
            "start": start,
            "end": end,
            "durationMinutes": duration,
        },
        "layoutSummary": {
            "gates": count_type(layout, "gate"),
            "fatos": count_type(layout, "fato"),
            "nodes": count_type(layout, "node"),
            "takeoffPoints": count_type(layout, "takeoffPoint"),
            "landingPoints": count_type(layout, "landingPoint"),
            "commonAirPoints": count_type(layout, "commonAirPoint"),
            "links": len(layout.get("links", [])),
        },
        "parameters": deepcopy(layout["simulationParameters"]),
        "layout": deepcopy(layout),
        "warnings": simulation_result.get("warnings", []),
        "analysis": analysis,
    }
    if include_simulation_result:
        payload["simulationResult"] = simulation_result
    return payload


def run_analysis_from_files(
    layout_path: str | Path,
    output_path: str | Path,
    sim_config_path: str | Path | None = None,
    start: str = "06:00",
    end: str = "22:00",
    duration_minutes: float | None = None,
    include_simulation_result: bool = True,
) -> dict[str, Any]:
    layout = load_layout_bundle(layout_path, sim_config_path)
    payload = build_analysis_payload(
        layout,
        start=start,
        end=end,
        duration_minutes=duration_minutes,
        include_simulation_result=include_simulation_result,
    )
    write_json(output_path, payload)
    return payload
