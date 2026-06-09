from __future__ import annotations

from collections import defaultdict
from datetime import date
from threading import Lock
from typing import Any

from demand_gen import DemandGenerator, DemandRequest

_generator = DemandGenerator()
_lock = Lock()


def _pick(payload: dict, *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _build_request(payload: dict) -> DemandRequest:
    raw_date = _pick(payload, "scenario_date", "scenarioDate")
    if not raw_date:
        raise ValueError("scenarioDate is required (YYYY-MM-DD).")
    raw_base = _pick(payload, "base_traffic", "baseTraffic")
    if raw_base is None:
        raise ValueError("baseTraffic is required.")
    raw_ratio = _pick(payload, "transfer_ratio_percent", "transferRatioPercent")
    if raw_ratio is None:
        raise ValueError("transferRatioPercent is required.")

    kwargs = dict(
        base_traffic=int(raw_base),
        transfer_ratio_percent=float(raw_ratio),
        scenario_date=date.fromisoformat(str(raw_date)),
        operation_start=str(_pick(payload, "operation_start", "operationStart") or "07:00"),
        operation_end=str(_pick(payload, "operation_end", "operationEnd") or "22:00"),
    )
    raw_seed = _pick(payload, "random_seed", "randomSeed")
    if raw_seed is not None:
        kwargs["random_seed"] = int(raw_seed)
    raw_limit = _pick(payload, "passenger_sample_limit", "passengerSampleLimit")
    if raw_limit is not None:
        kwargs["passenger_sample_limit"] = int(raw_limit)
    raw_min_distance = _pick(payload, "min_od_distance_km", "minOdDistanceKm", "odCutoffKm")
    if raw_min_distance is not None:
        min_distance = float(raw_min_distance)
        if min_distance < 0:
            raise ValueError("minOdDistanceKm must be greater than or equal to 0.")
        kwargs["min_od_distance_km"] = min_distance
    return DemandRequest(**kwargs)


def create_scenario(payload: dict) -> dict:
    request = _build_request(payload)
    with _lock:
        return _generator.create_scenario(request)


def get_scenario(scenario_id: str) -> dict:
    with _lock:
        return _generator.get_scenario(scenario_id)


def get_scenario_state(scenario_id: str):
    with _lock:
        return _generator.get_state(scenario_id)


def get_passenger_page(
    scenario_id: str,
    *,
    origin: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> dict:
    with _lock:
        return _generator.get_passenger_page(
            scenario_id, origin=origin, offset=offset, limit=limit
        )


def get_arrival_hours(scenario_id: str, *, origin: str | None = None) -> dict:
    with _lock:
        return _generator.get_passenger_arrival_hours(scenario_id, origin=origin)


def get_od_hours(scenario_id: str) -> dict:
    with _lock:
        state = _generator.get_state(scenario_id)

    buckets: dict[int, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    for record in state.passengers:
        buckets[int(record.arrival_time.hour)][record.origin][record.destination] += 1

    demand = state.summary.get("demand", {}) if isinstance(state.summary, dict) else {}
    hours: list[dict[str, object]] = []
    for hour in range(24):
        origins = []
        for origin, destinations in sorted(buckets.get(hour, {}).items()):
            destination_rows = [
                {"destination": destination, "passengers": count}
                for destination, count in sorted(destinations.items())
                if count > 0
            ]
            if destination_rows:
                origins.append(
                    {
                        "origin": origin,
                        "total": sum(item["passengers"] for item in destination_rows),
                        "destinations": destination_rows,
                    }
                )
        hours.append(
            {
                "hour": hour,
                "hourLabel": f"{hour:02d}:00",
                "total": sum(origin["total"] for origin in origins),
                "origins": origins,
            }
        )

    return {
        "scenarioId": scenario_id,
        "scenarioDate": demand.get("scenarioDate"),
        "operationStart": demand.get("operationStart"),
        "operationEnd": demand.get("operationEnd"),
        "hours": hours,
    }


def export_passengers_csv(scenario_id: str, *, origin: str | None = None) -> bytes:
    with _lock:
        return _generator.export_passengers_csv(scenario_id, origin=origin)
