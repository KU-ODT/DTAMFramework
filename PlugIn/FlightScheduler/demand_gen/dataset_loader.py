from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .csv_utils import find_column, read_csv_rows, read_float

DAY_FILE = "TrafficDemand_DayofWork.csv"
MONTH_FILE = "TrafficDemand_Monthly.csv"
TIMELINE_FILE = "TrafficDemand_Timeline.csv"
VERTIPORT_FILE = "vertiport.csv"
DEPARTURE_RATIO_FILE = "departure_ratios.csv"
ARRIVAL_RATIO_FILE = "arrival_ratios.csv"


@dataclass(frozen=True)
class DatasetBundle:
    dataset_dir: Path
    vertiports: list[str]
    vertiport_coordinates: dict[str, tuple[float, float]]
    departure_ratios: list[float]
    arrival_ratios: list[float]
    day_weights: dict[str, float]
    month_weights: dict[str, float]
    timeline_weights: list[float]
    warnings: list[str]

    def summary(self) -> dict[str, object]:
        return {
            "datasetDir": str(self.dataset_dir),
            "vertiportCount": len(self.vertiports),
            "vertiportCoordinateCount": len(self.vertiport_coordinates),
            "activeDepartureCount": sum(1 for value in self.departure_ratios if value > 0),
            "activeArrivalCount": sum(1 for value in self.arrival_ratios if value > 0),
            "departureRatioSum": round(sum(self.departure_ratios), 6),
            "arrivalRatioSum": round(sum(self.arrival_ratios), 6),
            "warnings": list(self.warnings),
            "vertiports": list(self.vertiports),
        }


def load_dataset(dataset_dir: Path) -> DatasetBundle:
    dataset_dir = dataset_dir.expanduser().resolve()
    vertiport_path = dataset_dir / VERTIPORT_FILE
    if vertiport_path.exists():
        vertiports, vertiport_coordinates = _load_vertiports(vertiport_path)
        vertiport_note = None
    else:
        vertiports = _infer_vertiports_from_ratios(
            dataset_dir / DEPARTURE_RATIO_FILE,
            dataset_dir / ARRIVAL_RATIO_FILE,
        )
        vertiport_coordinates = {}
        vertiport_note = "Vertiport file is missing; locations were inferred from ratio files."
    departure_ratios, departure_note = _load_ratios(
        dataset_dir / DEPARTURE_RATIO_FILE,
        vertiports,
        label="departure",
    )
    arrival_ratios, arrival_note = _load_ratios(
        dataset_dir / ARRIVAL_RATIO_FILE,
        vertiports,
        label="arrival",
    )
    day_weights = _load_day_weights(dataset_dir / DAY_FILE)
    month_weights = _load_month_weights(dataset_dir / MONTH_FILE)
    timeline_weights = _load_timeline_weights(dataset_dir / TIMELINE_FILE)

    warnings: list[str] = []
    if vertiport_note:
        warnings.append(vertiport_note)
    if departure_note:
        warnings.append(departure_note)
    if arrival_note:
        warnings.append(arrival_note)
    if len(vertiport_coordinates) < len(vertiports):
        warnings.append(
            "Some vertiport coordinates are missing; distance-based OD cut-off may be unavailable."
        )
    if sum(departure_ratios) != 1.0:
        warnings.append(
            "Departure ratios are not normalized to 1.0; legacy raw-ratio behavior is preserved."
        )
    if sum(arrival_ratios) != 1.0:
        warnings.append(
            "Arrival ratios are not normalized to 1.0; legacy raw-ratio behavior is preserved."
        )

    return DatasetBundle(
        dataset_dir=dataset_dir,
        vertiports=vertiports,
        vertiport_coordinates=vertiport_coordinates,
        departure_ratios=departure_ratios,
        arrival_ratios=arrival_ratios,
        day_weights=day_weights,
        month_weights=month_weights,
        timeline_weights=timeline_weights,
        warnings=warnings,
    )


