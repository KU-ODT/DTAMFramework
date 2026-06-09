from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

AIR_POINT_TYPES = {"takeoffPoint", "landingPoint", "commonAirPoint"}
ENTITY_TYPES = {"gate", "fato", "node", *AIR_POINT_TYPES}
FATO_MODES = {"both", "takeoff", "landing"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_default_simulation_parameters() -> dict[str, Any]:
    return {
        "vehicle": {
            "groundSpeedMps": 5,
            "airSpeedMps": 35,
            "verticalSpeedMps": 3,
        },
        "gateProcedure": {
            "engineStartAndTowDisconnectMinutes": 4,
            "engineStopAndTowConnectMinutes": 3,
            "groundHandlingMinutes": 10,
        },
        "fatoProcedure": {
            "postOperationLockMinutes": 1,
        },
    }


def validate_layout(layout: Any) -> str | None:
    if not isinstance(layout, dict):
        return "Layout must be an object."
    if not isinstance(layout.get("entities"), list):
        return "Layout entities must be an array."
    if not isinstance(layout.get("links"), list):
        return "Layout links must be an array."
    simulation_error = validate_simulation_parameters(layout.get("simulationParameters"))
    if simulation_error:
        return simulation_error

    entity_ids: set[str] = set()
    entities_by_id: dict[str, dict[str, Any]] = {}
    for entity in layout["entities"]:
        if not isinstance(entity, dict):
            return "Every entity must be an object."
        entity_id = entity.get("id")
        entity_type = entity.get("type")
        if not entity_id or entity_id in entity_ids:
            return "Every entity needs a unique id."
        if entity_type not in ENTITY_TYPES:
            return f"Unknown entity type: {entity_type}"
        if not is_number(entity.get("x")) or not is_number(entity.get("y")):
            return f"Invalid coordinates for {entity_id}."
        if entity_type == "fato" and entity.get("fatoMode", "both") not in FATO_MODES:
            return f"Invalid FATO mode for {entity_id}."
        if entity_type in AIR_POINT_TYPES and not is_number(entity.get("altitude")):
            return f"Invalid altitude for {entity_id}."
        entity_ids.add(entity_id)
        entities_by_id[entity_id] = entity

    link_ids: set[str] = set()
    for link in layout["links"]:
        if not isinstance(link, dict):
            return "Every link must be an object."
        link_id = link.get("id")
        source = link.get("from")
        target = link.get("to")
        if not link_id or link_id in link_ids:
            return "Every link needs a unique id."
        if source not in entity_ids or target not in entity_ids:
            return f"Link {link_id} references a missing entity."
        if source == target:
            return f"Link {link_id} cannot connect an entity to itself."
        link_error = validate_link_compatibility(entities_by_id[source], entities_by_id[target])
        if link_error:
            return f"{link_error} Invalid link: {link_id}."
        link_ids.add(link_id)

    return None


def validate_simulation_parameters(parameters: Any) -> str | None:
    if parameters is None:
        return None
    if not isinstance(parameters, dict):
        return "Simulation parameters must be an object."

    defaults = build_default_simulation_parameters()
    for section, fields in defaults.items():
        value = parameters.get(section)
        if value is None:
            continue
        if not isinstance(value, dict):
            return f"Simulation parameter section must be an object: {section}."
        for field in fields:
            if field in value and not is_number(value[field]):
                return f"Simulation parameter must be numeric: {section}.{field}."
            if field in value and float(value[field]) < 0:
                return f"Simulation parameter must be non-negative: {section}.{field}."
    return None


def validate_link_compatibility(source: dict[str, Any], target: dict[str, Any]) -> str | None:
    source_type = source["type"]
    target_type = target["type"]
    source_is_air_point = source_type in AIR_POINT_TYPES
    target_is_air_point = target_type in AIR_POINT_TYPES
    if not source_is_air_point and not target_is_air_point:
        return None

    if source_type == "fato" and target_is_air_point:
        fato = source
        air_point = target
    elif target_type == "fato" and source_is_air_point:
        fato = target
        air_point = source
    else:
        return "Takeoff and landing points can only connect to FATO."

    fato_mode = fato.get("fatoMode", "both")
    if air_point["type"] == "takeoffPoint" and fato_mode not in {"takeoff", "both"}:
        return "Takeoff points can only connect to takeoff or shared FATO."
    if air_point["type"] == "landingPoint" and fato_mode not in {"landing", "both"}:
        return "Landing points can only connect to landing or shared FATO."
    if air_point["type"] == "commonAirPoint" and fato_mode != "both":
        return "Common air points can only connect to shared FATO."
    return None


def normalize_layout(layout: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_layout_config(layout)
    normalized["simulationParameters"] = normalize_simulation_parameters(
        layout.get("simulationParameters")
    )
    return normalized


def normalize_layout_config(layout: dict[str, Any]) -> dict[str, Any]:
    grid = layout.get("grid") if isinstance(layout.get("grid"), dict) else {}
    normalized = {
        "meta": {
            "name": layout.get("meta", {}).get("name", "VP_Sim"),
            "updatedAt": utc_now(),
        },
        "grid": {
            "width": int(grid.get("width", 1000)),
            "height": int(grid.get("height", 720)),
            "size": int(grid.get("size", 20)),
            "unit": grid.get("unit", "m"),
        },
        "entities": deepcopy(layout["entities"]),
        "links": deepcopy(layout["links"]),
    }

    for entity in normalized["entities"]:
        entity["x"] = round(float(entity["x"]))
        entity["y"] = round(float(entity["y"]))
        if entity["type"] == "fato":
            entity["fatoMode"] = entity.get("fatoMode", "both")
        if entity["type"] in AIR_POINT_TYPES:
            entity["altitude"] = round(float(entity.get("altitude", 100)))

    return normalized


def normalize_simulation_parameters(parameters: Any) -> dict[str, Any]:
    normalized = deepcopy(build_default_simulation_parameters())
    if not isinstance(parameters, dict):
        return normalized

    for section, fields in normalized.items():
        provided_section = parameters.get(section)
        if not isinstance(provided_section, dict):
            continue
        for field, default_value in fields.items():
            if field not in provided_section or not is_number(provided_section[field]):
                continue
            value = float(provided_section[field])
            normalized[section][field] = round(value, 2) if value % 1 else int(value)
            if isinstance(default_value, int) and normalized[section][field] == round(value):
                normalized[section][field] = int(round(value))
    return normalized


def is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True
