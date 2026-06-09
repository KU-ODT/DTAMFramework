from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import csv
import heapq
import io
import math
import random
from threading import Lock
from typing import Any
from uuid import uuid4

from . import demand_service, layout_library, vertiport_config_store
from .flight_profile import build_mission_profile
from .route_planner import get_planner
from .vertiport_loader import load_vertiports
from vp_sim.simulation import (
    build_model as build_vp_model,
    clone_resources as clone_vp_resources,
    commit_resources as commit_vp_resources,
    schedule_departure as schedule_vp_departure,
    schedule_landing as schedule_vp_landing,
    segment_position as vp_segment_position,
    summarize_at as summarize_vp_at,
)
from vp_sim.validation import normalize_layout


AIRCRAFT_TYPES: dict[str, dict[str, object]] = {
    "a2": {"label": "2인승", "seats": 2, "color": "#94a3b8"},
    "a4": {"label": "4인승", "seats": 4, "color": "#38bdf8"},
    "a6": {"label": "6인승", "seats": 6, "color": "#34d399"},
    "a8": {"label": "8인승", "seats": 8, "color": "#f59e0b"},
}

BOARDING_BASE_S = 60.0
BOARDING_PER_PAX_S = 15.0
DEBOARDING_BASE_S = 45.0
DEBOARDING_PER_PAX_S = 10.0
MIN_TAKEOFF_SERVICE_S = 60.0
MIN_LANDING_SERVICE_S = 60.0
MAX_DESTINATION_ATTEMPTS = 8


@dataclass
class Aircraft:
    aircraft_id: str
    type_id: str
    type_label: str
    seats: int
    current_vertiport: str
    current_gate_id: str
    available_at: float
    state: str = "available"


@dataclass
class VertiportRuntime:
    vertiport_id: str
    code: str
    name: str
    layout: dict[str, Any] | None
    model: dict[str, Any] | None
    resources: dict[str, dict[str, float]]
    gate_ids: list[str]
    takeoff_fato_ids: list[str]
    landing_fato_ids: list[str]
    gate_available_at: dict[str, float]
    takeoff_fato_available_at: dict[str, float]
    landing_fato_available_at: dict[str, float]
    initial_fleet_by_type: dict[str, int] = field(default_factory=dict)
    overflow_gate_seq: int = 0
    overflow_warning_added: bool = False
    internal_aircraft: list[dict[str, Any]] = field(default_factory=list)
    departures: int = 0
    arrivals: int = 0
    served_passengers: int = 0
    requested_by_destination: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    served_by_destination: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    unserved_by_destination: dict[str, int] = field(default_factory=lambda: defaultdict(int))


@dataclass
class SimulationState:
    simulation_id: str
    summary: dict[str, object]
    flights: list[dict[str, object]]
    vertiports: dict[str, dict[str, object]]
    routes: dict[str, dict[str, object]]
    runtimes: dict[str, VertiportRuntime]


_lock = Lock()
_simulations: dict[str, SimulationState] = {}


def create_simulation(payload: dict) -> dict:
    scenario_id = str(payload.get("scenarioId") or payload.get("scenario_id") or "").strip()
    if not scenario_id:
        raise ValueError("scenarioId is required.")
    random_seed = _optional_int(payload.get("randomSeed", payload.get("random_seed")), default=42)
    flight_sample_limit = _optional_int(
        payload.get("flightSampleLimit", payload.get("flight_sample_limit")),
        default=500,
    )
    flight_sample_limit = max(0, min(flight_sample_limit, 2000))

    scenario_state = demand_service.get_scenario_state(scenario_id)
    result = _run_simulation(
        scenario_id=scenario_id,
        scenario_summary=scenario_state.summary,
        passengers=scenario_state.passengers,
        random_seed=random_seed,
        flight_sample_limit=flight_sample_limit,
    )
    with _lock:
        _simulations[result.simulation_id] = result
    return result.summary


def get_simulation(simulation_id: str) -> dict:
    return _get_state(simulation_id).summary


def get_flight_page(
    simulation_id: str,
    *,
    origin: str | None = None,
    destination: str | None = None,
    aircraft_id: str | None = None,
    offset: int = 0,
    limit: int = 200,
) -> dict:
    state = _get_state(simulation_id)
    flights = state.flights
    if origin:
        flights = [f for f in flights if f.get("origin") == origin]
    if destination:
        flights = [f for f in flights if f.get("destination") == destination]
    if aircraft_id:
        flights = [f for f in flights if f.get("aircraftId") == aircraft_id]
    total = len(flights)
    page = flights[offset : offset + limit]
    return {
        "simulationId": simulation_id,
        "originFilter": origin,
        "destinationFilter": destination,
        "aircraftFilter": aircraft_id,
        "offset": offset,
        "limit": limit,
        "total": total,
        "items": page,
    }


def get_vertiport_detail(simulation_id: str, vertiport_id: str) -> dict:
    state = _get_state(simulation_id)
    detail = state.vertiports.get(vertiport_id)
    if detail is None:
        raise KeyError(f"Vertiport not found in simulation: {vertiport_id}")
    return detail


def get_snapshot(
    simulation_id: str,
    *,
    time_seconds: float,
    vertiport_id: str | None = None,
) -> dict:
    state = _get_state(simulation_id)
    sim_info = state.summary.get("simulation") if isinstance(state.summary, dict) else {}
    duration = float(sim_info.get("durationSeconds") or 0) if isinstance(sim_info, dict) else 0.0
    time_value = max(0.0, min(float(time_seconds or 0), duration or float(time_seconds or 0)))
    selected_vertiport = vertiport_id or next(iter(state.runtimes), None)
    return {
        "simulationId": simulation_id,
        "timeSeconds": round(time_value, 2),
        "timeLabel": _format_seconds(time_value),
        "airspace": _build_airspace_snapshot(state.flights, time_value),
        "vertiport": (
            _build_vertiport_snapshot(state.runtimes[selected_vertiport], time_value)
            if selected_vertiport and selected_vertiport in state.runtimes
            else None
        ),
    }