def _load_vertiports(path: Path) -> tuple[list[str], dict[str, tuple[float, float]]]:
    rows, fieldnames = read_csv_rows(path)
    name_col = (
        find_column(fieldnames, lambda key: "vertiport" in key)
        or (fieldnames[1] if len(fieldnames) > 1 else fieldnames[0])
    )
    lat_col = find_column(fieldnames, lambda key: key in {"위도", "lat", "latitude"})
    lon_col = find_column(fieldnames, lambda key: key in {"경도", "lon", "lng", "longitude"})
    names: list[str] = []
    coordinates: dict[str, tuple[float, float]] = {}
    for row in rows:
        value = str(row.get(name_col, "")).strip()
        if value:
            names.append(value)
            lat = read_float(row.get(lat_col)) if lat_col else None
            lon = read_float(row.get(lon_col)) if lon_col else None
            if lat is not None and lon is not None:
                coordinates[value] = (lat, lon)
    if not names:
        raise ValueError(f"No vertiport names were parsed from {path}")
    return names, coordinates


def _infer_vertiports_from_ratios(departure_path: Path, arrival_path: Path) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for path in (departure_path, arrival_path):
        if not path.exists():
            continue
        rows, fieldnames = read_csv_rows(path)
        key_col = (
            find_column(
                fieldnames,
                lambda key: key in {"origin", "destination", "location", "vertiport", "name"},
            )
            or fieldnames[0]
        )
        for row in rows:
            name = str(row.get(key_col, "")).strip()
            if name and name not in seen:
                names.append(name)
                seen.add(name)
    if not names:
        raise ValueError(
            f"No vertiport names were parsed from ratio files: {departure_path}, {arrival_path}"
        )
    return names


def _load_ratios(path: Path, vertiports: list[str], label: str) -> tuple[list[float], str | None]:
    if not path.exists():
        if not vertiports:
            raise ValueError("Cannot generate uniform ratios without vertiports.")
        uniform = 1.0 / len(vertiports)
        return [uniform for _ in vertiports], f"{label.capitalize()} ratio file is missing; uniform ratios are used."

    rows, fieldnames = read_csv_rows(path)
    ratio_col = find_column(fieldnames, lambda key: key == "ratio")
    if ratio_col is None:
        raise ValueError(f"Ratio column was not found in {path}")
    key_col = (
        find_column(
            fieldnames,
            lambda key: key in {"origin", "destination", "location", "vertiport", "name"},
        )
        or fieldnames[0]
    )

    mapping: dict[str, float] = {}
    for row in rows:
        name = str(row.get(key_col, "")).strip()
        ratio = read_float(row.get(ratio_col))
        if not name or ratio is None:
            continue
        mapping[name] = ratio

    aligned = [mapping.get(name, 0.0) for name in vertiports]
    if not any(value > 0 for value in aligned):
        return aligned, f"{label.capitalize()} ratios loaded, but no active vertiport matches were found."
    return aligned, None


def _load_day_weights(path: Path) -> dict[str, float]:
    rows, fieldnames = read_csv_rows(path)
    key_col = fieldnames[0]
    value_col = find_column(fieldnames, lambda key: "유입비율" in key or key == "유입비율")
    if value_col is None:
        value_col = fieldnames[2]
    result: dict[str, float] = {}
    for row in rows:
        name = str(row.get(key_col, "")).strip().lower()
        value = read_float(row.get(value_col))
        if name and value is not None:
            result[name] = value / 100.0
    if not result:
        raise ValueError(f"Day-of-week weights are empty: {path}")
    return result


def _load_month_weights(path: Path) -> dict[str, float]:
    rows, fieldnames = read_csv_rows(path)
    key_col = fieldnames[0]
    value_col = find_column(fieldnames, lambda key: "유입비율" in key or key == "유입비율")
    if value_col is None:
        value_col = fieldnames[2]
    result: dict[str, float] = {}
    for row in rows:
        name = str(row.get(key_col, "")).strip().lower()[:3]
        value = read_float(row.get(value_col))
        if name and value is not None:
            result[name] = value / 100.0
    if not result:
        raise ValueError(f"Monthly weights are empty: {path}")
    return result


def _load_timeline_weights(path: Path) -> list[float]:
    rows, fieldnames = read_csv_rows(path)
    value_col = find_column(fieldnames, lambda key: "유입비율" in key or key == "유입비율")
    if value_col is None:
        value_col = fieldnames[3]
    values: list[float] = []
    for row in rows:
        value = read_float(row.get(value_col))
        if value is not None:
            values.append(value / 100.0)
    if len(values) != 24:
        raise ValueError(f"Timeline weights must contain 24 rows: {path}")
    total = sum(values)
    if total <= 0:
        raise ValueError(f"Timeline weights sum to zero: {path}")
    return [value / total for value in values]
