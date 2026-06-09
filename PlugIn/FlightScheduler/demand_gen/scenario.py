from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import csv
import io
from uuid import uuid4

from .dataset_loader import DatasetBundle, load_dataset
from .demand_math import (
    allocate_od_matrix,
    build_window_profile,
    compute_window_share,
    estimate_windowed_demand,
)
from .passenger_generation import PassengerRecord, generate_passenger_manifest

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data" / "defaults"


@dataclass
class DemandRequest:
    base_traffic: int
    transfer_ratio_percent: float
    scenario_date: date
    operation_start: str
    operation_end: str
    dataset_dir: str | Path | None = None
    random_seed: int | None = 42
    passenger_sample_limit: int = 100
    min_od_distance_km: float | None = None


@dataclass
class ScenarioState:
    scenario_id: str
    summary: dict[str, object]
    passengers: list[PassengerRecord]


class DemandGenerator:
    """Standalone demand generator decoupled from the FastAPI backend.

    Mirrors the demand-only pipeline from backend/services/scenario_service.py:
    preview → OD allocation → per-passenger arrival sampling. No flight/aircraft
    scheduling concerns are included.
    """

    def __init__(self, default_dataset_dir: str | Path | None = None) -> None:
        self._default_dataset_dir = (
            Path(default_dataset_dir).expanduser().resolve()
            if default_dataset_dir
            else DEFAULT_DATA_DIR
        )
        self._scenarios: dict[str, ScenarioState] = {}

    def load_default_config(self) -> dict[str, object]:
        dataset = load_dataset(self._default_dataset_dir)
        return {
            "defaultDatasetDir": str(self._default_dataset_dir),
            "dataset": dataset.summary(),
        }

    def preview(self, request: DemandRequest) -> dict[str, object]:
        dataset = load_dataset(self._resolve_dataset_dir(request.dataset_dir))
        window_profile = build_window_profile(
            request.operation_start,
            request.operation_end,
            dataset.timeline_weights,
        )
        demand = estimate_windowed_demand(
            request.base_traffic,
            request.transfer_ratio_percent,
            sum(item.effective_weight for item in window_profile),
            scenario_date=request.scenario_date,
            day_weights=dataset.day_weights,
            month_weights=dataset.month_weights,
        )
        return {
            "resolvedDatasetDir": str(dataset.dataset_dir),
            "dataset": dataset.summary(),
            "demand": demand,
            "windowProfile": [item.as_dict() for item in window_profile],
        }

    def create_scenario(self, request: DemandRequest) -> dict[str, object]:
        dataset = load_dataset(self._resolve_dataset_dir(request.dataset_dir))
        window_share = compute_window_share(
            request.operation_start,
            request.operation_end,
            dataset.timeline_weights,
        )
        demand = estimate_windowed_demand(
            request.base_traffic,
            request.transfer_ratio_percent,
            window_share,
            scenario_date=request.scenario_date,
            day_weights=dataset.day_weights,
            month_weights=dataset.month_weights,
        )
        allocation = allocate_od_matrix(
            dataset.vertiports,
            dataset.departure_ratios,
            dataset.arrival_ratios,
            int(demand["windowAdjustedPassengers"]),
            min_od_distance_km=request.min_od_distance_km,
            vertiport_coordinates=dataset.vertiport_coordinates,
        )
        passenger_data = generate_passenger_manifest(
            allocation["pairs"],
            request.scenario_date,
            dataset.timeline_weights,
            request.random_seed,
            operation_start=request.operation_start,
            operation_end=request.operation_end,
        )
        passengers: list[PassengerRecord] = passenger_data["records"]
        manifest_allocation = _allocation_from_passengers(dataset.vertiports, passengers)
        if "distanceCutoff" in allocation:
            manifest_allocation["distanceCutoff"] = allocation["distanceCutoff"]
        scenario_id = uuid4().hex[:12]

        summary = {
            "scenarioId": scenario_id,
            "resolvedDatasetDir": str(dataset.dataset_dir),
            "dataset": dataset.summary(),
            "demand": {
                **demand,
                "allocatedPassengers": manifest_allocation["allocatedPassengers"],
                "generatedPassengers": len(passengers),
                "scenarioDate": request.scenario_date.isoformat(),
                "operationStart": request.operation_start,
                "operationEnd": request.operation_end,
                "minOdDistanceKm": request.min_od_distance_km or 0,
            },
            "allocation": {
                key: value
                for key, value in manifest_allocation.items()
                if key != "pairs"
            },
            "timeline": passenger_data["timeline"],
            "passengers": {
                "total": len(passengers),
                "sampleLimit": request.passenger_sample_limit,
                "sample": [record.as_dict() for record in passengers[: request.passenger_sample_limit]],
                "origins": passenger_data["originCounts"],
            },
        }

        self._scenarios[scenario_id] = ScenarioState(
            scenario_id=scenario_id,
            summary=summary,
            passengers=passengers,
        )
        return summary

    def get_scenario(self, scenario_id: str) -> dict[str, object]:
        return self._get_state(scenario_id).summary

    def get_state(self, scenario_id: str) -> ScenarioState:
        return self._get_state(scenario_id)

    def get_passenger_page(
        self,
        scenario_id: str,
        *,
        origin: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, object]:
        state = self._get_state(scenario_id)
        passengers = state.passengers
        if origin:
            passengers = [record for record in passengers if record.origin == origin]
        total = len(passengers)
        page = passengers[offset : offset + limit]
        return {
            "scenarioId": scenario_id,
            "originFilter": origin,
            "offset": offset,
            "limit": limit,
            "total": total,
            "items": [record.as_dict() for record in page],
        }

    def get_passenger_arrival_hours(
        self,
        scenario_id: str,
        *,
        origin: str | None = None,
    ) -> dict[str, object]:
        state = self._get_state(scenario_id)
        passengers = state.passengers
        if origin:
            passengers = [record for record in passengers if record.origin == origin]
        counts = [0 for _ in range(24)]
        for record in passengers:
            counts[record.arrival_time.hour] += 1
        demand = state.summary.get("demand", {})
        operation_start = demand.get("operationStart") if isinstance(demand, dict) else None
        operation_end = demand.get("operationEnd") if isinstance(demand, dict) else None
        return {
            "scenarioId": scenario_id,
            "originFilter": origin,
            "operationStart": operation_start,
            "operationEnd": operation_end,
            "hours": [f"{hour:02d}:00" for hour in range(24)],
            "counts": counts,
            "total": sum(counts),
        }

    def export_passengers_csv(self, scenario_id: str, *, origin: str | None = None) -> bytes:
        state = self._get_state(scenario_id)
        passengers = state.passengers
        if origin:
            passengers = [record for record in passengers if record.origin == origin]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", "origin", "destination", "arrival_time", "arrival_hour"])
        for record in passengers:
            writer.writerow(
                [
                    record.id,
                    record.origin,
                    record.destination,
                    record.arrival_time.isoformat(),
                    record.arrival_time.hour,
                ]
            )
        return buffer.getvalue().encode("utf-8-sig")

    def _get_state(self, scenario_id: str) -> ScenarioState:
        state = self._scenarios.get(scenario_id)
        if state is None:
            raise KeyError(f"Scenario not found: {scenario_id}")
        return state

    def _resolve_dataset_dir(self, dataset_dir: str | Path | None) -> Path:
        if dataset_dir:
            return Path(dataset_dir).expanduser().resolve()
        return self._default_dataset_dir


