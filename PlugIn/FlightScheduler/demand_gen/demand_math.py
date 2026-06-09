from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import asin, ceil, cos, radians, sin, sqrt
from typing import Mapping


EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class WindowProfileItem:
    hour: int
    label: str
    weight: float
    window_fraction: float
    effective_weight: float

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "hour": self.hour,
            "label": self.label,
            "weight": round(self.weight, 8),
            "windowFraction": round(self.window_fraction, 8),
            "effectiveWeight": round(self.effective_weight, 8),
        }


def parse_hhmm(value: str) -> int:
    text = str(value).strip()
    try:
        hour_text, minute_text = text.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid time format: {value!r}") from None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid time value: {value!r}")
    return (hour * 60) + minute


def build_window_profile(
    operation_start: str,
    operation_end: str,
    timeline_weights: list[float],
) -> list[WindowProfileItem]:
    if len(timeline_weights) != 24:
        raise ValueError("Timeline weights must contain 24 hourly entries.")

    start_min = parse_hhmm(operation_start)
    end_min = parse_hhmm(operation_end)
    intervals = _window_intervals(start_min, end_min)

    items: list[WindowProfileItem] = []
    for hour, weight in enumerate(timeline_weights):
        hour_start = hour * 60
        hour_end = hour_start + 60
        overlap = 0.0
        for left, right in intervals:
            overlap += max(0, min(hour_end, right) - max(hour_start, left))
        fraction = overlap / 60.0
        items.append(
            WindowProfileItem(
                hour=hour,
                label=f"{hour:02d}:00",
                weight=weight,
                window_fraction=fraction,
                effective_weight=weight * fraction,
            )
        )
    return items


def compute_window_share(operation_start: str, operation_end: str, timeline_weights: list[float]) -> float:
    return sum(item.effective_weight for item in build_window_profile(operation_start, operation_end, timeline_weights))


def estimate_windowed_demand(
    base_traffic: int,
    transfer_ratio_percent: float,
    window_share: float,
    *,
    scenario_date: date | None = None,
    day_weights: dict[str, float] | None = None,
    month_weights: dict[str, float] | None = None,
) -> dict[str, int | float]:
    transfer_passengers = int(base_traffic * transfer_ratio_percent / 100.0)
    day_factor = _relative_day_factor(scenario_date, day_weights)
    month_factor = _relative_month_factor(scenario_date, month_weights)
    temporal_factor = day_factor * month_factor
    date_adjusted_transfer_passengers = int(transfer_passengers * temporal_factor)
    window_adjusted_passengers = int(date_adjusted_transfer_passengers * window_share)
    return {
        "baseTraffic": base_traffic,
        "transferRatioPercent": transfer_ratio_percent,
        "transferPassengers": transfer_passengers,
        "dayFactor": round(day_factor, 8),
        "monthFactor": round(month_factor, 8),
        "temporalFactor": round(temporal_factor, 8),
        "dateAdjustedTransferPassengers": date_adjusted_transfer_passengers,
        "windowShare": round(window_share, 8),
        "windowAdjustedPassengers": window_adjusted_passengers,
        "flightEstimateMin": ceil(window_adjusted_passengers / 6) if window_adjusted_passengers else 0,
        "flightEstimateMax": ceil(window_adjusted_passengers / 4) if window_adjusted_passengers else 0,
    }


def _relative_day_factor(scenario_date: date | None, day_weights: dict[str, float] | None) -> float:
    if scenario_date is None or not day_weights:
        return 1.0
    day_mean = sum(day_weights.values()) / max(len(day_weights), 1)
    if day_mean <= 0:
        return 1.0
    day_key = scenario_date.strftime("%A").lower()
    return day_weights.get(day_key, day_mean) / day_mean


def _relative_month_factor(scenario_date: date | None, month_weights: dict[str, float] | None) -> float:
    if scenario_date is None or not month_weights:
        return 1.0
    month_mean = sum(month_weights.values()) / max(len(month_weights), 1)
    if month_mean <= 0:
        return 1.0
    month_key = scenario_date.strftime("%b").lower()
    return month_weights.get(month_key, month_mean) / month_mean


def allocate_od_matrix(
    vertiports: list[str],
    departure_ratios: list[float],
    arrival_ratios: list[float],
    total_people: int,
    *,
    min_od_distance_km: float | None = None,
    vertiport_coordinates: Mapping[str, tuple[float, float]] | None = None,
) -> dict[str, object]:
    cutoff_km = _normalize_min_distance(min_od_distance_km)
    coordinates = vertiport_coordinates or {}
    if cutoff_km is not None:
        missing = [name for name in vertiports if name not in coordinates]
        if missing:
            raise ValueError(
                "OD distance cut-off requires coordinates for vertiports: "
                + ", ".join(missing)
            )

    rows: list[dict[str, object]] = []
    pairs: list[dict[str, object]] = []
    destination_totals = [0 for _ in vertiports]
    origin_totals: list[dict[str, object]] = []
    allocated_passengers = 0
    candidate_pairs = len(vertiports) * max(0, len(vertiports) - 1)
    excluded_pairs = 0
    excluded_passengers = 0

    for i, origin in enumerate(vertiports):
        origin_total = total_people * departure_ratios[i]
        denominator = sum(arrival_ratios[j] for j in range(len(vertiports)) if j != i)
        cell_values: list[int] = []
        row_total = 0

        for j, destination in enumerate(vertiports):
            if i == j or denominator <= 0:
                count = 0
            else:
                share = arrival_ratios[j] / denominator
                original_count = round(origin_total * share)
                if cutoff_km is not None:
                    distance_km = haversine_km(coordinates[origin], coordinates[destination])
                    if distance_km < cutoff_km:
                        count = 0
                        excluded_pairs += 1
                        excluded_passengers += original_count
                    else:
                        count = original_count
                else:
                    count = original_count
            cell_values.append(count)
            row_total += count
            destination_totals[j] += count
            if count > 0:
                pairs.append(
                    {
                        "origin": origin,
                        "destination": destination,
                        "passengers": count,
                    }
                )

        rows.append(
            {
                "origin": origin,
                "total": row_total,
                "cells": cell_values,
            }
        )
        origin_totals.append({"origin": origin, "passengers": row_total})
        allocated_passengers += row_total

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
        "distanceCutoff": {
            "enabled": cutoff_km is not None,
            "minDistanceKm": cutoff_km,
            "candidatePairs": candidate_pairs,
            "excludedPairs": excluded_pairs,
            "keptPairs": candidate_pairs - excluded_pairs,
            "excludedPassengers": excluded_passengers,
        },
    }


def _window_intervals(start_min: int, end_min: int) -> list[tuple[int, int]]:
    if start_min == end_min:
        return [(0, 24 * 60)]
    if start_min < end_min:
        return [(start_min, end_min)]
    return [(start_min, 24 * 60), (0, end_min)]


def _normalize_min_distance(value: float | None) -> float | None:
    if value is None:
        return None
    cutoff_km = float(value)
    if cutoff_km < 0:
        raise ValueError("minOdDistanceKm must be greater than or equal to 0.")
    return cutoff_km if cutoff_km > 0 else None


def haversine_km(
    origin: tuple[float, float],
    destination: tuple[float, float],
) -> float:
    lat1, lon1 = origin
    lat2, lon2 = destination
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    rlat1 = radians(lat1)
    rlat2 = radians(lat2)
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(min(1.0, sqrt(a)))