def export_flights_csv(simulation_id: str) -> bytes:
    state = _get_state(simulation_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "flight_plan_id",
            "flight_id",
            "aircraft_id",
            "aircraft_type",
            "origin",
            "destination",
            "origin_gate",
            "origin_fato",
            "destination_fato",
            "destination_gate",
            "passengers",
            "capacity",
            "load_factor",
            "assigned_at",
            "boarding_start",
            "boarding_end",
            "gate_out",
            "fato_in",
            "takeoff_time",
            "arrival_queue_enter",
            "landing_start",
            "landing_time",
            "gate_in",
            "deboarding_end",
            "route_distance_km",
        ]
    )
    for flight in state.flights:
        times = flight.get("times") or {}
        writer.writerow(
            [
                flight.get("flightPlanId"),
                flight.get("flightId"),
                flight.get("aircraftId"),
                flight.get("aircraftTypeLabel"),
                flight.get("origin"),
                flight.get("destination"),
                flight.get("originGateId"),
                flight.get("originFatoId"),
                flight.get("destinationFatoId"),
                flight.get("destinationGateId"),
                flight.get("passengerCount"),
                flight.get("capacity"),
                flight.get("loadFactor"),
                times.get("assignedAt"),
                times.get("boardingStart"),
                times.get("boardingEnd"),
                times.get("gateOut"),
                times.get("fatoIn"),
                times.get("takeoffTime"),
                times.get("arrivalQueueEnter"),
                times.get("landingStart"),
                times.get("landingTime"),
                times.get("gateIn"),
                times.get("deboardingEnd"),
                flight.get("routeDistanceKm"),
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def _get_state(simulation_id: str) -> SimulationState:
    with _lock:
        state = _simulations.get(simulation_id)
    if state is None:
        raise KeyError(f"Simulation not found: {simulation_id}")
    return state


def _run_simulation(
    *,
    scenario_id: str,
    scenario_summary: dict[str, object],
    passengers: list[Any],
    random_seed: int,
    flight_sample_limit: int,
) -> SimulationState:
    rng = random.Random(random_seed)
    warnings: list[str] = []
    ports = load_vertiports()
    port_ids = [str(port["id"]) for port in ports]
    port_codes = {port_id: f"{index + 1:02d}" for index, port_id in enumerate(port_ids)}
    port_by_id = {str(port["id"]): port for port in ports}
    runtimes, aircraft = _build_runtime_state(port_ids, port_codes, warnings)
    aliases = _build_name_aliases(port_ids)
    demand_by_hour = _aggregate_hourly_demand(passengers, aliases, port_ids, warnings)

    demand_info = scenario_summary.get("demand") if isinstance(scenario_summary, dict) else {}
    if not isinstance(demand_info, dict):
        demand_info = {}
    scenario_date = str(demand_info.get("scenarioDate") or "")
    operation_start = str(demand_info.get("operationStart") or "00:00")
    operation_end = str(demand_info.get("operationEnd") or "23:59")
    op_start_s = _parse_hhmm_seconds(operation_start)
    op_end_s = _parse_hhmm_seconds(operation_end)
    if op_start_s == op_end_s:
        op_end_s = op_start_s + 24 * 3600
    elif op_end_s < op_start_s:
        op_end_s += 24 * 3600

    for ac in aircraft.values():
        ac.available_at = op_start_s

    planner = get_planner()
    route_cache: dict[str, dict[str, object]] = {}
    blocked_pairs: set[tuple[str, str]] = set()
    route_sequence: dict[tuple[str, str], int] = defaultdict(int)
    flights: list[dict[str, object]] = []
    arrival_queue: list[tuple[float, int, str, dict[str, object]]] = []
    unserved_records: list[dict[str, object]] = []
    hourly_summary: list[dict[str, object]] = []
    flight_counter = 0
    event_seq = 0

    for origins in demand_by_hour.values():
        for origin, destinations in origins.items():
            runtime = runtimes.get(origin)
            if runtime is None:
                continue
            for destination, count in destinations.items():
                runtime.requested_by_destination[destination] += count

    all_hours = sorted(demand_by_hour)
    for hour in all_hours:
        hour_start = max(hour * 3600, op_start_s)
        hour_end = min((hour + 1) * 3600, op_end_s)
        if hour_end <= hour_start:
            continue
        remaining = {
            origin: dict(destinations)
            for origin, destinations in demand_by_hour[hour].items()
        }
        requested = _sum_nested(remaining)
        served_before = len(flights)
        passengers_before = sum(int(f["passengerCount"]) for f in flights)

        queue: list[tuple[float, int, str]] = []
        order = 0
        for ac in aircraft.values():
            if ac.available_at < hour_end:
                event_time = max(ac.available_at, hour_start)
                heapq.heappush(queue, (event_time, order, ac.aircraft_id))
                order += 1

        while queue or arrival_queue:
            next_departure_time = queue[0][0] if queue else math.inf
            next_arrival_time = arrival_queue[0][0] if arrival_queue else math.inf

            if next_arrival_time < next_departure_time and next_arrival_time < hour_end:
                arrival_time, _, aircraft_id, flight = heapq.heappop(arrival_queue)
                ac = aircraft[aircraft_id]
                destination_runtime = runtimes[str(flight["destination"])]
                if _complete_landing_leg(
                    flight=flight,
                    aircraft=ac,
                    destination_runtime=destination_runtime,
                    request_time=arrival_time,
                    warnings=warnings,
                ):
                    if ac.available_at < hour_end:
                        heapq.heappush(queue, (ac.available_at, order, ac.aircraft_id))
                        order += 1
                else:
                    event_seq += 1
                    heapq.heappush(arrival_queue, (arrival_time + 300.0, event_seq, aircraft_id, flight))
                continue

            if not queue or _sum_nested(remaining) <= 0 or next_departure_time >= hour_end:
                break

            event_time, _, aircraft_id = heapq.heappop(queue)
            ac = aircraft[aircraft_id]
            if ac.available_at >= hour_end:
                continue
            assign_at = max(event_time, ac.available_at, hour_start)
            if assign_at >= hour_end:
                continue
            origin = ac.current_vertiport
            flight = None
            destination = None
            passenger_count = 0
            local_blocked = set(blocked_pairs)

            for _attempt in range(MAX_DESTINATION_ATTEMPTS):
                destination = _choose_destination(
                    remaining.get(origin) or {},
                    ac.seats,
                    rng,
                    local_blocked,
                    origin,
                )
                if destination is None:
                    break
                route_key = f"{origin}|{destination}"
                route_info = route_cache.get(route_key)
                if route_info is None:
                    try:
                        route_result = planner.find_route(origin, destination)
                        profile = build_mission_profile(
                            air_distance_m=float(route_result.distance_km) * 1000.0
                        )
                    except Exception as exc:  # route failures should not abort the whole sim
                        blocked_pairs.add((origin, destination))
                        local_blocked.add((origin, destination))
                        warnings.append(f"Route unavailable for {origin} -> {destination}: {exc}")
                        continue
                    route_info = _route_info(origin, destination, route_result, profile)
                    route_cache[route_key] = route_info

                passenger_count = min(int(remaining[origin][destination]), ac.seats)
                if passenger_count <= 0:
                    local_blocked.add((origin, destination))
                    continue
                next_route_sequence = route_sequence[(origin, destination)] + 1
                next_flight_counter = flight_counter + 1
                flight = _schedule_departure_leg(
                    sequence=next_flight_counter,
                    route_sequence=next_route_sequence,
                    aircraft=ac,
                    origin=origin,
                    destination=destination,
                    passenger_count=passenger_count,
                    assign_at=assign_at,
                    route_info=route_info,
                    origin_runtime=runtimes[origin],
                    port_codes=port_codes,
                    scenario_date=scenario_date,
                    warnings=warnings,
                )
                if flight:
                    route_sequence[(origin, destination)] = next_route_sequence
                    flight_counter = next_flight_counter
                    break
                local_blocked.add((origin, destination))

            if not flight or not destination:
                if ac.available_at < hour_end:
                    ac.available_at = max(ac.available_at, assign_at + 300.0)
                    heapq.heappush(queue, (ac.available_at, order, ac.aircraft_id))
                    order += 1
                continue
            flights.append(flight)
            event_seq += 1
            heapq.heappush(
                arrival_queue,
                (
                    float(flight["timeSeconds"]["arrivalQueueEnter"]),
                    event_seq,
                    ac.aircraft_id,
                    flight,
                ),
            )
            remaining[origin][destination] -= passenger_count
            runtimes[origin].served_by_destination[destination] += passenger_count
            runtimes[origin].served_passengers += passenger_count
            runtimes[origin].departures += 1
            runtimes[destination].arrivals += 1
            if ac.available_at < hour_end:
                heapq.heappush(queue, (ac.available_at, order, ac.aircraft_id))
                order += 1

        unserved = _sum_nested(remaining)
        for origin, destinations in remaining.items():
            for destination, count in destinations.items():
                if count <= 0:
                    continue
                runtimes[origin].unserved_by_destination[destination] += count
                unserved_records.append(
                    {
                        "hour": hour,
                        "hourLabel": f"{hour % 24:02d}:00",
                        "origin": origin,
                        "destination": destination,
                        "passengers": count,
                        "reason": "hour_closed",
                    }
                )
        hourly_summary.append(
            {
                "hour": hour,
                "hourLabel": f"{hour % 24:02d}:00",
                "requestedPassengers": requested,
                "servedPassengers": sum(int(f["passengerCount"]) for f in flights) - passengers_before,
                "unservedPassengers": unserved,
                "flights": len(flights) - served_before,
            }
        )

    max_landing_time = op_end_s + 12 * 3600
    while arrival_queue:
        arrival_time, _, aircraft_id, flight = heapq.heappop(arrival_queue)
        if arrival_time > max_landing_time:
            warnings.append(f"Landing retry limit exceeded for {flight.get('flightPlanId')}.")
            continue
        ac = aircraft[aircraft_id]
        destination_runtime = runtimes[str(flight["destination"])]
        if not _complete_landing_leg(
            flight=flight,
            aircraft=ac,
            destination_runtime=destination_runtime,
            request_time=arrival_time,
            warnings=warnings,
        ):
            event_seq += 1
            heapq.heappush(arrival_queue, (arrival_time + 300.0, event_seq, aircraft_id, flight))

    total_requested = sum(item["requestedPassengers"] for item in hourly_summary)
    total_served = sum(int(f["passengerCount"]) for f in flights)
    total_unserved = sum(item["passengers"] for item in unserved_records)
    final_fleet_by_port = _final_fleet_by_port(aircraft)
    vertiport_summaries = _build_vertiport_summaries(
        runtimes,
        aircraft,
        final_fleet_by_port,
        port_by_id,
    )
    route_summaries = _build_route_summaries(route_cache, flights)

    simulation_id = uuid4().hex[:12]
    summary = {
        "simulationId": simulation_id,
        "scenarioId": scenario_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "randomSeed": random_seed,
        "demand": {
            "scenarioDate": scenario_date,
            "operationStart": operation_start,
            "operationEnd": operation_end,
            "requestedPassengers": total_requested,
            "servedPassengers": total_served,
            "unservedPassengers": total_unserved,
        },
        "fleet": {
            "totalAircraft": len(aircraft),
            "byType": _count_aircraft_by_type(aircraft.values()),
            "types": AIRCRAFT_TYPES,
        },
        "summary": {
            "flightCount": len(flights),
            "routeCount": len(route_summaries),
            "activeVertiports": sum(1 for item in vertiport_summaries if item["departures"] or item["arrivals"]),
            "servedRate": round(total_served / total_requested, 6) if total_requested else 0,
        },
        "timeline": hourly_summary,
        "vertiports": vertiport_summaries,
        "routes": list(route_summaries.values()),
        "flights": {
            "total": len(flights),
            "sampleLimit": flight_sample_limit,
            "sample": flights[:flight_sample_limit],
        },
        "unserved": {
            "total": total_unserved,
            "records": unserved_records[:500],
        },
        "warnings": _unique(warnings),
        "simulation": {
            "mode": "vp_sim_coupled",
            "durationSeconds": round(max(op_end_s, max((ac.available_at for ac in aircraft.values()), default=op_end_s)), 2),
            "operationStartSeconds": op_start_s,
            "operationEndSeconds": op_end_s,
        },
    }
    vertiport_details = {item["id"]: item for item in vertiport_summaries}
    return SimulationState(
        simulation_id=simulation_id,
        summary=summary,
        flights=flights,
        vertiports=vertiport_details,
        routes=route_summaries,
        runtimes=runtimes,
    )


def _build_airspace_snapshot(flights: list[dict[str, object]], time_value: float) -> list[dict[str, object]]:
    visible: list[dict[str, object]] = []
    for flight in flights:
        airspace = flight.get("airspace") if isinstance(flight, dict) else None
        if not isinstance(airspace, dict):
            continue
        start = float(airspace.get("start") or 0)
        end = float(airspace.get("end") or 0)
        if not (start <= time_value < end):
            continue
        geometry = airspace.get("geometry") or []
        position = _interpolate_geometry_position(geometry, (time_value - start) / max(0.001, end - start))
        if not position:
            continue
        visible.append(
            {
                "flightPlanId": flight.get("flightPlanId"),
                "flightId": flight.get("flightId"),
                "aircraftId": flight.get("aircraftId"),
                "typeId": flight.get("aircraftTypeId"),
                "typeLabel": flight.get("aircraftTypeLabel"),
                "origin": flight.get("origin"),
                "destination": flight.get("destination"),
                "passengerCount": flight.get("passengerCount"),
                "capacity": flight.get("capacity"),
                "state": "airspace",
                "lon": position[0],
                "lat": position[1],
                "progress": round((time_value - start) / max(0.001, end - start), 4),
            }
        )
    return visible


def _build_vertiport_snapshot(runtime: VertiportRuntime, time_value: float) -> dict[str, object]:
    aircraft = []
    queued_aircraft = 0
    for item in runtime.internal_aircraft:
        segment = next(
            (
                candidate
                for candidate in item.get("segments", [])
                if candidate["start"] <= time_value < candidate["end"]
            ),
            None,
        )
        if not segment:
            continue
        if segment.get("state") == "waiting":
            queued_aircraft += 1
        position = vp_segment_position(segment, time_value)
        if not position:
            continue
        aircraft.append(
            {
                "id": item.get("aircraftId") or item.get("id"),
                "flightPlanId": item.get("flightPlanId"),
                "flightId": item.get("flightId"),
                "kind": item.get("kind"),
                "typeId": item.get("typeId"),
                "typeLabel": item.get("typeLabel"),
                "state": segment.get("state"),
                "description": segment.get("description"),
                "x": position["x"],
                "y": position["y"],
                "altitude": position.get("altitude", 0),
                "origin": item.get("origin"),
                "destination": item.get("destination"),
            }
        )
    stats = summarize_vp_at(runtime.internal_aircraft, time_value)
    stats["activeAircraft"] = len(aircraft)
    stats["queuedAircraft"] = queued_aircraft
    return {
        "id": runtime.vertiport_id,
        "name": runtime.name,
        "timeSeconds": round(time_value, 2),
        "timeLabel": _format_seconds(time_value),
        "layout": runtime.layout,
        "aircraft": aircraft,
        "stats": stats,
    }


def _interpolate_geometry_position(geometry: list, progress: float) -> tuple[float, float] | None:
    coords = [
        (float(item[0]), float(item[1]))
        for item in geometry
        if isinstance(item, (list, tuple)) and len(item) >= 2
    ]
    if not coords:
        return None
    if len(coords) == 1:
        return coords[0]
    progress = max(0.0, min(1.0, float(progress)))
    lengths = []
    total = 0.0
    for a, b in zip(coords, coords[1:]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        lengths.append(length)
        total += length
    if total <= 0:
        return coords[-1]
    target = total * progress
    acc = 0.0
    for index, length in enumerate(lengths):
        if acc + length >= target:
            ratio = (target - acc) / max(length, 0.0000001)
            a = coords[index]
            b = coords[index + 1]
            return (a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio)
        acc += length
    return coords[-1]


def _build_runtime_state(
    port_ids: list[str],
    port_codes: dict[str, str],
    warnings: list[str],
) -> tuple[dict[str, VertiportRuntime], dict[str, Aircraft]]:
    configs = {item.get("vertiportId"): item for item in vertiport_config_store.list_configs()}
    runtimes: dict[str, VertiportRuntime] = {}
    aircraft: dict[str, Aircraft] = {}
    aircraft_seq = 1

    for port_id in port_ids:
        cfg = configs.get(port_id) or {}
        layout_name = cfg.get("layoutName")
        layout = None
        if layout_name:
            try:
                layout = normalize_layout(layout_library.get_layout(str(layout_name)))
            except KeyError:
                warnings.append(f"Layout not found for {port_id}: {layout_name}")
            except Exception as exc:
                warnings.append(f"Invalid layout for {port_id}: {exc}")
                layout = None
        resources = _layout_resources(layout, cfg)
        model = build_vp_model(layout) if layout else None
        vp_resources = _initial_vp_resources(model) if model else {}
        gate_available_at = {gate_id: 0.0 for gate_id in resources["gateIds"]}
        runtime = VertiportRuntime(
            vertiport_id=port_id,
            code=port_codes[port_id],
            name=port_id,
            layout=layout,
            model=model,
            resources=vp_resources,
            gate_ids=resources["gateIds"],
            takeoff_fato_ids=resources["takeoffFatoIds"],
            landing_fato_ids=resources["landingFatoIds"],
            gate_available_at=gate_available_at,
            takeoff_fato_available_at={fato_id: 0.0 for fato_id in resources["takeoffFatoIds"]},
            landing_fato_available_at={fato_id: 0.0 for fato_id in resources["landingFatoIds"]},
        )

        assignments = ((cfg.get("fleet") or {}).get("gateAssignments") or {})
        for gate_id in sorted(assignments):
            if model and gate_id not in model["entities"]:
                warnings.append(f"Fleet assignment references missing gate at {port_id}: {gate_id}")
                continue
            raw = assignments.get(gate_id) or {}
            type_id = str(raw.get("typeId") or "").strip()
            type_info = AIRCRAFT_TYPES.get(type_id)
            if not type_info:
                seats = _optional_int(raw.get("seats"), default=4)
                type_id = f"a{seats}" if f"a{seats}" in AIRCRAFT_TYPES else "a4"
                type_info = AIRCRAFT_TYPES[type_id]
            seats = int(type_info["seats"])
            aircraft_id = f"UAM{aircraft_seq:04d}"
            aircraft_seq += 1
            aircraft[aircraft_id] = Aircraft(
                aircraft_id=aircraft_id,
                type_id=type_id,
                type_label=str(type_info["label"]),
                seats=seats,
                current_vertiport=port_id,
                current_gate_id=gate_id,
                available_at=0.0,
            )
            runtime.initial_fleet_by_type[type_id] = runtime.initial_fleet_by_type.get(type_id, 0) + 1
            runtime.gate_available_at.setdefault(gate_id, 0.0)
            runtime.gate_available_at[gate_id] = float("inf")
            if runtime.resources:
                runtime.resources["gates"][gate_id] = float("inf")
        runtimes[port_id] = runtime

    if not aircraft:
        warnings.append("No initially assigned aircraft were found. Check vertiport layout/fleet assignment.")
    return runtimes, aircraft


def _initial_vp_resources(model: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        "links": {link["id"]: 0.0 for link in model["links"]},
        "fatos": {fato["id"]: 0.0 for fato in model["fatos"]},
        "gates": {gate["id"]: 0.0 for gate in model["gates"]},
        "nodes": {node["id"]: 0.0 for node in model["nodes"]},
    }


def _layout_resources(layout: dict | None, cfg: dict) -> dict[str, list[str]]:
    entities = list((layout or {}).get("entities") or [])
    gate_ids = sorted(str(e.get("id")) for e in entities if e.get("type") == "gate" and e.get("id"))
    fatoes = [e for e in entities if e.get("type") == "fato" and e.get("id")]
    takeoff_fatoes = [
        str(e["id"])
        for e in fatoes
        if str(e.get("fatoMode") or "both").strip().lower() in {"both", "takeoff", ""}
    ]
    landing_fatoes = [
        str(e["id"])
        for e in fatoes
        if str(e.get("fatoMode") or "both").strip().lower() in {"both", "landing", ""}
    ]
    if not gate_ids:
        assignments = ((cfg.get("fleet") or {}).get("gateAssignments") or {})
        gate_ids = sorted(str(key) for key in assignments) or ["gate-1"]
    all_fatoes = sorted(str(e["id"]) for e in fatoes) or ["fato-1"]
    if not takeoff_fatoes:
        takeoff_fatoes = all_fatoes
    if not landing_fatoes:
        landing_fatoes = all_fatoes
    return {
        "gateIds": gate_ids,
        "takeoffFatoIds": sorted(takeoff_fatoes),
        "landingFatoIds": sorted(landing_fatoes),
    }


def _aggregate_hourly_demand(
    passengers: list[Any],
    aliases: dict[str, str],
    port_ids: list[str],
    warnings: list[str],
) -> dict[int, dict[str, dict[str, int]]]:
    port_set = set(port_ids)
    demand: dict[int, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    unmapped: set[str] = set()
    for record in passengers:
        origin = _normalize_demand_name(getattr(record, "origin", ""), aliases, port_set)
        destination = _normalize_demand_name(getattr(record, "destination", ""), aliases, port_set)
        if origin is None:
            unmapped.add(str(getattr(record, "origin", "")))
            continue
        if destination is None:
            unmapped.add(str(getattr(record, "destination", "")))
            continue
        if origin == destination:
            continue
        hour = int(getattr(record, "arrival_time").hour)
        demand[hour][origin][destination] += 1
        if origin in demand[hour]:
            pass
    if unmapped:
        warnings.append("Demand vertiport names could not be mapped: " + ", ".join(sorted(unmapped)))
    for origins in demand.values():
        for origin, destinations in origins.items():
            runtime_destinations = dict(destinations)
            for destination, count in runtime_destinations.items():
                if count <= 0:
                    destinations.pop(destination, None)
    return demand


def _build_name_aliases(port_ids: list[str]) -> dict[str, str]:
    aliases = {name: name for name in port_ids}
    manual = {
        "영등포·여의도": "여의도",
        "상암·수색": "상암",
        "사당·이수": "사당",
        "가산·대림": "가산",
        "수서·문정": "수서",
        "연신내·불광": "연신내",
        "천호·길동": "천호",
    }
    aliases.update({k: v for k, v in manual.items() if v in port_ids})
    return aliases


def _normalize_demand_name(name: str, aliases: dict[str, str], port_set: set[str]) -> str | None:
    text = str(name).strip()
    if text in aliases:
        return aliases[text]
    if text in port_set:
        return text
    for token in text.replace("/", "·").split("·"):
        token = token.strip()
        if token in port_set:
            return token
    matches = [port_id for port_id in port_set if port_id and port_id in text]
    if len(matches) == 1:
        return matches[0]
    return None


def _choose_destination(
    destinations: dict[str, int],
    seats: int,
    rng: random.Random,
    blocked_pairs: set[tuple[str, str]],
    origin: str,
) -> str | None:
    active = [
        (destination, count)
        for destination, count in destinations.items()
        if count > 0 and (origin, destination) not in blocked_pairs
    ]
    if not active:
        return None
    full = [(destination, count) for destination, count in active if count >= seats]
    if full:
        total = sum(count for _, count in full)
        pick = rng.uniform(0, total)
        acc = 0.0
        for destination, count in full:
            acc += count
            if pick <= acc:
                return destination
        return full[-1][0]
    return max(active, key=lambda item: (item[1], item[0]))[0]


def _route_info(origin: str, destination: str, route_result: Any, profile: dict) -> dict[str, object]:
    phases = profile.get("phases") or []
    phase_by_code = {str(phase.get("code")): phase for phase in phases}
    taxi_out_s = float((phase_by_code.get("A") or {}).get("durationS") or 0)
    taxi_in_s = float((phase_by_code.get("K") or {}).get("durationS") or 0)
    takeoff_service_s = max(
        MIN_TAKEOFF_SERVICE_S,
        float((phase_by_code.get("B") or {}).get("durationS") or 0),
    )
    landing_service_s = max(
        MIN_LANDING_SERVICE_S,
        float((phase_by_code.get("J") or {}).get("durationS") or 0),
    )
    enroute_s = sum(
        float((phase_by_code.get(code) or {}).get("durationS") or 0)
        for code in ("C", "E", "F", "G", "I")
    )
    return {
        "key": f"{origin}|{destination}",
        "origin": origin,
        "destination": destination,
        "path": list(route_result.path),
        "distanceKm": round(float(route_result.distance_km), 4),
        "geometry": [[round(lon, 6), round(lat, 6)] for lon, lat in route_result.points],
        "profile": {
            "taxiOutS": taxi_out_s,
            "taxiInS": taxi_in_s,
            "takeoffServiceS": takeoff_service_s,
            "enrouteS": enroute_s,
            "landingServiceS": landing_service_s,
            "totalDurationS": round(
                taxi_out_s + takeoff_service_s + enroute_s + landing_service_s + taxi_in_s,
                2,
            ),
        },
    }


def _schedule_departure_leg(
    *,
    sequence: int,
    route_sequence: int,
    aircraft: Aircraft,
    origin: str,
    destination: str,
    passenger_count: int,
    assign_at: float,
    route_info: dict[str, object],
    origin_runtime: VertiportRuntime,
    port_codes: dict[str, str],
    scenario_date: str,
    warnings: list[str],
) -> dict[str, object] | None:
    if not origin_runtime.model or not origin_runtime.layout:
        warnings.append(f"VP simulation layout is missing for {origin}.")
        return None
    origin_gate_id = aircraft.current_gate_id
    if origin_gate_id not in origin_runtime.model["entities"]:
        warnings.append(f"Aircraft {aircraft.aircraft_id} is assigned to missing gate {origin_gate_id} at {origin}.")
        return None

    flight_plan_id = (
        f"FPL{port_codes.get(origin, '00')}{port_codes.get(destination, '00')}{route_sequence:03d}"
    )
    flight_id = f"FLT{sequence:06d}"
    departure = schedule_vp_departure(
        aircraft_id=aircraft.aircraft_id,
        gate_id=origin_gate_id,
        request_time=assign_at,
        model=origin_runtime.model,
        resources=origin_runtime.resources,
        parameters=origin_runtime.layout["simulationParameters"],
    )
    if not departure:
        warnings.append(f"No vp_sim departure path for {aircraft.aircraft_id} at {origin}/{origin_gate_id}.")
        return None

    departure_aircraft = _tag_internal_aircraft(
        departure["aircraft"],
        flight_plan_id=flight_plan_id,
        flight_id=flight_id,
        aircraft=aircraft,
        passenger_count=passenger_count,
        origin=origin,
        destination=destination,
    )
    origin_runtime.internal_aircraft.append(departure_aircraft)

    takeoff_time = float(departure["completionTime"])
    arrival_queue_enter = takeoff_time + float(route_info["profile"]["enrouteS"])
    origin_fato_id = departure_aircraft.get("fatoId")
    gate_out = float(departure["gateReleaseTime"])
    fato_in = _first_segment_time_touching(
        departure_aircraft["segments"],
        origin_fato_id,
        default=gate_out,
    )
    aircraft.state = "airborne"
    aircraft.available_at = math.inf

    times_raw = {
        "assignedAt": assign_at,
        "boardingStart": assign_at,
        "boardingEnd": gate_out,
        "gateOut": gate_out,
        "takeoffQueueEnter": gate_out,
        "fatoIn": fato_in,
        "takeoffTime": takeoff_time,
        "airborneStart": takeoff_time,
        "arrivalQueueEnter": arrival_queue_enter,
    }
    return {
        "flightPlanId": flight_plan_id,
        "flightId": flight_id,
        "aircraftId": aircraft.aircraft_id,
        "aircraftTypeId": aircraft.type_id,
        "aircraftTypeLabel": aircraft.type_label,
        "capacity": aircraft.seats,
        "passengerCount": passenger_count,
        "loadFactor": round(passenger_count / aircraft.seats, 4) if aircraft.seats else 0,
        "origin": origin,
        "destination": destination,
        "originCode": port_codes.get(origin),
        "destinationCode": port_codes.get(destination),
        "originGateId": origin_gate_id,
        "originFatoId": origin_fato_id,
        "destinationFatoId": None,
        "destinationGateId": None,
        "routeKey": route_info["key"],
        "routeDistanceKm": route_info["distanceKm"],
        "routePath": route_info["path"],
        "scenarioDate": scenario_date,
        "times": {key: _format_seconds(value) for key, value in times_raw.items()},
        "timeSeconds": {key: round(value, 2) for key, value in times_raw.items()},
        "airspace": {
            "start": round(takeoff_time, 2),
            "end": round(arrival_queue_enter, 2),
            "geometry": route_info["geometry"],
        },
        "durations": {
            "originVpS": round(takeoff_time - assign_at, 2),
            "enrouteS": round(float(route_info["profile"]["enrouteS"]), 2),
        },
    }


def _complete_landing_leg(
    *,
    flight: dict[str, object],
    aircraft: Aircraft,
    destination_runtime: VertiportRuntime,
    request_time: float,
    warnings: list[str],
) -> bool:
    landing = _schedule_best_landing_trial(
        aircraft_id=aircraft.aircraft_id,
        request_time=request_time,
        runtime=destination_runtime,
    )
    if not landing:
        return False

    commit_vp_resources(destination_runtime.resources, landing["resources"])
    destination_gate_id = landing["gateId"]
    destination_runtime.resources["gates"][destination_gate_id] = float("inf")
    landing_aircraft = _tag_internal_aircraft(
        landing["aircraft"],
        flight_plan_id=str(flight["flightPlanId"]),
        flight_id=str(flight["flightId"]),
        aircraft=aircraft,
        passenger_count=int(flight["passengerCount"]),
        origin=str(flight["origin"]),
        destination=str(flight["destination"]),
    )
    destination_runtime.internal_aircraft.append(landing_aircraft)

    landing_segments = landing_aircraft["segments"]
    landing_start = _first_airborne_start_to_fato(landing_segments, default=request_time)
    landing_time = _first_airborne_end_to_fato(landing_segments, default=landing["completionTime"])
    gate_in = float(landing["completionTime"])
    deboarding_end = float(landing["nextDepartureRequestTime"])
    times = dict(flight.get("timeSeconds") or {})
    times.update(
        {
            "landingStart": landing_start,
            "landingTime": landing_time,
            "gateIn": gate_in,
            "deboardingEnd": deboarding_end,
            "availableAt": deboarding_end,
        }
    )
    flight["destinationFatoId"] = landing_aircraft.get("fatoId")
    flight["destinationGateId"] = destination_gate_id
    flight["timeSeconds"] = {key: round(float(value), 2) for key, value in times.items()}
    flight["times"] = {key: _format_seconds(float(value)) for key, value in times.items()}
    durations = dict(flight.get("durations") or {})
    durations["destinationVpS"] = round(deboarding_end - request_time, 2)
    durations["totalS"] = round(deboarding_end - float(times["assignedAt"]), 2)
    flight["durations"] = durations

    aircraft.current_vertiport = str(flight["destination"])
    aircraft.current_gate_id = destination_gate_id
    aircraft.available_at = deboarding_end
    aircraft.state = "available"
    return True


def _schedule_flight(
    *,
    sequence: int,
    route_sequence: int,
    aircraft: Aircraft,
    origin: str,
    destination: str,
    passenger_count: int,
    assign_at: float,
    route_info: dict[str, object],
    origin_runtime: VertiportRuntime,
    destination_runtime: VertiportRuntime,
    port_codes: dict[str, str],
    scenario_date: str,
    warnings: list[str],
) -> dict[str, object] | None:
    if not origin_runtime.model or not destination_runtime.model:
        warnings.append(f"VP simulation layout is missing for {origin} or {destination}.")
        return None

    profile = route_info["profile"]
    origin_gate_id = aircraft.current_gate_id
    if origin_gate_id not in origin_runtime.model["entities"]:
        warnings.append(f"Aircraft {aircraft.aircraft_id} is assigned to missing gate {origin_gate_id} at {origin}.")
        return None

    flight_plan_id = (
        f"FPL{port_codes.get(origin, '00')}{port_codes.get(destination, '00')}{route_sequence:03d}"
    )
    flight_id = f"FLT{sequence:06d}"
    sim_aircraft_id = aircraft.aircraft_id

    origin_trial = clone_vp_resources(origin_runtime.resources)
    departure = schedule_vp_departure(
        aircraft_id=sim_aircraft_id,
        gate_id=origin_gate_id,
        request_time=assign_at,
        model=origin_runtime.model,
        resources=origin_trial,
        parameters=origin_runtime.layout["simulationParameters"],
    )
    if not departure:
        warnings.append(f"No vp_sim departure path for {aircraft.aircraft_id} at {origin}/{origin_gate_id}.")
        return None

    takeoff_time = float(departure["completionTime"])
    arrival_queue_enter = takeoff_time + float(profile["enrouteS"])
    landing = _schedule_best_landing_trial(
        aircraft_id=sim_aircraft_id,
        request_time=arrival_queue_enter,
        runtime=destination_runtime,
    )
    if not landing:
        warnings.append(f"No vp_sim landing slot for {aircraft.aircraft_id}: {origin} -> {destination}.")
        return None

    commit_vp_resources(origin_runtime.resources, origin_trial)
    commit_vp_resources(destination_runtime.resources, landing["resources"])
    destination_gate_id = landing["gateId"]
    destination_runtime.resources["gates"][destination_gate_id] = float("inf")

    departure_aircraft = _tag_internal_aircraft(
        departure["aircraft"],
        flight_plan_id=flight_plan_id,
        flight_id=flight_id,
        aircraft=aircraft,
        passenger_count=passenger_count,
        origin=origin,
        destination=destination,
    )
    landing_aircraft = _tag_internal_aircraft(
        landing["aircraft"],
        flight_plan_id=flight_plan_id,
        flight_id=flight_id,
        aircraft=aircraft,
        passenger_count=passenger_count,
        origin=origin,
        destination=destination,
    )
    origin_runtime.internal_aircraft.append(departure_aircraft)
    destination_runtime.internal_aircraft.append(landing_aircraft)

    departure_segments = departure_aircraft["segments"]
    landing_segments = landing_aircraft["segments"]
    boarding_start = assign_at
    gate_out = departure["gateReleaseTime"]
    fato_in = _first_segment_time_touching(departure_segments, departure_aircraft.get("fatoId"), default=gate_out)
    boarding_end = gate_out
    landing_start = _first_airborne_start_to_fato(landing_segments, default=arrival_queue_enter)
    landing_time = _first_airborne_end_to_fato(landing_segments, default=landing["completionTime"])
    gate_in = landing["completionTime"]
    deboarding_end = landing["nextDepartureRequestTime"]

    aircraft.current_vertiport = destination
    aircraft.current_gate_id = destination_gate_id
    aircraft.available_at = deboarding_end
    aircraft.state = "available"

    times_raw = {
        "assignedAt": assign_at,
        "boardingStart": boarding_start,
        "boardingEnd": boarding_end,
        "gateOut": gate_out,
        "takeoffQueueEnter": gate_out,
        "fatoIn": fato_in,
        "takeoffTime": takeoff_time,
        "airborneStart": takeoff_time,
        "arrivalQueueEnter": arrival_queue_enter,
        "landingStart": landing_start,
        "landingTime": landing_time,
        "gateIn": gate_in,
        "deboardingEnd": deboarding_end,
        "availableAt": deboarding_end,
    }
    return {
        "flightPlanId": flight_plan_id,
        "flightId": flight_id,
        "aircraftId": aircraft.aircraft_id,
        "aircraftTypeId": aircraft.type_id,
        "aircraftTypeLabel": aircraft.type_label,
        "capacity": aircraft.seats,
        "passengerCount": passenger_count,
        "loadFactor": round(passenger_count / aircraft.seats, 4) if aircraft.seats else 0,
        "origin": origin,
        "destination": destination,
        "originCode": port_codes.get(origin),
        "destinationCode": port_codes.get(destination),
        "originGateId": origin_gate_id,
        "originFatoId": origin_fato_id,
        "destinationFatoId": destination_fato_id,
        "destinationGateId": destination_gate_id,
        "routeKey": route_info["key"],
        "routeDistanceKm": route_info["distanceKm"],
        "routePath": route_info["path"],
        "scenarioDate": scenario_date,
        "times": {key: _format_seconds(value) for key, value in times_raw.items()},
        "timeSeconds": {key: round(value, 2) for key, value in times_raw.items()},
        "airspace": {
            "start": round(takeoff_time, 2),
            "end": round(arrival_queue_enter, 2),
            "geometry": route_info["geometry"],
        },
        "durations": {
            "originVpS": round(takeoff_time - assign_at, 2),
            "enrouteS": round(float(profile["enrouteS"]), 2),
            "destinationVpS": round(deboarding_end - arrival_queue_enter, 2),
            "totalS": round(deboarding_end - assign_at, 2),
        },
    }


def _schedule_best_landing_trial(
    *,
    aircraft_id: str,
    request_time: float,
    runtime: VertiportRuntime,
) -> dict[str, Any] | None:
    if not runtime.model or not runtime.layout:
        return None
    best: dict[str, Any] | None = None
    for gate_id in runtime.gate_ids:
        if gate_id not in runtime.model["entities"]:
            continue
        if math.isinf(runtime.resources.get("gates", {}).get(gate_id, 0.0)):
            continue
        trial = clone_vp_resources(runtime.resources)
        result = schedule_vp_landing(
            aircraft_id=aircraft_id,
            gate_id=gate_id,
            request_time=request_time,
            model=runtime.model,
            resources=trial,
            parameters=runtime.layout["simulationParameters"],
        )
        if not result or not math.isfinite(float(result.get("completionTime", math.inf))):
            continue
        candidate = {
            **result,
            "gateId": gate_id,
            "resources": trial,
        }
        if best is None or float(candidate["completionTime"]) < float(best["completionTime"]):
            best = candidate
    return best


def _tag_internal_aircraft(
    item: dict[str, Any],
    *,
    flight_plan_id: str,
    flight_id: str,
    aircraft: Aircraft,
    passenger_count: int,
    origin: str,
    destination: str,
) -> dict[str, Any]:
    tagged = deepcopy(item)
    tagged["flightPlanId"] = flight_plan_id
    tagged["flightId"] = flight_id
    tagged["aircraftId"] = aircraft.aircraft_id
    tagged["typeId"] = aircraft.type_id
    tagged["typeLabel"] = aircraft.type_label
    tagged["seats"] = aircraft.seats
    tagged["passengerCount"] = passenger_count
    tagged["origin"] = origin
    tagged["destination"] = destination
    return tagged


def _first_segment_time_touching(
    segments: list[dict[str, Any]],
    entity_id: str | None,
    *,
    default: float,
) -> float:
    if not entity_id:
        return default
    for segment in segments:
        if segment.get("at", {}).get("id") == entity_id:
            return float(segment["start"])
        if segment.get("to", {}).get("id") == entity_id:
            return float(segment["end"])
        if segment.get("from", {}).get("id") == entity_id:
            return float(segment["start"])
    return default


def _first_airborne_start_to_fato(segments: list[dict[str, Any]], *, default: float) -> float:
    for segment in segments:
        if segment.get("state") == "airborne":
            return float(segment["start"])
    return default


def _first_airborne_end_to_fato(segments: list[dict[str, Any]], *, default: float) -> float:
    for segment in segments:
        if segment.get("state") == "airborne":
            return float(segment["end"])
    return default


def _claim_resource(availability: dict[str, float], ready_at: float) -> tuple[str, float]:
    if not availability:
        return "resource-1", ready_at
    resource_id = min(availability, key=lambda item: (max(availability[item], ready_at), item))
    start = max(availability[resource_id], ready_at)
    return resource_id, start


def _claim_gate(
    runtime: VertiportRuntime,
    ready_at: float,
    warnings: list[str],
) -> tuple[str, float]:
    if not runtime.gate_available_at:
        gate_id = "gate-1"
        runtime.gate_available_at[gate_id] = 0.0
        return gate_id, ready_at
    finite = {
        gate_id: value
        for gate_id, value in runtime.gate_available_at.items()
        if value != float("inf")
    }
    if not finite:
        runtime.overflow_gate_seq += 1
        gate_id = f"overflow-{runtime.overflow_gate_seq}"
        runtime.gate_available_at[gate_id] = float("inf")
        if not runtime.overflow_warning_added:
            warnings.append(
                f"All layout gates occupied at {runtime.vertiport_id}; overflow parking was used."
            )
            runtime.overflow_warning_added = True
        return gate_id, ready_at
    gate_id = min(finite, key=lambda item: (max(finite[item], ready_at), item))
    return gate_id, max(finite[gate_id], ready_at)


def _build_vertiport_summaries(
    runtimes: dict[str, VertiportRuntime],
    aircraft: dict[str, Aircraft],
    final_fleet_by_port: dict[str, list[Aircraft]],
    port_by_id: dict[str, dict],
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for port_id, runtime in runtimes.items():
        final_aircraft = sorted(
            final_fleet_by_port.get(port_id, []),
            key=lambda item: item.aircraft_id,
        )
        destinations = sorted(
            set(runtime.requested_by_destination)
            | set(runtime.served_by_destination)
            | set(runtime.unserved_by_destination)
        )
        demand_by_destination = [
            {
                "destination": destination,
                "requested": int(runtime.requested_by_destination.get(destination, 0)),
                "served": int(runtime.served_by_destination.get(destination, 0)),
                "unserved": int(runtime.unserved_by_destination.get(destination, 0)),
            }
            for destination in destinations
        ]
        port = port_by_id.get(port_id) or {}
        summaries.append(
            {
                "id": port_id,
                "code": runtime.code,
                "name": port_id,
                "class": port.get("class"),
                "lat": port.get("lat"),
                "lon": port.get("lon"),
                "resources": {
                    "gateCount": len(runtime.gate_ids),
                    "overflowParkingCount": runtime.overflow_gate_seq,
                    "takeoffFatoCount": len(runtime.takeoff_fato_ids),
                    "landingFatoCount": len(runtime.landing_fato_ids),
                    "gateIds": runtime.gate_ids,
                    "takeoffFatoIds": runtime.takeoff_fato_ids,
                    "landingFatoIds": runtime.landing_fato_ids,
                },
                "initialFleetByType": _fill_type_counts(runtime.initial_fleet_by_type),
                "finalFleetByType": _fill_type_counts(_count_aircraft_by_type(final_aircraft)),
                "aircraft": [
                    {
                        "aircraftId": ac.aircraft_id,
                        "typeId": ac.type_id,
                        "typeLabel": ac.type_label,
                        "seats": ac.seats,
                        "gateId": ac.current_gate_id,
                        "availableAt": _format_seconds(ac.available_at),
                    }
                    for ac in final_aircraft
                ],
                "demandByDestination": demand_by_destination,
                "requestedPassengers": sum(item["requested"] for item in demand_by_destination),
                "servedPassengers": sum(item["served"] for item in demand_by_destination),
                "unservedPassengers": sum(item["unserved"] for item in demand_by_destination),
                "departures": runtime.departures,
                "arrivals": runtime.arrivals,
            }
        )
    return summaries


def _build_route_summaries(
    route_cache: dict[str, dict[str, object]],
    flights: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"flights": 0, "passengers": 0})
    for flight in flights:
        key = str(flight.get("routeKey"))
        counts[key]["flights"] += 1
        counts[key]["passengers"] += int(flight.get("passengerCount") or 0)
    summaries: dict[str, dict[str, object]] = {}
    for key, route in route_cache.items():
        summaries[key] = {
            "key": key,
            "origin": route["origin"],
            "destination": route["destination"],
            "path": route["path"],
            "distanceKm": route["distanceKm"],
            "geometry": route["geometry"],
            "flightCount": counts[key]["flights"],
            "passengerCount": counts[key]["passengers"],
        }
    return summaries


def _final_fleet_by_port(aircraft: dict[str, Aircraft]) -> dict[str, list[Aircraft]]:
    result: dict[str, list[Aircraft]] = defaultdict(list)
    for ac in aircraft.values():
        result[ac.current_vertiport].append(ac)
    return result


def _count_aircraft_by_type(items) -> dict[str, int]:
    counts: dict[str, int] = {type_id: 0 for type_id in AIRCRAFT_TYPES}
    for ac in items:
        type_id = ac.type_id if isinstance(ac, Aircraft) else str(ac)
        counts[type_id] = counts.get(type_id, 0) + 1
    return counts


def _fill_type_counts(counts: dict[str, int]) -> dict[str, int]:
    return {type_id: int(counts.get(type_id, 0)) for type_id in AIRCRAFT_TYPES}


def _sum_nested(data: dict[str, dict[str, int]]) -> int:
    return sum(int(count) for destinations in data.values() for count in destinations.values())


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        result.append(item)
        seen.add(item)
    return result


def _parse_hhmm_seconds(value: str) -> int:
    try:
        hour_text, minute_text = str(value).split(":", 1)
        return (int(hour_text) * 3600) + (int(minute_text) * 60)
    except (TypeError, ValueError):
        return 0


def _format_seconds(seconds: float) -> str:
    if not math.isfinite(float(seconds)):
        return "—"
    total = max(0, int(round(seconds)))
    day_offset, rem = divmod(total, 24 * 3600)
    hour, rem = divmod(rem, 3600)
    minute, second = divmod(rem, 60)
    suffix = f"+{day_offset}d" if day_offset else ""
    return f"{hour:02d}:{minute:02d}:{second:02d}{suffix}"


def _optional_int(value: object, *, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
