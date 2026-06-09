"""OperationModule-compatible operational environment map data for PSU.

The PSU traffic map must not invent demo aircraft/routes when DTAM 4001 is not
feeding live data.  This module reads the same active operational environment
CSV set that OperationModule uses, then exposes GeoJSON layer payloads for
vertiports, route nodes and node-link lines.
"""
from __future__ import annotations

import csv
import io
from functools import lru_cache
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1]
MODULE_ROOT = APP_DIR.parent
EXTENSION_ROOT = MODULE_ROOT.parent
FRAMEWORK_ROOT = EXTENSION_ROOT.parent

ENV_ACTIVE_DIR = FRAMEWORK_ROOT / "DB" / "operational_environment" / "active"
ENV_DEFAULT_DIR = FRAMEWORK_ROOT / "DB" / "operational_environment" / "default"
MISSION_DATA_DIR = FRAMEWORK_ROOT / "MissionModule" / "data"
VISUALIZATION_COORD_DIR = FRAMEWORK_ROOT / "VisualizationModule" / "data" / "coordinateDB"

VERTIPORT_FILE = "vertiport_default.csv"
CORRIDOR_FILE = "corridor_default.csv"
WAYPOINT_FILE = "waypoint_default.csv"


def _detect_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _read_csv_rows(path: Path, min_columns: int) -> list[list[str]]:
    if not path.is_file():
        return []
    raw = path.read_bytes()
    if not raw:
        return []
    text = raw.decode(_detect_encoding(raw), errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    result: list[list[str]] = []
    for row in rows[1:]:
        if not row or not any(str(cell).strip() for cell in row):
            continue
        padded = [str(cell).strip() for cell in row]
        if len(padded) < min_columns:
            padded.extend([""] * (min_columns - len(padded)))
        if len(padded) > min_columns:
            padded = padded[: min_columns - 1] + [", ".join(cell for cell in padded[min_columns - 1 :] if cell)]
        result.append(padded)
    return result


def _first_existing(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _parse_float(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed


def _split_links(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    normalized = text.replace(";", ",")
    return [part.strip() for part in normalized.split(",") if part.strip()]


def _feature_collection(features: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features or []}


def _row_to_vertiport(row: list[str]) -> dict[str, Any] | None:
    name = str(row[0] if len(row) > 0 else "").strip()
    lat = _parse_float(row[2] if len(row) > 2 else None)
    lon = _parse_float(row[3] if len(row) > 3 else None)
    if not name or lat is None or lon is None:
        return None
    return {
        "name": name,
        "class": str(row[1] if len(row) > 1 else "port" or "port").strip().lower() or "port",
        "lat": lat,
        "lon": lon,
        "inr_km": _parse_float(row[4] if len(row) > 4 else None, 0),
        "otr_km": _parse_float(row[5] if len(row) > 5 else None, 0),
        "mtr_km": _parse_float(row[6] if len(row) > 6 else None, 0),
        "inr_deg": _parse_float(row[7] if len(row) > 7 else None, 0),
        "otr_deg": _parse_float(row[8] if len(row) > 8 else None, 0),
        "circle_turn": str(row[9] if len(row) > 9 else "").strip() or "Left",
        "links": _split_links(row[10] if len(row) > 10 else ""),
    }


def _row_to_corridor(row: list[str]) -> dict[str, Any] | None:
    name = str(row[0] if len(row) > 0 else "").strip()
    lat = _parse_float(row[1] if len(row) > 1 else None)
    lon = _parse_float(row[2] if len(row) > 2 else None)
    if not name or lat is None or lon is None:
        return None
    return {
        "name": name,
        "lat": lat,
        "lon": lon,
        "altitude_ft": _parse_float(row[3] if len(row) > 3 else None, 1000),
        "links": _split_links(row[4] if len(row) > 4 else ""),
        "spare_links": _split_links(row[5] if len(row) > 5 else ""),
    }


@lru_cache(maxsize=1)
def load_operational_environment() -> dict[str, Any]:
    """Load the same active vertiport/corridor dataset used by OperationModule."""

    vertiport_path = _first_existing(
        [
            ENV_ACTIVE_DIR / VERTIPORT_FILE,
            ENV_DEFAULT_DIR / VERTIPORT_FILE,
            MISSION_DATA_DIR / VERTIPORT_FILE,
            VISUALIZATION_COORD_DIR / VERTIPORT_FILE,
        ]
    )
    corridor_path = _first_existing(
        [
            ENV_ACTIVE_DIR / CORRIDOR_FILE,
            ENV_DEFAULT_DIR / CORRIDOR_FILE,
            MISSION_DATA_DIR / CORRIDOR_FILE,
            VISUALIZATION_COORD_DIR / CORRIDOR_FILE,
            MISSION_DATA_DIR / WAYPOINT_FILE,
            VISUALIZATION_COORD_DIR / WAYPOINT_FILE,
        ]
    )

    vertiport_rows = _read_csv_rows(vertiport_path, 11) if vertiport_path else []
    corridor_rows = _read_csv_rows(corridor_path, 6) if corridor_path else []
    vertiports = [entry for row in vertiport_rows if (entry := _row_to_vertiport(row)) is not None]
    corridors = [entry for row in corridor_rows if (entry := _row_to_corridor(row)) is not None]

    corridor_names = {str(entry["name"]) for entry in corridors}
    links: list[dict[str, Any]] = []
    seen_corridor_links: set[tuple[str, str, bool]] = set()
    for corridor in corridors:
        source_name = str(corridor["name"])
        for target in corridor.get("links") or []:
            if target not in corridor_names:
                continue
            key = tuple(sorted((source_name, target))) + (False,)
            if key in seen_corridor_links:
                continue
            seen_corridor_links.add(key)
            links.append({"kind": "corridor", "from": source_name, "to": target, "spare": False})
        for target in corridor.get("spare_links") or []:
            if target not in corridor_names:
                continue
            key = tuple(sorted((source_name, target))) + (True,)
            if key in seen_corridor_links:
                continue
            seen_corridor_links.add(key)
            links.append({"kind": "corridor", "from": source_name, "to": target, "spare": True})

    for vertiport in vertiports:
        source_name = str(vertiport["name"])
        for target in vertiport.get("links") or []:
            if target in corridor_names:
                links.append({"kind": "vertiport", "from": source_name, "to": target, "spare": False})

    return {
        "files": {
            "active_dir": str(ENV_ACTIVE_DIR),
            "default_dir": str(ENV_DEFAULT_DIR),
            "vertiport": str(vertiport_path) if vertiport_path else "",
            "corridor": str(corridor_path) if corridor_path else "",
        },
        "vertiports": vertiports,
        "corridors": corridors,
        "links": links,
    }


def _point_feature(entry: dict[str, Any], *, feature_id: str, kind: str) -> dict[str, Any] | None:
    lat = _parse_float(entry.get("lat") if "lat" in entry else entry.get("latitude"))
    lon = _parse_float(entry.get("lon") if "lon" in entry else entry.get("longitude"))
    if lat is None or lon is None:
        return None
    properties = {key: value for key, value in entry.items() if key not in {"lat", "lon", "latitude", "longitude"}}
    properties.update({"feature_type": kind, "kind": kind})
    if kind == "node":
        properties.setdefault("node_id", entry.get("name"))
        properties.setdefault("node_kind", "CORRIDOR")
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
        "properties": properties,
    }


def _track_feature(track: dict[str, Any]) -> dict[str, Any] | None:
    lat = _parse_float(track.get("latitude") or track.get("lat"))
    lon = _parse_float(track.get("longitude") or track.get("lon") or track.get("lng"))
    aircraft_id = str(track.get("aircraft_id") or track.get("aircraftId") or track.get("id") or "").strip()
    if not aircraft_id or lat is None or lon is None:
        return None
    properties = {key: value for key, value in track.items() if key not in {"latitude", "longitude", "lat", "lon", "lng"}}
    properties.update(
        {
            "feature_type": "track",
            "kind": "track",
            "aircraft_id": aircraft_id,
            "aircraftId": aircraft_id,
            "status": str(track.get("status") or track.get("flight_status") or "ACTIVE").upper(),
            "flight_status": str(track.get("flight_status") or track.get("status") or "ACTIVE").upper(),
            "heading": _parse_float(track.get("heading"), _parse_float(track.get("heading_deg"), 0)) or 0,
            "heading_deg": _parse_float(track.get("heading_deg"), _parse_float(track.get("heading"), 0)) or 0,
        }
    )
    return {
        "type": "Feature",
        "id": aircraft_id,
        "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
        "properties": properties,
    }


def operational_environment_map_layers(
    *,
    live_tracks: list[dict[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build PSU map layers using OperationModule environment + real 4001 tracks only."""

    env = load_operational_environment()
    vertiports = {str(entry.get("name")): entry for entry in env.get("vertiports") or []}
    corridors = {str(entry.get("name")): entry for entry in env.get("corridors") or []}

    vertiport_features = [
        feature
        for entry in vertiports.values()
        if (feature := _point_feature(entry, feature_id=f"vertiport:{entry.get('name')}", kind="vertiport")) is not None
    ]
    node_features = [
        feature
        for entry in corridors.values()
        if (feature := _point_feature(entry, feature_id=f"node:{entry.get('name')}", kind="node")) is not None
    ]

    link_features: list[dict[str, Any]] = []
    for index, link in enumerate(env.get("links") or []):
        link_kind = str(link.get("kind") or "corridor")
        source = vertiports.get(str(link.get("from"))) if link_kind == "vertiport" else corridors.get(str(link.get("from")))
        target = corridors.get(str(link.get("to")))
        if not source or not target:
            continue
        source_lat = _parse_float(source.get("lat"))
        source_lon = _parse_float(source.get("lon"))
        target_lat = _parse_float(target.get("lat"))
        target_lon = _parse_float(target.get("lon"))
        if source_lat is None or source_lon is None or target_lat is None or target_lon is None:
            continue
        link_features.append(
            {
                "type": "Feature",
                "id": f"link:{index}",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[float(source_lon), float(source_lat)], [float(target_lon), float(target_lat)]],
                },
                "properties": {
                    "feature_type": "node_link",
                    "kind": "link",
                    "linkKind": link_kind,
                    "link_type": link_kind.upper(),
                    "from": link.get("from"),
                    "to": link.get("to"),
                    "spare": bool(link.get("spare")),
                    "selected": False,
                },
            }
        )

    track_features = [feature for track in live_tracks or [] if (feature := _track_feature(track)) is not None]

    return {
        "generated_at": generated_at or "",
        "environment": env,
        "vertiports": _feature_collection(vertiport_features),
        "nodes": _feature_collection(node_features),
        "links": _feature_collection(link_features),
        "waypoints": _feature_collection([]),
        "corridors": _feature_collection([]),
        "tracks": _feature_collection(track_features),
        # No static demo routes/tracks/conflicts on the operational map. These
        # must only be populated later by a real analysis engine or live data.
        "routes": _feature_collection([]),
        "actual_tracks": _feature_collection([]),
        "conflicts": _feature_collection([]),
    }


__all__ = ["load_operational_environment", "operational_environment_map_layers"]
