from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

AIR_POINT_TYPES = {"takeoffPoint", "landingPoint", "commonAirPoint"}
PRE_LANDING_BUFFER_SECONDS = 3 * 60
NODE_CLEARANCE_SECONDS = 10


def run_vertiport_simulation(layout: dict[str, Any], options: dict[str, Any] | None = None) -> dict[str, Any]:
    options = options or {}
    duration_seconds = max(60, float(options.get("durationMinutes", 120)) * 60)
    model = build_model(layout)
    parameters = layout["simulationParameters"]
    resources = {
        "links": {link["id"]: 0.0 for link in model["links"]},
        "fatos": {fato["id"]: 0.0 for fato in model["fatos"]},
        "gates": {gate["id"]: math.inf for gate in model["gates"]},
        "nodes": {node["id"]: 0.0 for node in model["nodes"]},
    }
    queue = [{"type": "departure", "gateId": gate["id"], "time": 0.0} for gate in model["gates"]]
    aircraft: list[dict[str, Any]] = []
    warnings: list[str] = []
    aircraft_index = 1

    sort_queue(queue)
    while queue:
        job = queue.pop(0)
        if job["time"] > duration_seconds + 3600:
            continue

        if job["type"] == "departure":
            result = schedule_departure(
                aircraft_id=f"D-{aircraft_index}",
                gate_id=job["gateId"],
                request_time=job["time"],
                model=model,
                resources=resources,
                parameters=parameters,
            )
            aircraft_index += 1
            if not result:
                warnings.append(f"No takeoff route from {job['gateId']}.")
                continue
            aircraft.append(result["aircraft"])
            queue.append({
                "type": "landing",
                "gateId": job["gateId"],
                "time": max(
                    0.0,
                    result["gateReleaseTime"] - estimate_pre_landing_lead_seconds(job["gateId"], model, parameters),
                ),
            })

        if job["type"] == "landing":
            result = schedule_landing(
                aircraft_id=f"L-{aircraft_index}",
                gate_id=job["gateId"],
                request_time=job["time"],
                model=model,
                resources=resources,
                parameters=parameters,
            )
            aircraft_index += 1
            if not result:
                warnings.append(f"No landing route to {job['gateId']}.")
                continue
            aircraft.append(result["aircraft"])
            queue.append({
                "type": "departure",
                "gateId": job["gateId"],
                "time": result["nextDepartureRequestTime"],
            })

        sort_queue(queue)
        if len(aircraft) > 2000:
            warnings.append("Simulation stopped at 2000 aircraft events.")
            break

    return {
        "durationSeconds": duration_seconds,
        "aircraft": aircraft,
        "warnings": warnings,
        "stats": summarize_at(aircraft, duration_seconds),
    }


def get_simulation_snapshot(result: dict[str, Any] | None, time_seconds: float) -> dict[str, Any]:
    if not result:
        return empty_snapshot()
    time_value = clamp(float(time_seconds or 0), 0, result["durationSeconds"])
    visible_aircraft = []
    queued_aircraft = 0

    for item in result["aircraft"]:
        segment = next((candidate for candidate in item["segments"] if candidate["start"] <= time_value < candidate["end"]), None)
        if not segment:
            continue
        if segment["state"] == "waiting":
            queued_aircraft += 1
        position = segment_position(segment, time_value)
        if not position:
            continue
        visible_aircraft.append({
            "id": item["id"],
            "kind": item["kind"],
            "label": "D" if item["kind"] == "departure" else "L",
            "state": segment["state"],
            "description": segment["description"],
            "x": position["x"],
            "y": position["y"],
            "altitude": position.get("altitude", 0),
        })

    return {
        "timeSeconds": time_value,
        "aircraft": visible_aircraft,
        "stats": {
            **summarize_at(result["aircraft"], time_value),
            "activeAircraft": len(visible_aircraft),
            "queuedAircraft": queued_aircraft,
        },
    }


