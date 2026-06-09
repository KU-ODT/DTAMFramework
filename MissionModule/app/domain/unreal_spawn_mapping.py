from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from ..config import DATA_DIR


DEFAULT_UNREAL_SPAWN_CSV = DATA_DIR / "unreal_vertiport_spawn_points.csv"
VERTIPORT_ALIASES = {
    "\uc5ec\uc758\ub3c4": "\uc601\ub4f1\ud3ec",  # Yeouido -> Yeongdeungpo resource name
}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Could not decode CSV file: {path}")


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_label(value: Any) -> str:
    text = str(value or "").strip().upper()
    compact = re.sub(r"[\s_-]+", "", text)
    if compact in {"F1", "FATO1"}:
        return "FATO 1"
    if compact in {"F2", "FATO2"}:
        return "FATO 2"
    match = re.fullmatch(r"(?:G|GATE)(\d+)", compact)
    if match:
        return f"GATE {int(match.group(1))}"
    return text


def _name_candidates(vertiport_name: str) -> list[str]:
    name = str(vertiport_name or "").strip()
    if not name:
        return []
    candidates = [name]
    alias = VERTIPORT_ALIASES.get(name)
    if alias and alias not in candidates:
        candidates.append(alias)
    return candidates


def _row_matches_identifier(row: dict[str, str], identifier: str) -> bool:
    if not identifier:
        return False
    target = str(identifier).strip().upper()
    target_label = _normalise_label(target)
    fields = (
        str(row.get("s_id") or "").strip().upper(),
        str(row.get("semantic_id") or "").strip().upper(),
        _normalise_label(row.get("label")),
        str(row.get("label") or "").strip().upper(),
    )
    return target in fields or target_label in fields


@lru_cache(maxsize=4)
def load_unreal_spawn_rows(csv_path: str | None = None) -> tuple[dict[str, str], ...]:
    path = Path(csv_path) if csv_path else DEFAULT_UNREAL_SPAWN_CSV
    if not path.exists():
        return tuple()
    return tuple(_read_csv_rows(path))


def lookup_unreal_spawn_row(
    vertiport_name: str,
    *,
    category: str | None = None,
    preferred_label: str | None = None,
    spawn_point_id: str | None = None,
    csv_path: str | None = None,
) -> Optional[dict[str, str]]:
    names = set(_name_candidates(vertiport_name))
    if not names:
        return None
    category_key = str(category or "").strip().upper()
    rows = [
        row
        for row in load_unreal_spawn_rows(csv_path)
        if str(row.get("vertiport") or "").strip() in names
        and (not category_key or str(row.get("category") or "").strip().upper() == category_key)
    ]
    if not rows:
        return None

    for identifier in (spawn_point_id, preferred_label):
        if identifier:
            for row in rows:
                if _row_matches_identifier(row, str(identifier)):
                    return row
    return rows[0]


def _float_from(row: dict[str, str], keys: Iterable[str]) -> float | None:
    for key in keys:
        value = _as_float(row.get(key))
        if value is not None:
            return value
    return None


def row_to_unreal_spawn_point(row: dict[str, str]) -> dict[str, Any] | None:
    lat = _as_float(row.get("lla_lat_deg"))
    lon = _as_float(row.get("lla_lon_deg"))
    x_m = _as_float(row.get("airsim_x_m"))
    y_m = _as_float(row.get("airsim_y_m"))
    spawn_z_m = _as_float(row.get("airsim_spawn_z_m"))
    if lat is None or lon is None or x_m is None or y_m is None or spawn_z_m is None:
        return None

    route_ground_m = _float_from(row, ("route_ground_m", "deck_h_m", "resource_z_m")) or 0.0
    route_alt_m = _float_from(row, ("route_alt_m",)) or (route_ground_m + 10.0)
    terrain_h_m = _float_from(row, ("terrain_h_m", "resource_pt_h_m"))
    deck_h_m = _float_from(row, ("deck_h_m", "resource_z_m")) or 0.0
    yaw_deg = _as_float(row.get("yaw_deg"))
    label = str(row.get("label") or "").strip()
    s_id = str(row.get("s_id") or "").strip().upper()
    semantic_id = str(row.get("semantic_id") or "").strip().upper()
    vertiport = str(row.get("vertiport") or "").strip()

    point: dict[str, Any] = {
        "name": f"{vertiport} {label}".strip(),
        "lat": float(lat),
        "lon": float(lon),
        "alt_m": float(route_alt_m),
        "ground_m": float(route_ground_m),
        "terrain_h_m": float(terrain_h_m) if terrain_h_m is not None else None,
        "deck_height_m": float(deck_h_m),
        "fato_height_m": float(deck_h_m),
        "local_z_m": float(deck_h_m),
        "spawn_point_id": s_id or label,
        "spawn_label": label,
        "label": label,
        "semantic_id": semantic_id,
        "category": str(row.get("category") or "").strip().upper(),
        "airsim_x_m": float(x_m),
        "airsim_y_m": float(y_m),
        "airsim_spawn_z_m": float(spawn_z_m),
        # Backward compatibility for callers that only know airsim_z_m.
        "airsim_z_m": float(spawn_z_m),
        "airsim_editor_z_m": _as_float(row.get("airsim_editor_z_m")),
        "airsim_spawn_z_before_bias_m": _as_float(row.get("airsim_spawn_z_before_bias_m")),
        "airsim_spawn_z_bias_m": _as_float(row.get("airsim_spawn_z_bias_m")),
        "source": row.get("source") or "unreal_vertiport_spawn_points.csv",
    }
    if yaw_deg is not None:
        point["yaw_deg"] = float(yaw_deg) % 360.0
    return point


def lookup_unreal_spawn_point(
    vertiport_name: str,
    *,
    category: str | None = None,
    preferred_label: str | None = None,
    spawn_point_id: str | None = None,
    csv_path: str | None = None,
) -> Optional[dict[str, Any]]:
    row = lookup_unreal_spawn_row(
        vertiport_name,
        category=category,
        preferred_label=preferred_label,
        spawn_point_id=spawn_point_id,
        csv_path=csv_path,
    )
    if row is None:
        return None
    return row_to_unreal_spawn_point(row)
