"""Scenario data loading and derived payload helpers for PSU Monitoring SW."""
from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1]
MODULE_ROOT = APP_DIR.parent
EXTENSION_ROOT = MODULE_ROOT.parent
FRAMEWORK_ROOT = EXTENSION_ROOT.parent
OPERATION_MODULE_ROOT = FRAMEWORK_ROOT / "OperationModule"
DATA_DIR = MODULE_ROOT / "data"
DEFAULT_SCENARIO_PATH = DATA_DIR / "scenarios" / "seoul_psu_demo.json"


def _items(scenario: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = scenario.get(key)
    return value if isinstance(value, list) else []


@lru_cache(maxsize=4)
def _load_scenario_cached(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Scenario root must be an object: {path}")
    return data


def load_scenario(path: Path = DEFAULT_SCENARIO_PATH) -> dict[str, Any]:
    """Return a defensive copy of the scenario JSON payload."""
    return copy.deepcopy(_load_scenario_cached(str(path)))


def list_scenarios() -> list[dict[str, Any]]:
    scenarios_dir = DATA_DIR / "scenarios"
    items: list[dict[str, Any]] = []
    for path in sorted(scenarios_dir.glob("*.json")):
        try:
            scenario = _load_scenario_cached(str(path))
        except Exception:
            continue
        items.append(
            {
                "scenario_id": scenario.get("scenario_id") or path.stem,
                "name": scenario.get("name") or path.stem,
                "description": scenario.get("description") or "",
                "path": str(path),
                "schema_version": scenario.get("schema_version") or "",
            }
        )
    return items


def scenario_metadata(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": scenario.get("scenario_id"),
        "name": scenario.get("name"),
        "description": scenario.get("description"),
        "schema_version": scenario.get("schema_version"),
        "created_at": scenario.get("created_at"),
        "current_time": scenario.get("current_time"),
        "source_notes": scenario.get("source_notes", []),
        "counts": {
            "waypoints": len(_items(scenario, "waypoints")),
            "corridors": len(_items(scenario, "corridors")),
            "vertiports": len(_items(scenario, "vertiports")),
            "flight_plans": len(_items(scenario, "flight_plans")),
            "track_states": len(_items(scenario, "track_states")),
            "conflict_events": len(_items(scenario, "conflict_events")),
            "capacity_metrics": len(_items(scenario, "capacity_metrics")),
            "event_logs": len(_items(scenario, "event_logs")),
        },
    }


def overview_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    tracks = _items(scenario, "track_states")
    flight_plans = _items(scenario, "flight_plans")
    conflicts = _items(scenario, "conflict_events")
    capacity_metrics = _items(scenario, "capacity_metrics")
    vertiports = _items(scenario, "vertiports")
    events = _items(scenario, "event_logs")

    active_uam = sum(1 for item in tracks if str(item.get("flight_status", "")).upper() == "ACTIVE")
    pending_intent = sum(1 for item in flight_plans if "PENDING" in str(item.get("status", "")).upper())
    conflict_alert = sum(1 for item in conflicts if str(item.get("severity", "")).upper() in {"CAUTION", "WARNING"})
    capacity_alert = sum(1 for item in capacity_metrics if str(item.get("status", "")).upper() in {"CAUTION", "WARNING"})
    delays = [float(item.get("average_delay_sec") or 0) for item in vertiports]
    average_delay_sec = round(sum(delays) / len(delays)) if delays else 0
    max_delay_sec = round(max(delays)) if delays else 0
    off_nominal_event = sum(1 for item in events if str(item.get("severity", "")).upper() in {"CAUTION", "WARNING"})
    traffic_trend = scenario.get("traffic_trend", [])
    top_priority_events = priority_events(scenario)
    capacity_hotspots = sorted(
        capacity_metrics,
        key=lambda item: float(item.get("utilization") or 0),
        reverse=True,
    )[:3]
    critical_vertiports = sorted(
        [
            item
            for item in vertiports
            if str(item.get("status", "")).upper() in {"CAUTION", "WARNING"}
        ],
        key=lambda item: (
            str(item.get("status", "")).upper() == "WARNING",
            float(item.get("average_delay_sec") or 0),
        ),
        reverse=True,
    )

    return {
        "scenario": scenario_metadata(scenario),
        "kpis": {
            "active_uam": active_uam,
            "pending_intent": pending_intent,
            "conflict_alert": conflict_alert,
            "capacity_alert": capacity_alert,
            "average_delay_sec": average_delay_sec,
            "max_delay_sec": max_delay_sec,
            "off_nominal_event": off_nominal_event,
            "data_link_health": "SIMULATED",
        },
        "status_summary": {
            "event_severity": _count_by(events, "severity"),
            "vertiport_status": _count_by(vertiports, "status"),
            "corridor_status": _count_by(_items(scenario, "corridors"), "status"),
            "flight_plan_status": _count_by(flight_plans, "status"),
            "track_status": _count_by(tracks, "flight_status"),
        },
        "traffic_summary": {
            "peak_active_flights": max([int(item.get("active_flights") or 0) for item in traffic_trend], default=active_uam),
            "peak_conflict_count": max([int(item.get("conflict_count") or 0) for item in traffic_trend], default=conflict_alert),
            "peak_average_delay_sec": max([int(item.get("average_delay_sec") or 0) for item in traffic_trend], default=average_delay_sec),
            "trend_points": len(traffic_trend),
        },
        "map_summary": {
            "track_count": len(tracks),
            "route_count": len(flight_plans),
            "vertiport_count": len(vertiports),
            "corridor_count": len(_items(scenario, "corridors")),
            "conflict_count": len(conflicts),
            "actual_track_count": len(tracks),
            "warning_corridors": sum(1 for item in _items(scenario, "corridors") if str(item.get("status", "")).upper() == "WARNING"),
        },
        "top_priority_event": top_priority_events[0] if top_priority_events else None,
        "capacity_hotspots": capacity_hotspots,
        "critical_vertiports": critical_vertiports,
        "priority_events": top_priority_events,
        "vertiport_summary": vertiports,
        "traffic_trend": traffic_trend,
        "generated_at": scenario.get("current_time"),
    }


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "UNKNOWN").upper()
        counts[value] = counts.get(value, 0) + 1
    return counts


def priority_events(scenario: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    events = _items(scenario, "event_logs")
    return sorted(
        events,
        key=lambda item: (
            int(item.get("priority_score") or 0),
            str(item.get("expected_time") or ""),
        ),
        reverse=True,
    )[:limit]


def capacity_summary(scenario: dict[str, Any]) -> dict[str, Any]:
    metrics = _items(scenario, "capacity_metrics")
    warnings = [item for item in metrics if str(item.get("status", "")).upper() == "WARNING"]
    cautions = [item for item in metrics if str(item.get("status", "")).upper() == "CAUTION"]
    return {
        "metrics": metrics,
        "warning_count": len(warnings),
        "caution_count": len(cautions),
        "max_utilization": max([float(item.get("utilization") or 0) for item in metrics], default=0),
        "generated_at": scenario.get("current_time"),
    }


def flow_capacity_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    """Build the Flow & Capacity view model from the static demo scenario."""
    metrics = _items(scenario, "capacity_metrics")
    corridors = _items(scenario, "corridors")
    vertiports = _items(scenario, "vertiports")
    flight_plans = _items(scenario, "flight_plans")
    events = _items(scenario, "event_logs")

    metric_by_target = {str(item.get("target_id")): item for item in metrics if item.get("target_id")}
    flow_events = [
        item
        for item in events
        if "FLOW" in str(item.get("recommended_screen", "")).upper()
        or "CAPACITY" in str(item.get("event_type", "")).upper()
        or "DENSITY" in str(item.get("event_type", "")).upper()
        or "DEVIATION" in str(item.get("event_type", "")).upper()
    ]

    demand_capacity_series = sorted(
        [
            {
                "target_type": item.get("target_type"),
                "target_id": item.get("target_id"),
                "time_window_start": item.get("time_window_start"),
                "time_window_end": item.get("time_window_end"),
                "time_label": _window_label(item.get("time_window_start"), item.get("time_window_end")),
                "demand": int(item.get("demand") or 0),
                "capacity": int(item.get("capacity") or 0),
                "utilization": float(item.get("utilization") or 0),
                "overload": max(0, int(item.get("demand") or 0) - int(item.get("capacity") or 0)),
                "status": str(item.get("status") or "UNKNOWN").upper(),
            }
            for item in metrics
        ],
        key=lambda item: (str(item.get("time_window_start") or ""), -float(item.get("utilization") or 0)),
    )

    corridor_density = []
    for corridor in corridors:
        corridor_id = str(corridor.get("corridor_id"))
        metric = metric_by_target.get(corridor_id, {})
        route_ids = {str(item) for item in corridor.get("route_ids") or []}
        related_flights = [
            plan
            for plan in flight_plans
            if str(plan.get("route_id")) in route_ids
        ]
        density_ratio = float(corridor.get("density_ratio") or 0)
        utilization = max(density_ratio, float(metric.get("utilization") or 0))
        corridor_density.append(
            {
                "target_type": "CORRIDOR",
                "target_id": corridor_id,
                "name": corridor.get("name"),
                "route_ids": sorted(route_ids),
                "capacity": int(corridor.get("capacity") or metric.get("capacity") or 0),
                "occupied_aircraft": int(corridor.get("occupied_aircraft") or 0),
                "density_ratio": density_ratio,
                "demand": int(metric.get("demand") or corridor.get("occupied_aircraft") or 0),
                "utilization": utilization,
                "overload": max(0, int(metric.get("demand") or 0) - int(metric.get("capacity") or corridor.get("capacity") or 0)),
                "status": str(corridor.get("status") or metric.get("status") or "UNKNOWN").upper(),
                "time_window": _window_label(metric.get("time_window_start"), metric.get("time_window_end")),
                "affected_aircraft": [plan.get("aircraft_id") for plan in related_flights],
                "flight_count": len(related_flights),
                "diagnosis": _diagnose_corridor(corridor, metric),
            }
        )

    vertiport_throughput = []
    for vertiport in vertiports:
        vertiport_id = str(vertiport.get("vertiport_id"))
        metric = metric_by_target.get(vertiport_id, {})
        inbound = [plan for plan in flight_plans if str(plan.get("destination_vertiport")) == vertiport_id]
        outbound = [plan for plan in flight_plans if str(plan.get("origin_vertiport")) == vertiport_id]
        fato_occupancy = _resource_occupancy(vertiport.get("fato_available"), vertiport.get("fato_total"))
        gate_occupancy = _resource_occupancy(vertiport.get("gate_available"), vertiport.get("gate_total"))
        charging_occupancy = _resource_occupancy(vertiport.get("charging_spot_available"), vertiport.get("charging_spot_total"))
        utilization = max(
            float(metric.get("utilization") or 0),
            fato_occupancy,
            gate_occupancy,
            charging_occupancy,
        )
        arrival_demand = len(inbound) + int(vertiport.get("arrival_queue") or 0)
        departure_demand = len(outbound) + int(vertiport.get("departure_queue") or 0)
        vertiport_throughput.append(
            {
                "target_type": "VERTIPORT",
                "target_id": vertiport_id,
                "name": vertiport.get("name"),
                "status": str(vertiport.get("status") or metric.get("status") or "UNKNOWN").upper(),
                "arrival_demand": arrival_demand,
                "departure_demand": departure_demand,
                "planned_arrivals": len(inbound),
                "planned_departures": len(outbound),
                "arrival_queue": int(vertiport.get("arrival_queue") or 0),
                "departure_queue": int(vertiport.get("departure_queue") or 0),
                "average_delay_sec": int(vertiport.get("average_delay_sec") or 0),
                "demand": int(metric.get("demand") or arrival_demand + departure_demand),
                "capacity": int(metric.get("capacity") or max(1, int(vertiport.get("fato_total") or 0) * 6)),
                "utilization": utilization,
                "overload": max(0, int(metric.get("demand") or 0) - int(metric.get("capacity") or 0)),
                "fato_occupancy": fato_occupancy,
                "gate_occupancy": gate_occupancy,
                "charging_occupancy": charging_occupancy,
                "time_window": _window_label(metric.get("time_window_start"), metric.get("time_window_end")),
                "affected_aircraft": [plan.get("aircraft_id") for plan in inbound + outbound],
                "bottleneck_cause": _diagnose_vertiport(vertiport, metric),
            }
        )

    resource_candidates = [
        *corridor_density,
        *vertiport_throughput,
    ]
    ranked_resources = sorted(
        resource_candidates,
        key=lambda item: (
            _status_weight(item.get("status")),
            float(item.get("utilization") or 0),
            int(item.get("average_delay_sec") or 0),
        ),
        reverse=True,
    )
    main_bottleneck = ranked_resources[0] if ranked_resources else None
    bottleneck_diagnosis = _bottleneck_diagnosis(main_bottleneck, flow_events)
    delay_propagation = _delay_propagation_events(scenario, flow_events, vertiport_throughput, corridor_density)

    total_demand = sum(int(item.get("demand") or 0) for item in metrics)
    total_capacity = sum(int(item.get("capacity") or 0) for item in metrics)
    warning_count = sum(1 for item in metrics if str(item.get("status")).upper() == "WARNING")
    caution_count = sum(1 for item in metrics if str(item.get("status")).upper() == "CAUTION")

    return {
        "scenario": scenario_metadata(scenario),
        "analysis_condition": {
            "time_window_start": min([str(item.get("time_window_start")) for item in metrics if item.get("time_window_start")], default=scenario.get("current_time")),
            "time_window_end": max([str(item.get("time_window_end")) for item in metrics if item.get("time_window_end")], default=scenario.get("current_time")),
            "interval_min": 5,
            "target_scope": "All network resources",
            "scenario_mode": "Baseline static demo",
            "generated_at": scenario.get("current_time"),
        },
        "summary": {
            "total_demand": total_demand,
            "total_capacity": total_capacity,
            "network_utilization": round(total_demand / total_capacity, 3) if total_capacity else 0,
            "warning_count": warning_count,
            "caution_count": caution_count,
            "max_utilization": max([float(item.get("utilization") or 0) for item in metrics], default=0),
            "main_bottleneck_id": main_bottleneck.get("target_id") if main_bottleneck else None,
            "main_bottleneck_type": main_bottleneck.get("target_type") if main_bottleneck else None,
            "main_bottleneck_cause": bottleneck_diagnosis.get("cause") if bottleneck_diagnosis else None,
            "delay_event_count": len(delay_propagation),
        },
        "demand_capacity_series": demand_capacity_series,
        "corridor_density": corridor_density,
        "vertiport_throughput": vertiport_throughput,
        "delay_propagation": delay_propagation,
        "bottleneck_diagnosis": bottleneck_diagnosis,
        "capacity_events": priority_events({"event_logs": flow_events}, limit=10),
        "generated_at": scenario.get("current_time"),
    }


def map_layers(scenario: dict[str, Any]) -> dict[str, Any]:
    waypoint_lookup = {
        str(item.get("waypoint_id")): item
        for item in _items(scenario, "waypoints")
        if item.get("waypoint_id")
    }
    vertiport_lookup = {
        str(item.get("vertiport_id")): item
        for item in _items(scenario, "vertiports")
        if item.get("vertiport_id")
    }

    def point_feature(item: dict[str, Any], feature_type: str, id_key: str) -> dict[str, Any] | None:
        lat = item.get("latitude")
        lon = item.get("longitude")
        if lat is None or lon is None:
            return None
        properties = {key: value for key, value in item.items() if key not in {"latitude", "longitude"}}
        properties["feature_type"] = feature_type
        return {
            "type": "Feature",
            "id": item.get(id_key),
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": properties,
        }

    vertiport_features = [
        feature
        for item in _items(scenario, "vertiports")
        if (feature := point_feature(item, "vertiport", "vertiport_id")) is not None
    ]
    track_features = [
        feature
        for item in _items(scenario, "track_states")
        if (feature := point_feature(item, "track", "aircraft_id")) is not None
    ]
    waypoint_features = [
        feature
        for item in _items(scenario, "waypoints")
        if (feature := point_feature(item, "waypoint", "waypoint_id")) is not None
    ]
    node_features = []
    for feature in waypoint_features:
        node = copy.deepcopy(feature)
        node["id"] = f"node-{feature.get('id')}"
        node_properties = dict(node.get("properties") or {})
        node_properties["feature_type"] = "node"
        node_properties["node_id"] = node_properties.get("waypoint_id")
        node_properties["node_kind"] = "WAYPOINT"
        node["properties"] = node_properties
        node_features.append(node)

    corridor_features = []
    link_features = []
    for item in _items(scenario, "corridors"):
        coordinates = item.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        corridor_features.append(
            {
                "type": "Feature",
                "id": item.get("corridor_id"),
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": {key: value for key, value in item.items() if key != "coordinates"},
            }
        )
        link_properties = {key: value for key, value in item.items() if key != "coordinates"}
        link_properties.update(
            {
                "feature_type": "node_link",
                "link_type": "CORRIDOR",
                "link_id": item.get("corridor_id"),
            }
        )
        link_features.append(
            {
                "type": "Feature",
                "id": f"link-{item.get('corridor_id')}",
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": link_properties,
            }
        )

    route_features = []
    plan_by_id: dict[str, dict[str, Any]] = {}
    corridor_by_route: dict[str, dict[str, Any]] = {}
    for corridor in _items(scenario, "corridors"):
        for route_id in corridor.get("route_ids") or []:
            corridor_by_route[str(route_id)] = corridor

    for plan in _items(scenario, "flight_plans"):
        plan_by_id[str(plan.get("flight_plan_id"))] = plan
        coordinates: list[list[float]] = []
        for waypoint_id in plan.get("waypoints") or []:
            waypoint = waypoint_lookup.get(str(waypoint_id))
            if not waypoint:
                continue
            coordinates.append([float(waypoint["longitude"]), float(waypoint["latitude"])])
        if len(coordinates) < 2:
            continue
        route_features.append(
            {
                "type": "Feature",
                "id": plan.get("flight_plan_id"),
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": {
                    "feature_type": "route",
                    "flight_plan_id": plan.get("flight_plan_id"),
                    "aircraft_id": plan.get("aircraft_id"),
                    "route_id": plan.get("route_id"),
                    "status": plan.get("status"),
                    "origin_vertiport": plan.get("origin_vertiport"),
                    "destination_vertiport": plan.get("destination_vertiport"),
                },
            }
        )

    actual_track_features = []
    for track in _items(scenario, "track_states"):
        current_lat = track.get("latitude")
        current_lon = track.get("longitude")
        if current_lat is None or current_lon is None:
            continue
        current_coordinate = [float(current_lon), float(current_lat)]
        plan = plan_by_id.get(str(track.get("flight_plan_id")))
        coordinates: list[list[float]] = []
        if plan:
            route_points = [
                [float(waypoint["longitude"]), float(waypoint["latitude"])]
                for waypoint_id in plan.get("waypoints") or []
                if (waypoint := waypoint_lookup.get(str(waypoint_id))) is not None
            ]
            if route_points:
                nearest_idx = min(
                    range(len(route_points)),
                    key=lambda idx: (route_points[idx][0] - current_coordinate[0]) ** 2
                    + (route_points[idx][1] - current_coordinate[1]) ** 2,
                )
                coordinates.extend(route_points[: nearest_idx + 1])
        if not coordinates:
            origin_id = str(plan.get("origin_vertiport")) if plan else ""
            origin = vertiport_lookup.get(origin_id)
            if origin:
                coordinates.append([float(origin["longitude"]), float(origin["latitude"])])
        if not coordinates or coordinates[-1] != current_coordinate:
            coordinates.append(current_coordinate)
        if len(coordinates) < 2:
            continue
        actual_track_features.append(
            {
                "type": "Feature",
                "id": f"{track.get('aircraft_id')}-history",
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": {
                    "feature_type": "actual_track",
                    "aircraft_id": track.get("aircraft_id"),
                    "flight_plan_id": track.get("flight_plan_id"),
                    "status": track.get("flight_status"),
                    "timestamp": track.get("timestamp"),
                },
            }
        )

    conflict_features = []
    for conflict in _items(scenario, "conflict_events"):
        location_id = str(conflict.get("location_id") or "")
        coordinate: list[float] | None = None
        waypoint = waypoint_lookup.get(location_id)
        if waypoint:
            coordinate = [float(waypoint["longitude"]), float(waypoint["latitude"])]
        else:
            corridor = next(
                (item for item in _items(scenario, "corridors") if str(item.get("corridor_id")) == location_id),
                None,
            )
            if corridor and corridor.get("coordinates"):
                coordinates = corridor.get("coordinates") or []
                coordinate = list(coordinates[len(coordinates) // 2])
            else:
                vertiport = vertiport_lookup.get(location_id)
                if vertiport:
                    coordinate = [float(vertiport["longitude"]), float(vertiport["latitude"])]
        if coordinate is None:
            continue
        conflict_features.append(
            {
                "type": "Feature",
                "id": conflict.get("conflict_id"),
                "geometry": {"type": "Point", "coordinates": coordinate},
                "properties": {
                    "feature_type": "conflict",
                    "conflict_id": conflict.get("conflict_id"),
                    "conflict_type": conflict.get("conflict_type"),
                    "location_id": conflict.get("location_id"),
                    "related_aircraft": ",".join(conflict.get("related_aircraft") or []),
                    "predicted_time": conflict.get("predicted_time"),
                    "eta_gap_sec": conflict.get("eta_gap_sec"),
                    "required_gap_sec": conflict.get("required_gap_sec"),
                    "severity": conflict.get("severity"),
                    "status": conflict.get("severity"),
                },
            }
        )

    return {
        "generated_at": scenario.get("current_time"),
        "vertiports": _feature_collection(vertiport_features),
        "tracks": _feature_collection(track_features),
        "waypoints": _feature_collection(waypoint_features),
        "nodes": _feature_collection(node_features),
        "links": _feature_collection(link_features),
        "corridors": _feature_collection(corridor_features),
        "routes": _feature_collection(route_features),
        "actual_tracks": _feature_collection(actual_track_features),
        "conflicts": _feature_collection(conflict_features),
    }


def _feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def traffic_conflict_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    """Build the Traffic Map / Conflict view model."""
    flight_plans = _items(scenario, "flight_plans")
    tracks = _items(scenario, "track_states")
    conflicts = _items(scenario, "conflict_events")
    events = _items(scenario, "event_logs")
    waypoints = _items(scenario, "waypoints")
    vertiports = _items(scenario, "vertiports")
    corridors = _items(scenario, "corridors")

    track_by_aircraft = {str(item.get("aircraft_id")): item for item in tracks}
    conflict_by_aircraft: dict[str, list[dict[str, Any]]] = {}
    for conflict in conflicts:
        for aircraft_id in conflict.get("related_aircraft") or []:
            conflict_by_aircraft.setdefault(str(aircraft_id), []).append(conflict)

    vertiport_by_id = {str(item.get("vertiport_id")): item for item in vertiports}
    waypoint_by_id = {str(item.get("waypoint_id")): item for item in waypoints}
    corridor_by_id = {str(item.get("corridor_id")): item for item in corridors}
    corridor_by_route: dict[str, dict[str, Any]] = {}
    for corridor in corridors:
        for route_id in corridor.get("route_ids") or []:
            corridor_by_route[str(route_id)] = corridor

    flights = []
    planned_aircraft: set[str] = set()
    for plan in flight_plans:
        aircraft_id = str(plan.get("aircraft_id"))
        planned_aircraft.add(aircraft_id)
        related_conflicts = conflict_by_aircraft.get(aircraft_id, [])
        severities = [str(item.get("severity") or "NORMAL").upper() for item in related_conflicts]
        severity = "WARNING" if "WARNING" in severities else "CAUTION" if "CAUTION" in severities else "NORMAL"
        track = track_by_aircraft.get(aircraft_id)
        corridor = corridor_by_route.get(str(plan.get("route_id")))
        delay_sec = _delay_sec_from_events(events, aircraft_id, str(plan.get("flight_plan_id")))
        flights.append(
            {
                "flight_plan_id": plan.get("flight_plan_id"),
                "aircraft_id": aircraft_id,
                "operator_id": plan.get("operator_id"),
                "route_id": plan.get("route_id"),
                "current_corridor_id": corridor.get("corridor_id") if corridor else None,
                "current_corridor_name": corridor.get("name") if corridor else None,
                "origin_vertiport": plan.get("origin_vertiport"),
                "origin_name": vertiport_by_id.get(str(plan.get("origin_vertiport")), {}).get("name"),
                "destination_vertiport": plan.get("destination_vertiport"),
                "destination_name": vertiport_by_id.get(str(plan.get("destination_vertiport")), {}).get("name"),
                "waypoints": plan.get("waypoints", []),
                "planned_departure_time": plan.get("planned_departure_time"),
                "planned_arrival_time": plan.get("planned_arrival_time"),
                "eta": plan.get("planned_arrival_time"),
                "delay_sec": delay_sec,
                "planned_altitude": plan.get("planned_altitude"),
                "planned_speed": plan.get("planned_speed"),
                "status": plan.get("status"),
                "track": track,
                "is_active": bool(track) and str(track.get("flight_status", "")).upper() == "ACTIVE",
                "conflict_count": len(related_conflicts),
                "severity": severity,
                "related_conflicts": [item.get("conflict_id") for item in related_conflicts],
            }
        )

    for track in tracks:
        aircraft_id = str(track.get("aircraft_id") or track.get("aircraftId") or "")
        if not aircraft_id or aircraft_id in planned_aircraft:
            continue
        related_conflicts = conflict_by_aircraft.get(aircraft_id, [])
        severities = [str(item.get("severity") or "NORMAL").upper() for item in related_conflicts]
        severity = "WARNING" if "WARNING" in severities else "CAUTION" if "CAUTION" in severities else "NORMAL"
        flights.append(
            {
                "flight_plan_id": track.get("flight_plan_id") or f"LIVE-4001-{aircraft_id}",
                "aircraft_id": aircraft_id,
                "operator_id": track.get("operator_id") or "DTAM",
                "route_id": track.get("route_id") or "",
                "current_corridor_id": track.get("current_corridor_id") or "",
                "current_corridor_name": track.get("current_corridor_name") or "ICD 4001 live track",
                "origin_vertiport": track.get("origin_vertiport") or "",
                "origin_name": None,
                "destination_vertiport": track.get("destination_vertiport") or "",
                "destination_name": None,
                "waypoints": [],
                "planned_departure_time": None,
                "planned_arrival_time": None,
                "eta": track.get("timestamp") or track.get("received_at"),
                "delay_sec": 0,
                "planned_altitude": track.get("altitude"),
                "planned_speed": track.get("ground_speed"),
                "status": track.get("flight_status") or track.get("status") or "ACTIVE",
                "track": track,
                "is_active": str(track.get("flight_status") or track.get("status") or "").upper() in {"ACTIVE", "CONNECTED"},
                "conflict_count": len(related_conflicts),
                "severity": severity,
                "related_conflicts": [item.get("conflict_id") for item in related_conflicts],
                "source": track.get("source") or "ICD-4001",
            }
        )

    conflict_details = []
    for conflict in conflicts:
        location_id = str(conflict.get("location_id") or "")
        location = waypoint_by_id.get(location_id) or corridor_by_id.get(location_id) or {}
        eta_gap = float(conflict.get("eta_gap_sec") or 0)
        required_gap = float(conflict.get("required_gap_sec") or 0)
        if required_gap > 0:
            separation_margin_sec = eta_gap - required_gap
        else:
            separation_margin_sec = 0
        conflict_details.append(
            {
                **conflict,
                "location": location,
                "location_name": location.get("name") or location.get("corridor_id") or location_id,
                "separation_margin_sec": separation_margin_sec,
                "time_to_event_label": _time_label(scenario.get("current_time"), conflict.get("predicted_time")),
            }
        )

    timeline = sorted(
        conflict_details,
        key=lambda item: (
            str(item.get("predicted_time") or ""),
            0 if str(item.get("severity")).upper() == "WARNING" else 1,
        ),
    )

    return {
        "scenario": scenario_metadata(scenario),
        "flights": flights,
        "tracks": tracks,
        "conflicts": conflict_details,
        "timeline": timeline,
        "summary": {
            "flight_count": len(flights),
            "active_track_count": len(tracks),
            "active_flight_count": sum(1 for item in flights if item.get("is_active")),
            "conflict_count": len(conflicts),
            "warning_count": sum(1 for item in conflicts if str(item.get("severity")).upper() == "WARNING"),
            "caution_count": sum(1 for item in conflicts if str(item.get("severity")).upper() == "CAUTION"),
            "tracked_conflict_aircraft": sorted(conflict_by_aircraft.keys()),
        },
        "generated_at": scenario.get("current_time"),
    }


def _time_label(current_time: Any, predicted_time: Any) -> str:
    # Static scenario helper: keep the label deterministic and UI-friendly.
    if not current_time or not predicted_time:
        return "--"
    try:
        from datetime import datetime

        current = datetime.fromisoformat(str(current_time))
        predicted = datetime.fromisoformat(str(predicted_time))
        delta_sec = int((predicted - current).total_seconds())
        sign = "" if delta_sec >= 0 else "-"
        delta_sec = abs(delta_sec)
        return f"{sign}{delta_sec // 60:02d}:{delta_sec % 60:02d}"
    except Exception:
        return "--"


def _delay_sec_from_events(events: list[dict[str, Any]], aircraft_id: str, flight_plan_id: str) -> int:
    """Extract a deterministic demo delay value from ETA deviation event titles."""
    for event in events:
        targets = {str(item) for item in event.get("related_targets") or []}
        if aircraft_id not in targets and flight_plan_id not in targets:
            continue
        title = str(event.get("title") or "")
        marker = "+" if "+" in title else "-" if "-" in title else ""
        if not marker:
            continue
        try:
            after_marker = title.split(marker, 1)[1]
            mmss = after_marker.split()[0]
            minutes_text, seconds_text = mmss.split(":", 1)
            value = int(minutes_text) * 60 + int(seconds_text)
            return value if marker == "+" else -value
        except Exception:
            continue
    return 0


def _status_weight(status: Any) -> int:
    return {"WARNING": 3, "CAUTION": 2, "NORMAL": 1}.get(str(status or "").upper(), 0)


def _resource_occupancy(available: Any, total: Any) -> float:
    total_value = float(total or 0)
    if total_value <= 0:
        return 0
    return round(max(0, min(1, 1 - float(available or 0) / total_value)), 3)


def _window_label(start: Any, end: Any) -> str:
    if not start and not end:
        return "--"
    return f"{_time_hhmm(start)}-{_time_hhmm(end)}"


def _time_hhmm(value: Any) -> str:
    if not value:
        return "--"
    text = str(value)
    if "T" in text:
        return text.split("T", 1)[1][:5]
    return text[:5]


def _duration_min(start: Any, end: Any, default: int = 10) -> int:
    if not start or not end:
        return default
    try:
        from datetime import datetime

        start_dt = datetime.fromisoformat(str(start))
        end_dt = datetime.fromisoformat(str(end))
        return max(1, round((end_dt - start_dt).total_seconds() / 60))
    except Exception:
        return default


def _diagnose_corridor(corridor: dict[str, Any], metric: dict[str, Any]) -> str:
    utilization = max(float(corridor.get("density_ratio") or 0), float(metric.get("utilization") or 0))
    if utilization >= 1:
        return "Corridor demand exceeds declared capacity"
    if utilization >= 0.8:
        return "Corridor density approaching caution threshold"
    return "Corridor flow is within nominal range"


def _diagnose_vertiport(vertiport: dict[str, Any], metric: dict[str, Any]) -> str:
    fato_occupancy = _resource_occupancy(vertiport.get("fato_available"), vertiport.get("fato_total"))
    gate_occupancy = _resource_occupancy(vertiport.get("gate_available"), vertiport.get("gate_total"))
    charging_occupancy = _resource_occupancy(vertiport.get("charging_spot_available"), vertiport.get("charging_spot_total"))
    utilization = float(metric.get("utilization") or 0)
    if int(vertiport.get("fato_available") or 0) <= 0 or fato_occupancy >= 0.9:
        return "FATO saturation"
    if utilization >= 1:
        return "Demand exceeds declared vertiport capacity"
    if gate_occupancy >= 0.8:
        return "Gate occupancy bottleneck"
    if charging_occupancy >= 0.75:
        return "Charging resource pressure"
    if int(vertiport.get("arrival_queue") or 0) >= 3:
        return "Arrival queue growth"
    return "Vertiport resources are within nominal range"


def _bottleneck_diagnosis(main_bottleneck: dict[str, Any] | None, events: list[dict[str, Any]]) -> dict[str, Any]:
    if not main_bottleneck:
        return {
            "target_id": None,
            "target_type": None,
            "status": "UNKNOWN",
            "cause": "No bottleneck candidate",
            "expected_duration_min": 0,
            "impact": "No capacity impact detected",
            "root_causes": [],
            "mitigations": [],
        }

    target_id = str(main_bottleneck.get("target_id"))
    target_type = str(main_bottleneck.get("target_type"))
    related_events = [
        event
        for event in events
        if target_id in {str(item) for item in event.get("related_targets") or []}
    ]
    if target_type == "VERTIPORT":
        cause = str(main_bottleneck.get("bottleneck_cause") or "Vertiport resource bottleneck")
        root_causes = [
            f"FATO occupancy {float(main_bottleneck.get('fato_occupancy') or 0) * 100:.0f}%",
            f"Gate occupancy {float(main_bottleneck.get('gate_occupancy') or 0) * 100:.0f}%",
            f"Average delay {_format_mmss(main_bottleneck.get('average_delay_sec'))}",
        ]
        mitigations = [
            "Hold inbound departures for 120 sec",
            "Move non-critical arrivals to alternate vertiport",
            "Prioritize turnaround resources for delayed aircraft",
        ]
    else:
        cause = str(main_bottleneck.get("diagnosis") or "Corridor density bottleneck")
        root_causes = [
            f"Density ratio {float(main_bottleneck.get('density_ratio') or 0) * 100:.0f}%",
            f"Occupied {main_bottleneck.get('occupied_aircraft')} / Capacity {main_bottleneck.get('capacity')}",
            f"Route group {', '.join(main_bottleneck.get('route_ids') or [])}",
        ]
        mitigations = [
            "Meter new entries into the corridor",
            "Assign alternate route for pending review flights",
            "Apply temporary speed harmonization",
        ]

    first_event = related_events[0] if related_events else {}
    return {
        "target_id": target_id,
        "target_type": target_type,
        "status": main_bottleneck.get("status"),
        "cause": cause,
        "expected_duration_min": _duration_min(first_event.get("created_time"), first_event.get("expected_time"), default=15),
        "impact": f"Demand {main_bottleneck.get('demand')} / Capacity {main_bottleneck.get('capacity')} · affected {len(main_bottleneck.get('affected_aircraft') or [])} UAM",
        "root_causes": root_causes,
        "mitigations": mitigations,
        "related_events": [event.get("event_id") for event in related_events],
        "affected_aircraft": main_bottleneck.get("affected_aircraft") or [],
    }


def _delay_propagation_events(
    scenario: dict[str, Any],
    events: list[dict[str, Any]],
    vertiports: list[dict[str, Any]],
    corridors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    propagation: list[dict[str, Any]] = []
    event_by_id = {str(item.get("event_id")): item for item in events}
    vp03 = next((item for item in vertiports if item.get("target_id") == "VP-03"), None)
    c2 = next((item for item in corridors if item.get("target_id") == "C2"), None)
    eta_event = next((item for item in events if str(item.get("event_type")) == "ETA_DEVIATION"), None)

    if vp03:
        event = event_by_id.get("EV-20260514-002", {})
        propagation.append(
            {
                "step": 1,
                "time": _time_hhmm(event.get("expected_time") or scenario.get("current_time")),
                "target_id": "VP-03",
                "target_type": "VERTIPORT",
                "status": vp03.get("status"),
                "title": "VP-03 FATO saturation increases arrival delay",
                "delay_sec": int(vp03.get("average_delay_sec") or 0),
                "affected_aircraft": vp03.get("affected_aircraft") or [],
                "description": "FATO availability is zero, so arrival and departure queues are expected to grow.",
            }
        )
    if c2:
        event = event_by_id.get("EV-20260514-003", {})
        propagation.append(
            {
                "step": 2,
                "time": _time_hhmm(event.get("expected_time") or scenario.get("current_time")),
                "target_id": "C2",
                "target_type": "CORRIDOR",
                "status": c2.get("status"),
                "title": "C2 metering causes short holding delay",
                "delay_sec": 120,
                "affected_aircraft": c2.get("affected_aircraft") or [],
                "description": "Corridor density is above capacity and new entries should be metered.",
            }
        )
    if eta_event:
        delay_sec = _delay_sec_from_events(events, "UAM-014", "FP-20260514-003")
        propagation.append(
            {
                "step": 3,
                "time": _time_hhmm(eta_event.get("expected_time")),
                "target_id": "UAM-014",
                "target_type": "AIRCRAFT",
                "status": eta_event.get("severity"),
                "title": "UAM-014 ETA deviation propagates to VP-02 arrival queue",
                "delay_sec": delay_sec,
                "affected_aircraft": ["UAM-014"],
                "description": "The delayed aircraft arrives into a caution-state vertiport and can increase queue pressure.",
            }
        )
    return propagation


def decision_support_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    """Build the final integrated Decision Support view model.

    The checklist asks for candidate generation and before/after comparison,
    not an automated optimizer. This payload therefore keeps every mitigation as
    an operator-confirmable candidate with deterministic static-demo metrics.
    """
    traffic = traffic_conflict_payload(scenario)
    flow = flow_capacity_payload(scenario)
    baseline = _decision_baseline_metrics(scenario, traffic, flow)
    recommendations = _decision_recommendations(scenario, traffic, flow, baseline)
    comparison = _decision_comparison_scenarios(baseline, recommendations)
    operation = _operation_handoff_payload(scenario, recommendations, comparison)
    report = _decision_report(scenario, baseline, recommendations, comparison, operation)

    return {
        "scenario": scenario_metadata(scenario),
        "analysis_mode": {
            "phase": "8/8 final replay report integration",
            "layer": "decision-support",
            "automation_level": "candidate-generation",
            "operator_authority": "manual-confirmation-required",
            "optimization_engine": "static-rulebook-demo",
            "generated_at": scenario.get("current_time"),
        },
        "baseline": baseline,
        "recommendations": recommendations,
        "comparison": comparison,
        "operation_handoff": operation,
        "report": report,
        "generated_at": scenario.get("current_time"),
    }


def replay_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    """Build the final-phase replay timeline for the demo scenario."""
    overview = overview_payload(scenario)
    traffic = traffic_conflict_payload(scenario)
    flow = flow_capacity_payload(scenario)
    decision = decision_support_payload(scenario)
    frames = _replay_frames(scenario, overview, traffic, flow, decision)
    return {
        "scenario": scenario_metadata(scenario),
        "playback": {
            "mode": "static-demo-replay",
            "start_time": frames[0].get("timestamp") if frames else scenario.get("current_time"),
            "end_time": frames[-1].get("timestamp") if frames else scenario.get("current_time"),
            "frame_count": len(frames),
            "default_interval_ms": 1600,
            "speed_options": [
                {"label": "0.5x", "interval_ms": 2400},
                {"label": "1x", "interval_ms": 1600},
                {"label": "2x", "interval_ms": 800},
            ],
            "operator_controls": ["play", "pause", "reset", "step-forward", "step-back"],
        },
        "summary": {
            "initial_active_flights": overview.get("traffic_summary", {}).get("peak_active_flights"),
            "conflict_events": len(traffic.get("conflicts", [])),
            "capacity_events": len(flow.get("capacity_events", [])),
            "decision_candidates": len(decision.get("recommendations", [])),
            "recommended_scenario": next(
                (item.get("scenario_id") for item in decision.get("comparison", []) if item.get("recommended")),
                None,
            ),
            "report_id": decision.get("report", {}).get("report_id"),
        },
        "frames": frames,
        "generated_at": scenario.get("current_time"),
    }


def final_validation_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    """Return a final integration checklist aligned with the master checklist."""
    decision = decision_support_payload(scenario)
    replay = replay_payload(scenario)
    map_payload = map_layers(scenario)
    checks = [
        {
            "section": "Core Screens",
            "items": [
                _validation_item("Overview KPI", True, "8종 KPI와 이벤트/버티포트 요약 연결"),
                _validation_item("Traffic Map / Conflict", bool(map_payload.get("tracks", {}).get("features")), "지도, 운항 목록, 충돌 타임라인 연결"),
                _validation_item("Flow & Capacity", True, "D/C Chart, 회랑/버티포트 병목, 지연 전파 연결"),
                _validation_item("Decision Support", len(decision.get("recommendations", [])) >= 6, "체크리스트 조치 후보 유형 생성"),
                _validation_item("Replay / Report", len(replay.get("frames", [])) >= 6, "시나리오 재생 프레임과 리포트 출력 준비"),
            ],
        },
        {
            "section": "Analysis Outputs",
            "items": [
                _validation_item("Conflict Candidates", len(decision.get("recommendations", [])) > 0, "충돌 이벤트별 조치 후보 생성"),
                _validation_item("Before / After Metrics", _recommendations_have_comparison(decision), "지연, 충돌 건수, 수용량 초과 시간 비교"),
                _validation_item("Mitigation Scenario", any(item.get("recommended") for item in decision.get("comparison", [])), "복합 완화안 추천 시나리오 포함"),
                _validation_item("Operation Preview", decision.get("operation_handoff", {}).get("handoff_status") in {"READY", "MODULE_MISSING"}, "자동 실행 없는 preview 패키지 생성"),
            ],
        },
        {
            "section": "Final Deliverables",
            "items": [
                _validation_item("Scenario Dataset", scenario_metadata(scenario).get("counts", {}).get("flight_plans", 0) > 0, "더미 시나리오 데이터셋 탑재"),
                _validation_item("API Surface", True, "Overview/Traffic/Capacity/Decision/Replay/Report API 제공"),
                _validation_item("Report Export", True, "JSON/Markdown/HTML 리포트 출력 엔드포인트 제공"),
                _validation_item("MissionModule Map Assets", True, "MissionModule MBTiles/vendor 참조 구조 유지"),
            ],
        },
    ]
    flat_items = [item for section in checks for item in section.get("items", [])]
    passed = sum(1 for item in flat_items if item.get("status") == "PASS")
    warnings = sum(1 for item in flat_items if item.get("status") == "WARN")
    return {
        "scenario": scenario_metadata(scenario),
        "phase": "8/8 final replay report integration",
        "completion": {
            "passed": passed,
            "warnings": warnings,
            "total": len(flat_items),
            "percentage": round((passed / len(flat_items)) * 100) if flat_items else 0,
        },
        "checks": checks,
        "known_limits": [
            "연구용 static demo 데이터 기반이며 실제 운항 승인/자동 재계획 실행은 하지 않습니다.",
            "OperationModule 연동은 dry-run preview payload 생성까지로 제한합니다.",
            "리플레이는 저장된 시나리오 이벤트를 순차 설명하는 시연용 timeline입니다.",
        ],
        "generated_at": scenario.get("current_time"),
    }


def scenario_result_report_payload(scenario: dict[str, Any]) -> dict[str, Any]:
    """Return JSON, Markdown, and HTML report outputs for the final phase."""
    decision = decision_support_payload(scenario)
    replay = replay_payload(scenario)
    validation = final_validation_payload(scenario)
    base_report = decision.get("report", {})
    markdown = _scenario_result_markdown(scenario, decision, replay, validation)
    html = _markdown_to_report_html(base_report.get("title") or "PSU Scenario Result Report", markdown)
    return {
        **base_report,
        "format": "json-markdown-html",
        "exports": {
            "json": "/api/reports/scenario-result",
            "markdown": "/api/reports/scenario-result.md",
            "html": "/api/reports/scenario-result.html",
        },
        "replay_summary": replay.get("summary"),
        "validation_summary": validation.get("completion"),
        "markdown": markdown,
        "html": html,
    }


def _decision_baseline_metrics(
    scenario: dict[str, Any],
    traffic: dict[str, Any],
    flow: dict[str, Any],
) -> dict[str, Any]:
    vertiports = _items(scenario, "vertiports")
    metrics = _items(scenario, "capacity_metrics")
    delays = [int(item.get("average_delay_sec") or 0) for item in vertiports]
    overload_minutes = sum(
        _duration_min(item.get("time_window_start"), item.get("time_window_end"), default=10)
        for item in metrics
        if int(item.get("demand") or 0) > int(item.get("capacity") or 0)
    )

    traffic_summary = traffic.get("summary", {})
    flow_summary = flow.get("summary", {})
    return {
        "scenario_id": scenario.get("scenario_id"),
        "conflict_count": int(traffic_summary.get("conflict_count") or 0),
        "warning_conflict_count": int(traffic_summary.get("warning_count") or 0),
        "caution_conflict_count": int(traffic_summary.get("caution_count") or 0),
        "capacity_warning_count": int(flow_summary.get("warning_count") or 0),
        "capacity_caution_count": int(flow_summary.get("caution_count") or 0),
        "average_delay_sec": round(sum(delays) / len(delays)) if delays else 0,
        "max_delay_sec": max(delays, default=0),
        "network_utilization": float(flow_summary.get("network_utilization") or 0),
        "max_utilization": float(flow_summary.get("max_utilization") or 0),
        "over_capacity_minutes": overload_minutes,
        "main_bottleneck_id": flow_summary.get("main_bottleneck_id"),
        "main_bottleneck_type": flow_summary.get("main_bottleneck_type"),
    }


def _decision_recommendations(
    scenario: dict[str, Any],
    traffic: dict[str, Any],
    flow: dict[str, Any],
    baseline: dict[str, Any],
) -> list[dict[str, Any]]:
    conflicts = {str(item.get("conflict_id")): item for item in traffic.get("conflicts", [])}
    events = {str(item.get("event_id")): item for item in _items(scenario, "event_logs")}
    capacity_targets = {
        str(item.get("target_id")): item
        for item in [*(flow.get("corridor_density") or []), *(flow.get("vertiport_throughput") or [])]
    }
    conflict_001 = conflicts.get("CF-20260514-001", {})
    conflict_002 = conflicts.get("CF-20260514-002", {})
    c2 = capacity_targets.get("C2", {})
    vp03 = capacity_targets.get("VP-03", {})

    candidates = [
        {
            "recommendation_id": "DS-20260514-001",
            "category": "DEPARTURE_DELAY",
            "title": "UAM-034 출발 90초 지연",
            "target_type": "AIRCRAFT",
            "target_id": "UAM-034",
            "related_conflict_id": "CF-20260514-001",
            "related_event_id": "EV-20260514-001",
            "affected_aircraft": ["UAM-034", "UAM-021"],
            "severity": conflict_001.get("severity", "WARNING"),
            "rationale": "WP-07 예상 도착 간격이 필요 분리 기준보다 짧아, 후행 기체의 출발 슬롯을 뒤로 밀어 시간 분리를 확보합니다.",
            "action_steps": [
                "UAM-034 출발 허가 예정 시각을 +90초로 조정",
                "UAM-021 기존 속도/경로 유지",
                "WP-07 ETA 재계산 후 분리 여유 30초 이상이면 운영자 확인",
            ],
            "delta": {
                "conflict_count": -1,
                "warning_conflict_count": -1,
                "average_delay_sec": 15,
                "over_capacity_minutes": -2,
            },
            "operation_intent": {
                "intent_type": "DELAY_DEPARTURE",
                "aircraft_id": "UAM-034",
                "delay_sec": 90,
                "confirmation_required": True,
            },
        },
        {
            "recommendation_id": "DS-20260514-002",
            "category": "SPEED_ADJUSTMENT",
            "title": "UAM-021 속도 8kt 감속",
            "target_type": "AIRCRAFT",
            "target_id": "UAM-021",
            "related_conflict_id": "CF-20260514-001",
            "related_event_id": "EV-20260514-001",
            "affected_aircraft": ["UAM-021", "UAM-034"],
            "severity": conflict_001.get("severity", "WARNING"),
            "rationale": "선행 기체의 지상속도를 임시로 낮춰 WP-07 통과 시점의 시간 간격을 벌립니다.",
            "action_steps": [
                "UAM-021 계획 속도 80kt를 72kt로 임시 조정",
                "감속 구간은 WP-03~WP-07로 제한",
                "분리 확보 후 원 속도 복귀 시각을 OperationModule에 전달",
            ],
            "delta": {
                "conflict_count": -1,
                "warning_conflict_count": -1,
                "average_delay_sec": 8,
                "max_delay_sec": 0,
            },
            "operation_intent": {
                "intent_type": "ADJUST_SPEED",
                "aircraft_id": "UAM-021",
                "speed_delta_kt": -8,
                "segment": "WP-03/WP-07",
                "confirmation_required": True,
            },
        },
        {
            "recommendation_id": "DS-20260514-003",
            "category": "ALTITUDE_SEPARATION",
            "title": "WP-07 통과 구간 고도 분리",
            "target_type": "WAYPOINT",
            "target_id": "WP-07",
            "related_conflict_id": "CF-20260514-001",
            "related_event_id": "EV-20260514-001",
            "affected_aircraft": ["UAM-021", "UAM-034"],
            "severity": conflict_001.get("severity", "WARNING"),
            "rationale": "시간 분리 조치가 슬롯에 부담을 줄 경우, 동일 웨이포인트 통과 구간에서 임시 고도층을 분리합니다.",
            "action_steps": [
                "UAM-021은 기존 450m 유지",
                "UAM-034는 WP-03~WP-07 구간 480m 임시 배정",
                "WP-07 통과 후 목적지 접근 고도 체계로 복귀",
            ],
            "delta": {
                "conflict_count": -1,
                "warning_conflict_count": -1,
                "average_delay_sec": 0,
                "max_delay_sec": 0,
            },
            "operation_intent": {
                "intent_type": "ASSIGN_ALTITUDE_LAYER",
                "aircraft_id": "UAM-034",
                "altitude_m": 480,
                "segment": "WP-03/WP-07",
                "confirmation_required": True,
            },
        },
        {
            "recommendation_id": "DS-20260514-004",
            "category": "ROUTE_ADJUSTMENT",
            "title": "UAM-034 대체 경로 R-2B 후보",
            "target_type": "AIRCRAFT",
            "target_id": "UAM-034",
            "related_conflict_id": "CF-20260514-001",
            "related_event_id": "EV-20260514-001",
            "affected_aircraft": ["UAM-034"],
            "severity": "CAUTION",
            "rationale": "WP-07 중첩을 회피하고 C2 밀도 부담을 낮추기 위해 R-03 대신 R-2B 우회 경로를 후보로 제시합니다.",
            "action_steps": [
                "UAM-034 항로를 R-03에서 R-2B 후보로 재계산",
                "우회 경로의 C2 진입 여부와 VP-04 도착 슬롯 영향 확인",
                "운영자 승인 시 OperationModule 운항 재계획 패키지로 전달",
            ],
            "delta": {
                "conflict_count": -1,
                "warning_conflict_count": -1,
                "capacity_warning_count": -1,
                "network_utilization": -0.07,
                "average_delay_sec": -8,
                "over_capacity_minutes": -5,
            },
            "operation_intent": {
                "intent_type": "REROUTE",
                "aircraft_id": "UAM-034",
                "from_route_id": "R-03",
                "to_route_id": "R-2B",
                "confirmation_required": True,
            },
        },
        {
            "recommendation_id": "DS-20260514-005",
            "category": "CORRIDOR_METERING",
            "title": "C2 신규 진입 120초 홀딩",
            "target_type": "CORRIDOR",
            "target_id": "C2",
            "related_conflict_id": "CF-20260514-002",
            "related_event_id": "EV-20260514-003",
            "affected_aircraft": c2.get("affected_aircraft") or conflict_002.get("related_aircraft") or [],
            "severity": conflict_002.get("severity", "CAUTION"),
            "rationale": "C2 회랑의 수요가 수용량을 초과하므로 신규 진입을 계량해 밀도 초과 시간을 줄입니다.",
            "action_steps": [
                "C2 진입 예정 항공기 중 PENDING_REVIEW 항목을 120초 홀딩",
                "ACTIVE 항공기는 현 경로 유지, 간격만 재계산",
                "10분 분석 창에서 수용량 초과 잔여 시간을 재평가",
            ],
            "delta": {
                "caution_conflict_count": -1,
                "capacity_warning_count": -1,
                "network_utilization": -0.05,
                "average_delay_sec": 22,
                "over_capacity_minutes": -6,
            },
            "operation_intent": {
                "intent_type": "METER_CORRIDOR_ENTRY",
                "corridor_id": "C2",
                "hold_sec": 120,
                "confirmation_required": True,
            },
        },
        {
            "recommendation_id": "DS-20260514-006",
            "category": "ARRIVAL_SEQUENCING",
            "title": "VP-03 도착 순서 재조정",
            "target_type": "VERTIPORT",
            "target_id": "VP-03",
            "related_conflict_id": None,
            "related_event_id": "EV-20260514-002",
            "affected_aircraft": vp03.get("affected_aircraft") or ["UAM-019", "UAM-027"],
            "severity": vp03.get("status", "WARNING"),
            "rationale": "VP-03 FATO 가용이 0이므로 지연이 큰 도착편과 회전 자원을 우선 배정해 지연 전파를 줄입니다.",
            "action_steps": [
                "UAM-019 접근 순서를 우선 배정",
                "UAM-027은 VP-03 접근 전 홀딩 또는 대체 버티포트 후보와 비교",
                "FATO 회전 시간 회복 후 다음 도착 슬롯을 재계산",
            ],
            "delta": {
                "capacity_warning_count": -1,
                "average_delay_sec": -35,
                "max_delay_sec": -115,
                "over_capacity_minutes": -8,
            },
            "operation_intent": {
                "intent_type": "RESEQUENCE_ARRIVALS",
                "vertiport_id": "VP-03",
                "priority_aircraft": ["UAM-019"],
                "confirmation_required": True,
            },
        },
        {
            "recommendation_id": "DS-20260514-007",
            "category": "VERTIPORT_REBALANCE",
            "title": "UAM-027 대체 버티포트 VP-04 유도",
            "target_type": "VERTIPORT",
            "target_id": "VP-04",
            "related_conflict_id": None,
            "related_event_id": "EV-20260514-002",
            "affected_aircraft": ["UAM-027"],
            "severity": "CAUTION",
            "rationale": "VP-03의 FATO 포화와 도착 큐를 낮추기 위해 VP-04를 대체 착륙 후보로 제시합니다.",
            "action_steps": [
                "UAM-027 목적지를 VP-03에서 VP-04 후보로 전환해 ETA 재산출",
                "VP-04 게이트/충전 자원 여유 확인",
                "승객/운항사 승인 필요 여부를 리포트에 표시",
            ],
            "delta": {
                "capacity_warning_count": -1,
                "network_utilization": -0.1,
                "average_delay_sec": -45,
                "max_delay_sec": -150,
                "over_capacity_minutes": -10,
            },
            "operation_intent": {
                "intent_type": "DIVERT_TO_ALTERNATE_VERTIPORT",
                "aircraft_id": "UAM-027",
                "from_vertiport_id": "VP-03",
                "to_vertiport_id": "VP-04",
                "confirmation_required": True,
            },
        },
    ]

    recommendations = [
        _build_decision_recommendation(candidate, baseline, events)
        for candidate in candidates
    ]
    return sorted(
        recommendations,
        key=lambda item: (
            _status_weight(item.get("severity")),
            int(item.get("expected_effect", {}).get("priority_score") or 0),
            item.get("recommendation_id") or "",
        ),
        reverse=True,
    )


def _build_decision_recommendation(
    candidate: dict[str, Any],
    baseline: dict[str, Any],
    events: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    delta = candidate.pop("delta")
    after = _decision_after_metrics(baseline, delta)
    event = events.get(str(candidate.get("related_event_id")), {})
    before = {
        key: baseline.get(key)
        for key in (
            "conflict_count",
            "capacity_warning_count",
            "average_delay_sec",
            "max_delay_sec",
            "network_utilization",
            "over_capacity_minutes",
        )
    }
    return {
        **candidate,
        "status": "CANDIDATE",
        "expected_time": event.get("expected_time"),
        "time_to_event_label": _time_label(event.get("created_time"), event.get("expected_time")),
        "before": before,
        "after": after,
        "expected_effect": _decision_expected_effect(before, after, event),
        "risk_notes": _decision_risk_notes(candidate.get("category")),
    }


def _decision_after_metrics(baseline: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    after = {
        "conflict_count": int(baseline.get("conflict_count") or 0),
        "warning_conflict_count": int(baseline.get("warning_conflict_count") or 0),
        "caution_conflict_count": int(baseline.get("caution_conflict_count") or 0),
        "capacity_warning_count": int(baseline.get("capacity_warning_count") or 0),
        "capacity_caution_count": int(baseline.get("capacity_caution_count") or 0),
        "average_delay_sec": int(baseline.get("average_delay_sec") or 0),
        "max_delay_sec": int(baseline.get("max_delay_sec") or 0),
        "network_utilization": float(baseline.get("network_utilization") or 0),
        "over_capacity_minutes": int(baseline.get("over_capacity_minutes") or 0),
    }
    for key, value in delta.items():
        if key not in after:
            continue
        if key == "network_utilization":
            after[key] = round(max(0.0, float(after[key]) + float(value or 0)), 3)
        else:
            after[key] = max(0, int(round(float(after[key]) + float(value or 0))))
    if after["warning_conflict_count"] == 0 and after["conflict_count"] < after["caution_conflict_count"]:
        after["caution_conflict_count"] = after["conflict_count"]
    if after["capacity_warning_count"] == 0 and after["capacity_caution_count"] > 0:
        after["capacity_caution_count"] = min(after["capacity_caution_count"], 1)
    return after


def _decision_expected_effect(
    before: dict[str, Any],
    after: dict[str, Any],
    event: dict[str, Any],
) -> dict[str, Any]:
    conflict_reduction = int(before.get("conflict_count") or 0) - int(after.get("conflict_count") or 0)
    capacity_warning_reduction = int(before.get("capacity_warning_count") or 0) - int(after.get("capacity_warning_count") or 0)
    average_delay_delta = int(after.get("average_delay_sec") or 0) - int(before.get("average_delay_sec") or 0)
    max_delay_delta = int(after.get("max_delay_sec") or 0) - int(before.get("max_delay_sec") or 0)
    over_capacity_delta = int(after.get("over_capacity_minutes") or 0) - int(before.get("over_capacity_minutes") or 0)
    network_utilization_delta = round(float(after.get("network_utilization") or 0) - float(before.get("network_utilization") or 0), 3)

    summary_bits = []
    if conflict_reduction:
        summary_bits.append(f"충돌 {conflict_reduction}건 감소")
    if capacity_warning_reduction:
        summary_bits.append(f"수용량 Warning {capacity_warning_reduction}건 감소")
    if average_delay_delta:
        direction = "감소" if average_delay_delta < 0 else "증가"
        summary_bits.append(f"평균 지연 {_format_mmss(abs(average_delay_delta))} {direction}")
    if max_delay_delta:
        direction = "감소" if max_delay_delta < 0 else "증가"
        summary_bits.append(f"최대 지연 {_format_mmss(abs(max_delay_delta))} {direction}")
    if over_capacity_delta:
        direction = "감소" if over_capacity_delta < 0 else "증가"
        summary_bits.append(f"초과 시간 {abs(over_capacity_delta)}분 {direction}")

    return {
        "priority_score": int(event.get("priority_score") or 50),
        "conflict_reduction": conflict_reduction,
        "capacity_warning_reduction": capacity_warning_reduction,
        "average_delay_delta_sec": average_delay_delta,
        "max_delay_delta_sec": max_delay_delta,
        "network_utilization_delta": network_utilization_delta,
        "over_capacity_minutes_delta": over_capacity_delta,
        "summary": ", ".join(summary_bits) if summary_bits else "운영 리스크를 낮추는 보조 후보",
    }


def _decision_risk_notes(category: Any) -> list[str]:
    notes = {
        "DEPARTURE_DELAY": [
            "후행 항공기 연결편 지연 여부 확인 필요",
            "지연 적용 전 운항사 승인 절차 필요",
        ],
        "SPEED_ADJUSTMENT": [
            "감속 구간 내 후속 항공기 간격 재확인 필요",
            "배터리/소음 제한 조건과 함께 검토 필요",
        ],
        "ALTITUDE_SEPARATION": [
            "임시 고도층은 주변 회랑 고도 체계와 충돌하지 않아야 함",
            "접근 단계에서 원래 고도 복귀 타이밍 검증 필요",
        ],
        "ROUTE_ADJUSTMENT": [
            "우회 경로의 추가 비행시간과 회랑 예약 상태 확인 필요",
            "목적지 도착 슬롯 재협의 가능성 있음",
        ],
        "CORRIDOR_METERING": [
            "계량 홀딩이 출발지 지상 혼잡으로 전파될 수 있음",
            "ACTIVE 항공기에는 강제 경로 변경을 적용하지 않음",
        ],
        "ARRIVAL_SEQUENCING": [
            "우선순위 변경은 버티포트 지상자원 상태와 동기화 필요",
            "응급/특수 임무 항공기는 별도 우선권 확인 필요",
        ],
        "VERTIPORT_REBALANCE": [
            "대체 버티포트 승객 이동 및 운항사 승인 필요",
            "VP-04 수용량이 추가 도착편을 받는지 재검증 필요",
        ],
    }
    return notes.get(str(category), ["운영자 확인 후 적용해야 하는 후보입니다."])


def _decision_comparison_scenarios(
    baseline: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    def by_id(recommendation_id: str) -> dict[str, Any] | None:
        return next(
            (item for item in recommendations if str(item.get("recommendation_id")) == recommendation_id),
            None,
        )

    scenarios = [
        {
            "scenario_id": "baseline",
            "label": "Baseline",
            "description": "조치 전 현재 PSU 모니터링 상태",
            "applied_recommendations": [],
            "metrics": {
                key: baseline.get(key)
                for key in (
                    "conflict_count",
                    "capacity_warning_count",
                    "average_delay_sec",
                    "max_delay_sec",
                    "network_utilization",
                    "over_capacity_minutes",
                )
            },
        },
    ]

    scenario_specs = [
        ("departure-delay", "출발 지연 후보", "UAM-034 출발 지연으로 WP-07 시간 분리 확보", ["DS-20260514-001"]),
        ("route-adjustment", "대체 경로 후보", "UAM-034 R-2B 우회로 충돌과 C2 부하를 동시 완화", ["DS-20260514-004"]),
        ("arrival-sequencing", "도착 순서 후보", "VP-03 도착 순서를 조정해 FATO 포화 지연을 완화", ["DS-20260514-006"]),
        ("vertiport-rebalance", "대체 버티포트 후보", "UAM-027을 VP-04로 유도해 VP-03 부하를 분산", ["DS-20260514-007"]),
    ]
    for scenario_id, label, description, ids in scenario_specs:
        rec = by_id(ids[0])
        if not rec:
            continue
        scenarios.append(
            {
                "scenario_id": scenario_id,
                "label": label,
                "description": description,
                "applied_recommendations": ids,
                "metrics": rec.get("after"),
                "effect": rec.get("expected_effect"),
            }
        )

    combined_delta = {
        "conflict_count": -2,
        "warning_conflict_count": -1,
        "caution_conflict_count": -1,
        "capacity_warning_count": -2,
        "capacity_caution_count": -1,
        "average_delay_sec": -64,
        "max_delay_sec": -180,
        "network_utilization": -0.22,
        "over_capacity_minutes": -24,
    }
    combined_after = _decision_after_metrics(baseline, combined_delta)
    before = scenarios[0]["metrics"]
    scenarios.append(
        {
            "scenario_id": "combined-mitigation",
            "label": "복합 완화안",
            "description": "출발 지연 + 대체 경로 + VP-03 순서/대체 버티포트를 묶은 운영자 승인용 패키지",
            "applied_recommendations": [
                "DS-20260514-001",
                "DS-20260514-004",
                "DS-20260514-006",
                "DS-20260514-007",
            ],
            "metrics": combined_after,
            "effect": _decision_expected_effect(before, combined_after, {"priority_score": 95}),
            "recommended": True,
        }
    )
    return scenarios


def _operation_handoff_payload(
    scenario: dict[str, Any],
    recommendations: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
) -> dict[str, Any]:
    package_id = f"PSU-DS-{str(scenario.get('scenario_id') or 'SCENARIO').replace(' ', '-')}-{_time_hhmm(scenario.get('current_time')).replace(':', '')}"
    recommended_scenario = next((item for item in comparison if item.get("recommended")), comparison[-1] if comparison else {})
    return {
        "target_module": "OperationModule",
        "module_root": str(OPERATION_MODULE_ROOT),
        "available": OPERATION_MODULE_ROOT.is_dir(),
        "handoff_status": "READY" if OPERATION_MODULE_ROOT.is_dir() else "MODULE_MISSING",
        "handoff_mode": "preview-only",
        "package_id": package_id,
        "recommended_scenario_id": recommended_scenario.get("scenario_id"),
        "requires_operator_confirmation": True,
        "notes": [
            "8회차 최종 범위에서는 OperationModule을 직접 실행하지 않고 전달 가능한 dry-run 명령 패키지를 제공합니다.",
            "리플레이와 리포트 출력 화면에서 preview payload와 제한사항을 함께 확인할 수 있습니다.",
        ],
        "command_package": {
            "package_id": package_id,
            "source_module": "PSU",
            "target_module": "OperationModule",
            "scenario_id": scenario.get("scenario_id"),
            "generated_at": scenario.get("current_time"),
            "candidate_count": len(recommendations),
            "actions": [
                {
                    "recommendation_id": item.get("recommendation_id"),
                    "category": item.get("category"),
                    "title": item.get("title"),
                    "target_type": item.get("target_type"),
                    "target_id": item.get("target_id"),
                    "operation_intent": item.get("operation_intent"),
                    "expected_effect": item.get("expected_effect"),
                }
                for item in recommendations
            ],
        },
    }


def _decision_report(
    scenario: dict[str, Any],
    baseline: dict[str, Any],
    recommendations: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    operation: dict[str, Any],
) -> dict[str, Any]:
    recommended = next((item for item in comparison if item.get("recommended")), comparison[-1] if comparison else {})
    recommended_metrics = recommended.get("metrics") or {}
    report_id = f"PSU-REPORT-{_time_hhmm(scenario.get('current_time')).replace(':', '')}"
    top_recommendations = recommendations[:3]
    summary = (
        f"기준 상태는 충돌 {baseline.get('conflict_count')}건, 수용량 Warning "
        f"{baseline.get('capacity_warning_count')}건, 평균 지연 {_format_mmss(baseline.get('average_delay_sec'))}입니다. "
        f"복합 완화안 적용 시 충돌 {recommended_metrics.get('conflict_count')}건, 수용량 Warning "
        f"{recommended_metrics.get('capacity_warning_count')}건, 평균 지연 "
        f"{_format_mmss(recommended_metrics.get('average_delay_sec'))}로 개선됩니다."
    )
    sections = [
        {
            "heading": "Baseline",
            "items": [
                f"주요 병목: {baseline.get('main_bottleneck_type')} {baseline.get('main_bottleneck_id')}",
                f"네트워크 수요/수용량 비율: {float(baseline.get('network_utilization') or 0) * 100:.0f}%",
                f"수용량 초과 시간: {baseline.get('over_capacity_minutes')}분",
            ],
        },
        {
            "heading": "Top Recommendations",
            "items": [
                f"{item.get('recommendation_id')} · {item.get('title')} · {item.get('expected_effect', {}).get('summary')}"
                for item in top_recommendations
            ],
        },
        {
            "heading": "Operation Handoff",
            "items": [
                f"패키지: {operation.get('package_id')}",
                f"상태: {operation.get('handoff_status')} / 방식: {operation.get('handoff_mode')}",
                "운영자 승인 전 자동 실행 없음",
            ],
        },
    ]
    markdown_lines = [f"# {report_id}", "", summary, ""]
    for section in sections:
        markdown_lines.append(f"## {section['heading']}")
        markdown_lines.extend(f"- {item}" for item in section.get("items", []))
        markdown_lines.append("")
    return {
        "report_id": report_id,
        "title": "PSU Decision Support Scenario Evaluation",
        "format": "markdown-preview",
        "summary": summary,
        "sections": sections,
        "markdown": "\n".join(markdown_lines).strip(),
        "generated_at": scenario.get("current_time"),
    }


def _replay_frames(
    scenario: dict[str, Any],
    overview: dict[str, Any],
    traffic: dict[str, Any],
    flow: dict[str, Any],
    decision: dict[str, Any],
) -> list[dict[str, Any]]:
    events = {str(item.get("event_id")): item for item in _items(scenario, "event_logs")}
    conflicts = {str(item.get("conflict_id")): item for item in traffic.get("conflicts", [])}
    comparison = decision.get("comparison", [])
    recommended = next((item for item in comparison if item.get("recommended")), comparison[-1] if comparison else {})
    recommended_metrics = recommended.get("metrics", {})
    trend_by_time = {
        str(item.get("time")): item
        for item in scenario.get("traffic_trend", [])
    }

    def trend_metrics(label: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
        point = trend_by_time.get(label, fallback or {})
        return {
            "active_flights": point.get("active_flights", overview.get("kpis", {}).get("active_uam")),
            "average_delay_sec": point.get("average_delay_sec", overview.get("kpis", {}).get("average_delay_sec")),
            "conflict_count": point.get("conflict_count", overview.get("kpis", {}).get("conflict_alert")),
            "capacity_warning_count": flow.get("summary", {}).get("warning_count"),
            "network_utilization": flow.get("summary", {}).get("network_utilization"),
        }

    frame_specs = [
        {
            "time": "14:30",
            "title": "Baseline monitoring snapshot",
            "screen": "Overview",
            "event_id": None,
            "description": "서울권 demo 시나리오의 기본 운항 상태와 KPI를 확인합니다.",
            "related_targets": ["OVERVIEW"],
            "metrics": trend_metrics("14:30"),
            "operator_focus": "전체 KPI와 우선 이벤트 큐 확인",
        },
        {
            "time": "14:38",
            "title": events.get("EV-20260514-001", {}).get("title", "WP-07 predicted conflict"),
            "screen": "Traffic Map / Conflict",
            "event_id": "EV-20260514-001",
            "conflict_id": "CF-20260514-001",
            "description": "WP-07에서 UAM-021/UAM-034 시간 분리 부족을 탐지하고 상세 충돌 패널을 확인합니다.",
            "related_targets": ["WP-07", "UAM-021", "UAM-034"],
            "metrics": trend_metrics("14:40"),
            "operator_focus": "충돌 위치, ETA gap, suggested action 검토",
        },
        {
            "time": "14:40",
            "title": events.get("EV-20260514-002", {}).get("title", "VP-03 FATO saturation"),
            "screen": "Flow & Capacity",
            "event_id": "EV-20260514-002",
            "description": "VP-03의 FATO 가용 0 상태와 도착 큐 증가가 네트워크 지연으로 전파되는지 확인합니다.",
            "related_targets": ["VP-03", "UAM-019", "UAM-027"],
            "metrics": {
                **trend_metrics("14:40"),
                "main_bottleneck": flow.get("summary", {}).get("main_bottleneck_id"),
                "max_utilization": flow.get("summary", {}).get("max_utilization"),
            },
            "operator_focus": "버티포트 처리량과 병목 원인 진단",
        },
        {
            "time": "14:41",
            "title": events.get("EV-20260514-003", {}).get("title", "C2 density exceeds threshold"),
            "screen": "Flow & Capacity",
            "event_id": "EV-20260514-003",
            "conflict_id": "CF-20260514-002",
            "description": "C2 회랑 수요가 수용량을 초과해 계량 진입/대체 경로 후보가 필요한 상태를 재생합니다.",
            "related_targets": ["C2", "UAM-014", "UAM-019", "UAM-021", "UAM-034"],
            "metrics": trend_metrics("14:40"),
            "operator_focus": "회랑 밀도와 수용량 초과 시간 확인",
        },
        {
            "time": "14:46",
            "title": events.get("EV-20260514-004", {}).get("title", "ETA deviation"),
            "screen": "Traffic Map / Conflict",
            "event_id": "EV-20260514-004",
            "description": "UAM-014 ETA 편차가 VP-02 도착 큐로 전파될 수 있는지 확인합니다.",
            "related_targets": ["UAM-014", "FP-20260514-003", "VP-02"],
            "metrics": trend_metrics("14:50"),
            "operator_focus": "지연 항공기와 목적지 버티포트 영향 확인",
        },
        {
            "time": "14:48",
            "title": "Decision support mitigation package",
            "screen": "Decision Support",
            "event_id": None,
            "description": "출발 지연, 대체 경로, 도착 순서, 대체 버티포트 후보를 묶어 전후 효과를 비교합니다.",
            "related_targets": recommended.get("applied_recommendations", []),
            "metrics": {
                "active_flights": trend_metrics("14:50").get("active_flights"),
                "average_delay_sec": recommended_metrics.get("average_delay_sec"),
                "conflict_count": recommended_metrics.get("conflict_count"),
                "capacity_warning_count": recommended_metrics.get("capacity_warning_count"),
                "over_capacity_minutes": recommended_metrics.get("over_capacity_minutes"),
                "network_utilization": recommended_metrics.get("network_utilization"),
            },
            "operator_focus": "OperationModule preview 전 운영자 승인 항목 확인",
        },
        {
            "time": "14:50",
            "title": "Scenario result report output",
            "screen": "Replay / Report",
            "event_id": None,
            "description": "리플레이 흐름과 시나리오 결과 리포트를 JSON/Markdown/HTML로 출력합니다.",
            "related_targets": [decision.get("report", {}).get("report_id")],
            "metrics": trend_metrics("15:00"),
            "operator_focus": "시연 종료, 리포트 export 및 제한사항 확인",
        },
    ]

    frames: list[dict[str, Any]] = []
    for idx, spec in enumerate(frame_specs, start=1):
        event = events.get(str(spec.get("event_id")), {})
        conflict = conflicts.get(str(spec.get("conflict_id")), {})
        frames.append(
            {
                "step": idx,
                "time_label": spec.get("time"),
                "timestamp": event.get("expected_time") or _timestamp_for_time(scenario.get("current_time"), spec.get("time")),
                "title": spec.get("title"),
                "screen": spec.get("screen"),
                "event_id": spec.get("event_id"),
                "conflict_id": spec.get("conflict_id"),
                "severity": event.get("severity") or conflict.get("severity") or "NORMAL",
                "description": spec.get("description"),
                "related_targets": [item for item in spec.get("related_targets", []) if item],
                "metrics": spec.get("metrics"),
                "operator_focus": spec.get("operator_focus"),
                "map_focus": _replay_map_focus(spec.get("related_targets", []), conflict),
                "recommended_tab": screen_to_tab_hint(spec.get("screen")),
            }
        )
    return frames


def _timestamp_for_time(current_time: Any, time_label: Any) -> str:
    current = str(current_time or "")
    label = str(time_label or "")
    if "T" in current and len(label) >= 5:
        return f"{current.split('T', 1)[0]}T{label[:5]}:00+09:00"
    return label


def _replay_map_focus(targets: list[Any], conflict: dict[str, Any]) -> dict[str, Any]:
    if conflict:
        return {
            "type": "conflict",
            "id": conflict.get("conflict_id"),
            "location_id": conflict.get("location_id"),
            "targets": conflict.get("related_aircraft") or [],
        }
    aircraft = [str(item) for item in targets if str(item).startswith("UAM-")]
    vertiports = [str(item) for item in targets if str(item).startswith("VP-")]
    corridors = [str(item) for item in targets if str(item).startswith("C")]
    if aircraft:
        return {"type": "aircraft", "id": aircraft[0], "targets": aircraft}
    if vertiports:
        return {"type": "vertiport", "id": vertiports[0], "targets": vertiports}
    if corridors:
        return {"type": "corridor", "id": corridors[0], "targets": corridors}
    return {"type": "overview", "id": None, "targets": [str(item) for item in targets]}


def screen_to_tab_hint(screen: Any) -> str:
    normalized = str(screen or "").lower()
    if "replay" in normalized or "report" in normalized:
        return "replay-report"
    if "decision" in normalized:
        return "decision-support"
    if "flow" in normalized or "capacity" in normalized:
        return "flow-capacity"
    if "traffic" in normalized or "conflict" in normalized:
        return "traffic-map"
    return "overview"


def _validation_item(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "PASS" if passed else "WARN",
        "detail": detail,
    }


def _recommendations_have_comparison(decision: dict[str, Any]) -> bool:
    for item in decision.get("recommendations", []):
        before = item.get("before") or {}
        after = item.get("after") or {}
        required = {"conflict_count", "average_delay_sec", "over_capacity_minutes"}
        if not required.issubset(before) or not required.issubset(after):
            return False
    return bool(decision.get("recommendations"))


def _scenario_result_markdown(
    scenario: dict[str, Any],
    decision: dict[str, Any],
    replay: dict[str, Any],
    validation: dict[str, Any],
) -> str:
    report = decision.get("report", {})
    baseline = decision.get("baseline", {})
    recommended = next((item for item in decision.get("comparison", []) if item.get("recommended")), {})
    recommended_metrics = recommended.get("metrics", {})
    lines = [
        f"# {report.get('title', 'PSU Scenario Result Report')}",
        "",
        f"- Report ID: {report.get('report_id')}",
        f"- Scenario: {scenario.get('scenario_id')} / {scenario.get('name')}",
        f"- Generated At: {scenario.get('current_time')}",
        f"- Replay Frames: {replay.get('playback', {}).get('frame_count')}",
        f"- Final Completion: {validation.get('completion', {}).get('percentage')}%",
        "",
        "## Executive Summary",
        report.get("summary", ""),
        "",
        "## Baseline vs Recommended",
        f"- Conflict Count: {baseline.get('conflict_count')} → {recommended_metrics.get('conflict_count')}",
        f"- Capacity Warning: {baseline.get('capacity_warning_count')} → {recommended_metrics.get('capacity_warning_count')}",
        f"- Average Delay: {_format_mmss(baseline.get('average_delay_sec'))} → {_format_mmss(recommended_metrics.get('average_delay_sec'))}",
        f"- Max Delay: {_format_mmss(baseline.get('max_delay_sec'))} → {_format_mmss(recommended_metrics.get('max_delay_sec'))}",
        f"- Over-Capacity Time: {baseline.get('over_capacity_minutes')}m → {recommended_metrics.get('over_capacity_minutes')}m",
        "",
        "## Replay Timeline",
    ]
    for frame in replay.get("frames", []):
        lines.append(
            f"- {frame.get('step')}. {frame.get('time_label')} / {frame.get('screen')} / "
            f"{frame.get('title')} ({frame.get('severity')})"
        )
    lines.extend(["", "## Decision Candidates"])
    for item in decision.get("recommendations", []):
        lines.append(
            f"- {item.get('recommendation_id')} [{item.get('category')}] "
            f"{item.get('title')} — {item.get('expected_effect', {}).get('summary')}"
        )
    lines.extend(["", "## Final Validation"])
    for section in validation.get("checks", []):
        lines.append(f"### {section.get('section')}")
        for item in section.get("items", []):
            lines.append(f"- [{item.get('status')}] {item.get('name')}: {item.get('detail')}")
    lines.extend(["", "## Known Limits"])
    for item in validation.get("known_limits", []):
        lines.append(f"- {item}")
    return "\n".join(lines).strip()


def _markdown_to_report_html(title: str, markdown: str) -> str:
    body_lines = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            body_lines.append(f"<h1>{_html_escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body_lines.append(f"<h2>{_html_escape(line[3:])}</h2>")
        elif line.startswith("### "):
            body_lines.append(f"<h3>{_html_escape(line[4:])}</h3>")
        elif line.startswith("- "):
            body_lines.append(f"<p class=\"bullet\">• {_html_escape(line[2:])}</p>")
        elif line:
            body_lines.append(f"<p>{_html_escape(line)}</p>")
        else:
            body_lines.append("")
    return (
        "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\" />"
        f"<title>{_html_escape(title)}</title>"
        "<style>body{font-family:Segoe UI,sans-serif;margin:32px;line-height:1.6;color:#111827}"
        "h1,h2,h3{color:#0f172a}.bullet{margin:.35rem 0;padding-left:.6rem}"
        "p{max-width:980px}</style></head><body>"
        + "\n".join(body_lines)
        + "</body></html>"
    )


def _html_escape(value: Any) -> str:
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _format_mmss(seconds: Any) -> str:
    value = abs(int(float(seconds or 0)))
    return f"{value // 60:02d}:{value % 60:02d}"