def schedule_departure(
    aircraft_id: str,
    gate_id: str,
    request_time: float,
    model: dict[str, Any],
    resources: dict[str, dict[str, float]],
    parameters: dict[str, Any],
) -> dict[str, Any] | None:
    gate = model["entities"][gate_id]
    candidates = build_takeoff_candidates(gate_id, model)
    start_procedure_seconds = minutes(parameters["gateProcedure"]["engineStartAndTowDisconnectMinutes"])
    lock_seconds = minutes(parameters["fatoProcedure"]["postOperationLockMinutes"])
    ground_speed = positive(parameters["vehicle"]["groundSpeedMps"], 1)
    air_speed = positive(parameters["vehicle"]["airSpeedMps"], 1)
    vertical_speed = positive(parameters["vehicle"]["verticalSpeedMps"], 1)

    best = None
    for candidate in candidates:
        trial_resources = clone_resources(resources)
        air_travel_seconds = air_travel_time(candidate["fato"], candidate["airPoint"], air_speed, vertical_speed)
        terminal_ready_time = max(
            trial_resources["fatos"].get(candidate["fato"]["id"], 0.0),
            trial_resources["links"].get(candidate["airLink"]["id"], 0.0),
        )
        segments: list[dict[str, Any]] = []
        ground = reserve_path(
            path=candidate["groundPath"],
            start_time=request_time,
            resources=trial_resources,
            model=model,
            speed=ground_speed,
            terminal_resource_id=candidate["fato"]["id"],
            terminal_resource_map=trial_resources["fatos"],
            terminal_ready_time=terminal_ready_time,
            terminal_entry_requires_resource_clear=True,
            terminal_wait_description="FATO/이륙 경로 점유 대기",
        )
        segments.extend(ground["segments"])

        procedure_start = ground["endTime"]
        air_start = procedure_start + start_procedure_seconds
        segments.append(stationary_segment(
            at=candidate["fato"],
            start=procedure_start,
            end=air_start,
            state="procedure",
            description="시동 및 견인장치 분리",
        ))

        air_end = air_start + air_travel_seconds
        trial_resources["fatos"][candidate["fato"]["id"]] = air_end + lock_seconds
        trial_resources["links"][candidate["airLink"]["id"]] = air_end + NODE_CLEARANCE_SECONDS
        segments.append(moving_segment(
            from_entity=candidate["fato"],
            to_entity=candidate["airPoint"],
            start=air_start,
            end=air_end,
            state="airborne",
            description="이륙",
        ))

        gate_release_time = first_movement_start(segments) or request_time
        trial_resources["gates"][gate["id"]] = gate_release_time
        completion_time = air_end
        if not best or completion_time < best["completionTime"]:
            best = {
                "resources": trial_resources,
                "aircraft": {
                    "id": aircraft_id,
                    "kind": "departure",
                    "gateId": gate_id,
                    "fatoId": candidate["fato"]["id"],
                    "completionTime": completion_time,
                    "segments": segments,
                },
                "gateReleaseTime": gate_release_time,
                "completionTime": completion_time,
            }

    if not best:
        return None
    commit_resources(resources, best["resources"])
    return best