def _allocation_from_passengers(
    vertiports: list[str],
    passengers: list[PassengerRecord],
) -> dict[str, object]:
    index_by_name = {name: index for index, name in enumerate(vertiports)}
    matrix = [[0 for _ in vertiports] for _ in vertiports]

    for record in passengers:
        origin_index = index_by_name.get(record.origin)
        destination_index = index_by_name.get(record.destination)
        if origin_index is None or destination_index is None:
            continue
        matrix[origin_index][destination_index] += 1

    rows: list[dict[str, object]] = []
    pairs: list[dict[str, object]] = []
    destination_totals = [0 for _ in vertiports]
    origin_totals: list[dict[str, object]] = []
    allocated_passengers = 0

    for origin_index, origin in enumerate(vertiports):
        cells = matrix[origin_index]
        row_total = sum(cells)
        rows.append(
            {
                "origin": origin,
                "total": row_total,
                "cells": list(cells),
            }
        )
        origin_totals.append({"origin": origin, "passengers": row_total})
        allocated_passengers += row_total

        for destination_index, count in enumerate(cells):
            destination_totals[destination_index] += count
            if count > 0:
                pairs.append(
                    {
                        "origin": origin,
                        "destination": vertiports[destination_index],
                        "passengers": count,
                    }
                )

    top_pairs = sorted(pairs, key=lambda item: item["passengers"], reverse=True)[:15]
    return {
        "originCount": len(vertiports),
        "destinationCount": len(vertiports),
        "destinations": list(vertiports),
        "rows": rows,
        "originTotals": origin_totals,
        "destinationTotals": [
            {"destination": name, "passengers": total}
            for name, total in zip(vertiports, destination_totals)
        ],
        "allocatedPassengers": allocated_passengers,
        "activePairs": len(pairs),
        "topPairs": top_pairs,
        "pairs": pairs,
    }