def schedule_landing(
    aircraft_id: str,
    gate_id: str,
    request_time: float,
    model: dict[str, Any],
    resources: dict[str, dict[str, float]],
    parameters: dict[str, Any],
) -> dict[str, Any] | None:
    candidates = build_landing_candidates(gate_id, model)
    stop_and_connect_seconds = minutes(parameters["gateProcedure"]["engineStopAndTowConnectMinutes"])
    handling_seconds = minutes(parameters["gateProcedure"]["groundHandlingMinutes"])
    lock_seconds = minutes(parameters["fatoProcedure"]["postOperationLockMinutes"])
    ground_speed = positive(parameters["vehicle"]["groundSpeedMps"], 1)
    air_speed = positive(parameters["vehicle"]["airSpeedMps"], 1)
    vertical_speed = positive(parameters["vehicle"]["verticalSpeedMps"], 1)

    best = None
    for candidate in candidates:
        trial_resources = clone_resources(resources)
        segments: list[dict[str, Any]] = []
        air_travel_seconds = air_travel_time(candidate["airPoint"], candidate["fato"], air_speed, vertical_speed)
        air_start = max(
            request_time,
            trial_resources["links"].get(candidate["airLink"]["id"], 0.0),
            trial_resources["fatos"].get(candidate["fato"]["id"], 0.0),
        )
        if air_start > request_time:
            segments.append(external_waiting_segment(
                start=request_time,
                end=air_start,
                state="waiting",
                description="착륙 수요 대기",
            ))

        touchdown_time = air_start + air_travel_seconds
        trial_resources["links"][candidate["airLink"]["id"]] = touchdown_time + NODE_CLEARANCE_SECONDS
        segments.append(moving_segment(
            from_entity=candidate["airPoint"],
            to_entity=candidate["fato"],
            start=air_start,
            end=touchdown_time,
            state="airborne",
            description="착륙",
        ))
        segments.append(stationary_segment(
            at=candidate["fato"],
            start=touchdown_time,
            end=touchdown_time + lock_seconds,
            state="fatoLock",
            description="FATO 잠금",
        ))
        ground_start = touchdown_time + lock_seconds + stop_and_connect_seconds
        segments.append(stationary_segment(
            at=candidate["fato"],
            start=touchdown_time + lock_seconds,
            end=ground_start,
            state="procedure",
            description="시동 종료 및 견인장치 연결",
        ))

        ground = reserve_path(
            path=candidate["groundPath"],
            start_time=ground_start,
            resources=trial_resources,
            model=model,
            speed=ground_speed,
            terminal_resource_id=gate_id,
            terminal_resource_map=trial_resources["gates"],
            terminal_wait_description="Gate 배정 대기",
        )
        segments.extend(ground["segments"])
        fato_exit_time = first_movement_from_entity_end(ground["segments"], candidate["fato"]["id"], ground_start)
        trial_resources["fatos"][candidate["fato"]["id"]] = max(ground_start, fato_exit_time)

        gate_arrival = ground["endTime"]
        next_departure_request_time = gate_arrival + handling_seconds
        trial_resources["gates"][gate_id] = next_departure_request_time
        segments.append(stationary_segment(
            at=model["entities"][gate_id],
            start=gate_arrival,
            end=gate_arrival + handling_seconds,
            state="handling",
            description="충전 및 청소",
        ))

        completion_time = gate_arrival
        if not best or completion_time < best["completionTime"]:
            best = {
                "resources": trial_resources,
                "aircraft": {
                    "id": aircraft_id,
                    "kind": "landing",
                    "gateId": gate_id,
                    "fatoId": candidate["fato"]["id"],
                    "completionTime": completion_time,
                    "segments": segments,
                },
                "nextDepartureRequestTime": next_departure_request_time,
                "completionTime": completion_time,
            }

    if not best:
        return None
    commit_resources(resources, best["resources"])
    return best


def reserve_path(
    path: dict[str, Any],
    start_time: float,
    resources: dict[str, dict[str, float]],
    model: dict[str, Any],
    speed: float,
    terminal_resource_id: str | None = None,
    terminal_resource_map: dict[str, float] | None = None,
    terminal_ready_time: float | None = None,
    terminal_entry_requires_resource_clear: bool = False,
    terminal_wait_description: str = "Link 점유 대기",
) -> dict[str, Any]:
    segments: list[dict[str, Any]] = []
    current_time = start_time
    if not path or not path["links"]:
        return {"segments": segments, "endTime": current_time}

    for index, link in enumerate(path["links"]):
        from_entity = model["entities"][path["nodes"][index]]
        to_entity = model["entities"][path["nodes"][index + 1]]
        travel_seconds = link["distance"] / speed
        is_terminal_link = bool(
            terminal_resource_id
            and index == len(path["links"]) - 1
            and to_entity["id"] == terminal_resource_id
        )
        link_ready_time = resources["links"].get(link["id"], 0.0)
        node_ready_time = resources["nodes"].get(to_entity["id"], 0.0) if to_entity["type"] == "node" else 0.0
        terminal_ready_start = 0.0
        if is_terminal_link:
            ready_time = terminal_ready_time if terminal_ready_time is not None else (terminal_resource_map or {}).get(terminal_resource_id, 0.0)
            terminal_ready_start = ready_time if terminal_entry_requires_resource_clear else ready_time - travel_seconds
        node_ready_start = node_ready_time - travel_seconds
        link_start = max(current_time, link_ready_time, terminal_ready_start, node_ready_start)
        if link_start > current_time:
            reserve_waiting_position(resources, from_entity, link_start)
            segments.append(stationary_segment(
                at=from_entity,
                start=current_time,
                end=link_start,
                state="waiting",
                description=(
                    "Node 점유 대기"
                    if node_ready_start >= link_ready_time and node_ready_start >= terminal_ready_start and node_ready_start > current_time
                    else terminal_wait_description
                    if is_terminal_link and terminal_ready_start > current_time
                    else "Link 점유 대기"
                ),
            ))
        link_end = link_start + travel_seconds
        resources["links"][link["id"]] = link_end
        reserve_departing_node(resources, from_entity, link_start)
        segments.append(moving_segment(
            from_entity=from_entity,
            to_entity=to_entity,
            start=link_start,
            end=link_end,
            state="taxi",
            description="지상 이동",
        ))
        current_time = link_end
        if to_entity["type"] == "node":
            clear_time = current_time + NODE_CLEARANCE_SECONDS
            resources["nodes"][to_entity["id"]] = max(resources["nodes"].get(to_entity["id"], 0.0), clear_time)
            segments.append(stationary_segment(
                at=to_entity,
                start=current_time,
                end=clear_time,
                state="clearance",
                description="Node 통과 간격",
            ))
            current_time = clear_time

    return {"segments": segments, "endTime": current_time}


def build_takeoff_candidates(gate_id: str, model: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for air_link in model["airLinks"]:
        fato = next((entity for entity in air_link["ends"] if entity["type"] == "fato"), None)
        air_point = next((entity for entity in air_link["ends"] if is_takeoff_air_point(entity)), None)
        if not fato or not air_point or not can_use_fato_for_air_point(fato, air_point):
            continue
        ground_path = dijkstra(model["groundAdjacency"], gate_id, fato["id"])
        if ground_path:
            candidates.append({"fato": fato, "airPoint": air_point, "airLink": air_link, "groundPath": ground_path})
    return candidates


def build_landing_candidates(gate_id: str, model: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for air_link in model["airLinks"]:
        fato = next((entity for entity in air_link["ends"] if entity["type"] == "fato"), None)
        air_point = next((entity for entity in air_link["ends"] if is_landing_air_point(entity)), None)
        if not fato or not air_point or not can_use_fato_for_air_point(fato, air_point):
            continue
        ground_path = dijkstra(model["groundAdjacency"], fato["id"], gate_id)
        if ground_path:
            candidates.append({"fato": fato, "airPoint": air_point, "airLink": air_link, "groundPath": ground_path})
    return candidates


def estimate_pre_landing_lead_seconds(gate_id: str, model: dict[str, Any], parameters: dict[str, Any]) -> float:
    candidates = build_landing_candidates(gate_id, model)
    if not candidates:
        return 0.0
    lock_seconds = minutes(parameters["fatoProcedure"]["postOperationLockMinutes"])
    stop_and_connect_seconds = minutes(parameters["gateProcedure"]["engineStopAndTowConnectMinutes"])
    ground_speed = positive(parameters["vehicle"]["groundSpeedMps"], 1)
    air_speed = positive(parameters["vehicle"]["airSpeedMps"], 1)
    vertical_speed = positive(parameters["vehicle"]["verticalSpeedMps"], 1)

    best = 0.0
    for candidate in candidates:
        air_seconds = air_travel_time(candidate["airPoint"], candidate["fato"], air_speed, vertical_speed)
        ground_seconds = candidate["groundPath"]["cost"] / ground_speed
        best = max(best, air_seconds + lock_seconds + stop_and_connect_seconds + ground_seconds + PRE_LANDING_BUFFER_SECONDS)
    return best


def build_model(layout: dict[str, Any]) -> dict[str, Any]:
    entities = {entity["id"]: deepcopy(entity) for entity in layout["entities"]}
    links = []
    for link in layout["links"]:
        from_entity = entities.get(link["from"])
        to_entity = entities.get(link["to"])
        if not from_entity or not to_entity:
            continue
        normalized = {
            **deepcopy(link),
            "fromEntity": from_entity,
            "toEntity": to_entity,
            "ends": [from_entity, to_entity],
            "distance": distance(from_entity, to_entity),
            "isAirLink": from_entity.get("type") in AIR_POINT_TYPES or to_entity.get("type") in AIR_POINT_TYPES,
        }
        links.append(normalized)
    ground_links = [link for link in links if not link["isAirLink"]]
    air_links = [link for link in links if link["isAirLink"]]
    ground_adjacency = {entity_id: [] for entity_id in entities}
    for link in ground_links:
        ground_adjacency[link["from"]].append({"node": link["to"], "link": link, "cost": link["distance"]})
        ground_adjacency[link["to"]].append({"node": link["from"], "link": link, "cost": link["distance"]})
    return {
        "entities": entities,
        "links": links,
        "groundLinks": ground_links,
        "airLinks": air_links,
        "groundAdjacency": ground_adjacency,
        "gates": [entity for entity in entities.values() if entity["type"] == "gate"],
        "fatos": [entity for entity in entities.values() if entity["type"] == "fato"],
        "nodes": [entity for entity in entities.values() if entity["type"] == "node"],
    }


def dijkstra(adjacency: dict[str, list[dict[str, Any]]], start: str, goal: str) -> dict[str, Any] | None:
    if start == goal:
        return {"nodes": [start], "links": [], "cost": 0.0}
    distances = {start: 0.0}
    previous: dict[str, dict[str, Any]] = {}
    unvisited = set(adjacency.keys())

    while unvisited:
        current = None
        best_distance = math.inf
        for node in unvisited:
            distance_value = distances.get(node, math.inf)
            if distance_value < best_distance:
                current = node
                best_distance = distance_value
        if not current or best_distance == math.inf:
            break
        unvisited.remove(current)
        if current == goal:
            break
        for edge in adjacency.get(current, []):
            if edge["node"] not in unvisited:
                continue
            alt = best_distance + edge["cost"]
            if alt < distances.get(edge["node"], math.inf):
                distances[edge["node"]] = alt
                previous[edge["node"]] = {"node": current, "link": edge["link"]}

    if goal not in previous:
        return None
    nodes = [goal]
    links = []
    current = goal
    while current != start:
        step = previous.get(current)
        if not step:
            return None
        links.insert(0, step["link"])
        nodes.insert(0, step["node"])
        current = step["node"]
    return {"nodes": nodes, "links": links, "cost": distances[goal]}


def moving_segment(from_entity: dict[str, Any], to_entity: dict[str, Any], start: float, end: float, state: str, description: str) -> dict[str, Any]:
    return {
        "state": state,
        "description": description,
        "start": start,
        "end": end,
        "from": point_from_entity(from_entity),
        "to": point_from_entity(to_entity),
        "fromAltitude": entity_altitude(from_entity),
        "toAltitude": entity_altitude(to_entity),
    }


def stationary_segment(at: dict[str, Any], start: float, end: float, state: str, description: str) -> dict[str, Any]:
    return {
        "state": state,
        "description": description,
        "start": start,
        "end": end,
        "at": point_from_entity(at),
    }


def external_waiting_segment(start: float, end: float, state: str, description: str) -> dict[str, Any]:
    return {"state": state, "description": description, "start": start, "end": end}


def segment_position(segment: dict[str, Any], time_value: float) -> dict[str, Any] | None:
    if "at" in segment:
        return segment["at"]
    if "from" not in segment or "to" not in segment:
        return None
    duration = max(0.001, segment["end"] - segment["start"])
    t_value = clamp((time_value - segment["start"]) / duration, 0, 1)
    return {
        "x": segment["from"]["x"] + (segment["to"]["x"] - segment["from"]["x"]) * t_value,
        "y": segment["from"]["y"] + (segment["to"]["y"] - segment["from"]["y"]) * t_value,
        "altitude": (segment.get("fromAltitude") or 0) + ((segment.get("toAltitude") or 0) - (segment.get("fromAltitude") or 0)) * t_value,
    }


def summarize_at(aircraft: list[dict[str, Any]], time_seconds: float) -> dict[str, int]:
    takeoff_success = 0
    landing_complete = 0
    for item in aircraft:
        if item["completionTime"] <= time_seconds and item["kind"] == "departure":
            takeoff_success += 1
        if item["completionTime"] <= time_seconds and item["kind"] == "landing":
            landing_complete += 1
    return {
        "takeoffSuccess": takeoff_success,
        "landingComplete": landing_complete,
        "totalThroughput": takeoff_success + landing_complete,
    }


def empty_snapshot() -> dict[str, Any]:
    return {
        "timeSeconds": 0,
        "aircraft": [],
        "stats": {
            "takeoffSuccess": 0,
            "landingComplete": 0,
            "totalThroughput": 0,
            "activeAircraft": 0,
            "queuedAircraft": 0,
        },
    }


def point_from_entity(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "x": entity["x"],
        "y": entity["y"],
        "altitude": entity_altitude(entity),
        "id": entity["id"],
        "type": entity["type"],
    }


def first_movement_start(segments: list[dict[str, Any]]) -> float | None:
    movement = next((segment for segment in segments if "from" in segment and "to" in segment), None)
    return movement["start"] if movement else None


def first_movement_from_entity_end(segments: list[dict[str, Any]], entity_id: str, fallback: float) -> float:
    movement = next((segment for segment in segments if segment.get("from", {}).get("id") == entity_id and "to" in segment), None)
    return movement["end"] if movement else fallback


def can_use_fato_for_air_point(fato: dict[str, Any], air_point: dict[str, Any]) -> bool:
    mode = fato.get("fatoMode", "both")
    if air_point["type"] == "takeoffPoint":
        return mode in {"takeoff", "both"}
    if air_point["type"] == "landingPoint":
        return mode in {"landing", "both"}
    if air_point["type"] == "commonAirPoint":
        return mode == "both"
    return False


def is_takeoff_air_point(entity: dict[str, Any]) -> bool:
    return entity.get("type") in {"takeoffPoint", "commonAirPoint"}


def is_landing_air_point(entity: dict[str, Any]) -> bool:
    return entity.get("type") in {"landingPoint", "commonAirPoint"}


def sort_queue(queue: list[dict[str, Any]]) -> None:
    queue.sort(key=lambda item: (item["time"], job_priority(item["type"])))


def job_priority(job_type: str) -> int:
    if job_type == "departure":
        return 0
    if job_type == "landing":
        return 1
    return 2


def clone_resources(resources: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    return {key: value.copy() for key, value in resources.items()}


def commit_resources(target: dict[str, dict[str, float]], source: dict[str, dict[str, float]]) -> None:
    target.clear()
    target.update({key: value.copy() for key, value in source.items()})


def reserve_waiting_position(resources: dict[str, dict[str, float]], entity: dict[str, Any], release_time: float) -> None:
    if entity.get("type") == "node":
        resources["nodes"][entity["id"]] = max(resources["nodes"].get(entity["id"], 0.0), release_time + NODE_CLEARANCE_SECONDS)
    if entity.get("type") == "fato":
        resources["fatos"][entity["id"]] = max(resources["fatos"].get(entity["id"], 0.0), release_time)
    if entity.get("type") == "gate":
        resources["gates"][entity["id"]] = max(resources["gates"].get(entity["id"], 0.0), release_time)


def reserve_departing_node(resources: dict[str, dict[str, float]], entity: dict[str, Any], departure_time: float) -> None:
    if entity.get("type") != "node":
        return
    resources["nodes"][entity["id"]] = max(resources["nodes"].get(entity["id"], 0.0), departure_time + NODE_CLEARANCE_SECONDS)


def minutes(value: Any) -> float:
    return max(0.0, float(value or 0)) * 60


def positive(value: Any, fallback: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    return numeric if math.isfinite(numeric) and numeric > 0 else fallback


def distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.hypot((a.get("x") or 0) - (b.get("x") or 0), (a.get("y") or 0) - (b.get("y") or 0))


def air_travel_time(from_entity: dict[str, Any], to_entity: dict[str, Any], air_speed: float, vertical_speed: float) -> float:
    horizontal = distance(from_entity, to_entity)
    altitude = abs(float(from_entity.get("altitude") or 0) - float(to_entity.get("altitude") or 0))
    return max(horizontal / air_speed, altitude / vertical_speed)


def entity_altitude(entity: dict[str, Any]) -> float:
    return max(0.0, float(entity.get("altitude") or 0)) if entity.get("type") in AIR_POINT_TYPES else 0.0


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))
