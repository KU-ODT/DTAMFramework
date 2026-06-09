# -*- coding: utf-8 -*-
"""Build calibrated Unreal/AirSim spawn-point mapping for all vertiports.

Inputs
------
* docs/unreal_editor_s_points.csv
    Authoritative Unreal Editor preview-marker world coordinates
    (GroundNodeMarker_* component locations).
* MissionModule/data/resources_vp.csv
    Terrain/deck-height reference used only for vertical spawn calibration.

Output
------
The generated CSV is the runtime source for Operation/Mission modules when they
need Gate/FATO Unreal coordinates.  X/Y are taken from the editor marker
coordinates; Z is an AirSim settings NED-down value calibrated by the measured
Jamsil deck bias.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EDITOR_S_POINTS_CSV = ROOT / "docs" / "unreal_editor_s_points.csv"
RESOURCE_VP_CSV = ROOT / "MissionModule" / "data" / "resources_vp.csv"

PRIMARY_OUT = ROOT / "MissionModule" / "data" / "unreal_vertiport_spawn_points.csv"
DOCS_OUT = ROOT / "docs" / "unreal_vertiport_spawn_points_calibrated.csv"
DOCS_MD_OUT = ROOT / "docs" / "unreal_vertiport_spawn_points_calibrated.md"
VIS_OUT = ROOT / "VisualizationModule" / "data" / "coordinateDB" / "unreal_vertiport_spawn_points.csv"
RUNTIME_VIS_OUT = (
    ROOT
    / "VisualizationModule"
    / "runtime"
    / "Unreal"
    / "Environments"
    / "DTAMVisualization"
    / "Data"
    / "coordinateDB"
    / "unreal_vertiport_spawn_points.csv"
)
META_OUT = ROOT / "docs" / "unreal_vertiport_spawn_points_calibrated.meta.json"


CESIUM_ORIGIN_HEIGHT_M = 350.0
AIRSIM_FATO_SPAWN_CLEARANCE_M = 1.0
JAMSIL_TARGET_SPAWN_Z_M = 294.4

# User-confirmed Jamsil ground/deck empirical calibration.
# This is recomputed from resources_vp.csv during generation, but kept here as
# documentation of the intended basis.
CALIBRATION_VERTIPORT = "\uc7a0\uc2e4"  # Jamsil


SPAWN_LABELS: list[dict[str, str]] = [
    {"label": "GATE 1", "semantic_id": "G1", "s_id": "S16", "category": "GATE", "yaw_policy": "angle_minus_90"},
    {"label": "GATE 2", "semantic_id": "G2", "s_id": "S15", "category": "GATE", "yaw_policy": "angle_minus_90"},
    {"label": "GATE 3", "semantic_id": "G3", "s_id": "S14", "category": "GATE", "yaw_policy": "angle_minus_90"},
    {"label": "GATE 4", "semantic_id": "G4", "s_id": "S13", "category": "GATE", "yaw_policy": "angle_minus_90"},
    {"label": "GATE 5", "semantic_id": "G5", "s_id": "S04", "category": "GATE", "yaw_policy": "angle_plus_90"},
    {"label": "GATE 6", "semantic_id": "G6", "s_id": "S03", "category": "GATE", "yaw_policy": "angle_plus_90"},
    {"label": "GATE 7", "semantic_id": "G7", "s_id": "S02", "category": "GATE", "yaw_policy": "angle_plus_90"},
    {"label": "GATE 8", "semantic_id": "G8", "s_id": "S01", "category": "GATE", "yaw_policy": "angle_plus_90"},
    {"label": "FATO 1", "semantic_id": "F1", "s_id": "S26", "category": "FATO", "yaw_policy": "angle"},
    {"label": "FATO 2", "semantic_id": "F2", "s_id": "S25", "category": "FATO", "yaw_policy": "angle"},
]


FIELDNAMES = [
    "vertiport",
    "vertiport_class",
    "vertiport_lat_deg",
    "vertiport_lon_deg",
    "vertiport_angle_deg",
    "category",
    "label",
    "semantic_id",
    "s_id",
    "node_id",
    "node_type",
    "marker_x_cm",
    "marker_y_cm",
    "marker_z_cm",
    "airsim_x_m",
    "airsim_y_m",
    "airsim_editor_z_m",
    "airsim_spawn_z_m",
    "airsim_spawn_z_before_bias_m",
    "airsim_spawn_z_bias_m",
    "airsim_spawn_z_policy",
    "yaw_deg",
    "lla_lat_deg",
    "lla_lon_deg",
    "lla_height_m",
    "terrain_h_m",
    "deck_h_m",
    "surface_h_m",
    "route_ground_m",
    "route_alt_m",
    "resource_x_m",
    "resource_y_m",
    "resource_z_m",
    "resource_lat_deg",
    "resource_lon_deg",
    "resource_pt_h_m",
    "trace_status",
    "source",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Could not decode CSV: {path}")


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(value: Any, digits: int = 6) -> str:
    number = _float(value)
    if number is None:
        return ""
    return f"{number:.{digits}f}"


def _surface_spawn_z_before_bias(resource: dict[str, str]) -> float | None:
    terrain_h = _float(resource.get("pt_h_m"))
    deck_h = _float(resource.get("Z_m"))
    if terrain_h is None:
        return None
    return CESIUM_ORIGIN_HEIGHT_M - (terrain_h + float(deck_h or 0.0)) - AIRSIM_FATO_SPAWN_CLEARANCE_M


def _calibration_bias_m(resources: dict[tuple[str, str], dict[str, str]]) -> float:
    labels = {item["label"] for item in SPAWN_LABELS}
    values: list[float] = []
    for label in labels:
        resource = resources.get((CALIBRATION_VERTIPORT, label))
        if not resource:
            continue
        before = _surface_spawn_z_before_bias(resource)
        if before is not None:
            values.append(before)
    if not values:
        raise RuntimeError("No calibration rows found for Jamsil.")
    mean_before = sum(values) / len(values)
    return JAMSIL_TARGET_SPAWN_Z_M - mean_before


def _yaw(angle_deg: float, policy: str) -> float:
    if policy == "angle_minus_90":
        return (angle_deg - 90.0) % 360.0
    if policy == "angle_plus_90":
        return (angle_deg + 90.0) % 360.0
    return angle_deg % 360.0


def build_rows() -> tuple[list[dict[str, str]], dict[str, Any]]:
    editor_rows = _read_csv(EDITOR_S_POINTS_CSV)
    resource_rows = _read_csv(RESOURCE_VP_CSV)
    resources = {
        (str(row.get("Vertiport") or "").strip(), str(row.get("Label") or "").strip().upper()): row
        for row in resource_rows
        if row.get("Vertiport") and row.get("Label")
    }
    bias_m = _calibration_bias_m(resources)

    editor_by_port_s_id = {
        (str(row.get("vertiport") or "").strip(), str(row.get("s_id") or "").strip().upper()): row
        for row in editor_rows
        if row.get("vertiport") and row.get("s_id")
    }
    vertiports: list[str] = []
    for row in editor_rows:
        name = str(row.get("vertiport") or "").strip()
        if name and name not in vertiports:
            vertiports.append(name)

    output_rows: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    for vertiport in vertiports:
        for item in SPAWN_LABELS:
            label = item["label"]
            s_id = item["s_id"]
            editor = editor_by_port_s_id.get((vertiport, s_id))
            resource = resources.get((vertiport, label))
            if editor is None or resource is None:
                missing.append({"vertiport": vertiport, "label": label, "s_id": s_id})
                continue

            angle_deg = float(_float(editor.get("vertiport_angle_deg"), 0.0) or 0.0)
            before_bias = _surface_spawn_z_before_bias(resource)
            spawn_z = (before_bias + bias_m) if before_bias is not None else None
            terrain_h = _float(resource.get("pt_h_m"))
            deck_h = _float(resource.get("Z_m"), 0.0)
            surface_h = (terrain_h + float(deck_h or 0.0)) if terrain_h is not None else None
            route_ground_m = float(deck_h or 0.0)
            route_alt_m = route_ground_m + 10.0
            yaw_deg = _yaw(angle_deg, item["yaw_policy"])

            row = {
                "vertiport": vertiport,
                "vertiport_class": editor.get("vertiport_class", ""),
                "vertiport_lat_deg": _fmt(editor.get("vertiport_lat_deg"), 12),
                "vertiport_lon_deg": _fmt(editor.get("vertiport_lon_deg"), 12),
                "vertiport_angle_deg": _fmt(angle_deg, 6),
                "category": item["category"],
                "label": label,
                "semantic_id": item["semantic_id"],
                "s_id": s_id,
                "node_id": str(editor.get("node_id") or ""),
                "node_type": str(editor.get("node_type") or ""),
                "marker_x_cm": _fmt(editor.get("marker_x_cm"), 6),
                "marker_y_cm": _fmt(editor.get("marker_y_cm"), 6),
                "marker_z_cm": _fmt(editor.get("marker_z_cm"), 6),
                "airsim_x_m": _fmt(editor.get("airsim_x_m"), 6),
                "airsim_y_m": _fmt(editor.get("airsim_y_m"), 6),
                "airsim_editor_z_m": _fmt(editor.get("airsim_z_m"), 6),
                "airsim_spawn_z_m": _fmt(spawn_z, 6),
                "airsim_spawn_z_before_bias_m": _fmt(before_bias, 6),
                "airsim_spawn_z_bias_m": _fmt(bias_m, 6),
                "airsim_spawn_z_policy": (
                    "settings_NED_down = cesium_origin_height_m - (resource_pt_h_m + resource_Z_m) "
                    "- spawn_clearance_m + jamsil_empirical_bias_m"
                ),
                "yaw_deg": _fmt(yaw_deg, 6),
                "lla_lat_deg": _fmt(editor.get("lla_lat_deg"), 12),
                "lla_lon_deg": _fmt(editor.get("lla_lon_deg"), 12),
                "lla_height_m": _fmt(editor.get("lla_height_m"), 6),
                "terrain_h_m": _fmt(terrain_h, 6),
                "deck_h_m": _fmt(deck_h, 6),
                "surface_h_m": _fmt(surface_h, 6),
                "route_ground_m": _fmt(route_ground_m, 6),
                "route_alt_m": _fmt(route_alt_m, 6),
                "resource_x_m": _fmt(resource.get("X_m"), 6),
                "resource_y_m": _fmt(resource.get("Y_m"), 6),
                "resource_z_m": _fmt(resource.get("Z_m"), 6),
                "resource_lat_deg": _fmt(resource.get("pt_lat_deg"), 12),
                "resource_lon_deg": _fmt(resource.get("pt_lon_deg"), 12),
                "resource_pt_h_m": _fmt(resource.get("pt_h_m"), 6),
                "trace_status": str(editor.get("trace_status") or ""),
                "source": "editor_preview_marker_xy + resources_vp_surface_height + jamsil_z_bias",
            }
            output_rows.append(row)

    meta = {
        "rows": len(output_rows),
        "vertiport_count": len(vertiports),
        "points_per_vertiport": len(SPAWN_LABELS),
        "calibration_vertiport": CALIBRATION_VERTIPORT,
        "jamsil_target_spawn_z_m": JAMSIL_TARGET_SPAWN_Z_M,
        "airsim_spawn_z_bias_m": bias_m,
        "cesium_origin_height_m": CESIUM_ORIGIN_HEIGHT_M,
        "spawn_clearance_m": AIRSIM_FATO_SPAWN_CLEARANCE_M,
        "missing": missing,
        "inputs": [str(EDITOR_S_POINTS_CSV), str(RESOURCE_VP_CSV)],
        "outputs": [str(PRIMARY_OUT), str(DOCS_OUT), str(VIS_OUT), str(RUNTIME_VIS_OUT)],
    }
    return output_rows, meta


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, rows: list[dict[str, str]], meta: dict[str, Any]) -> None:
    samples = [row for row in rows if row["vertiport"] == CALIBRATION_VERTIPORT]
    sample_lines = []
    for row in samples[:10]:
        sample_lines.append(
            f"| {row['semantic_id']} | {row['label']} | {row['s_id']} | "
            f"{row['airsim_x_m']} | {row['airsim_y_m']} | {row['airsim_spawn_z_m']} | {row['yaw_deg']} |"
        )
    sample_table = "\n".join(sample_lines)
    path.write_text(
        "\n".join(
            [
                "# Unreal vertiport Gate/FATO calibrated spawn points",
                "",
                "This table is generated from the actual Unreal Editor preview marker coordinates.",
                "",
                "## Calibration",
                "",
                f"- Calibration vertiport: `{CALIBRATION_VERTIPORT}`",
                f"- Target AirSim settings Z at calibration deck: `{JAMSIL_TARGET_SPAWN_Z_M:.3f}` m",
                f"- Applied global Z bias: `{float(meta['airsim_spawn_z_bias_m']):.6f}` m",
                f"- Formula: `Z = {CESIUM_ORIGIN_HEIGHT_M:.1f} - (terrain_h_m + deck_h_m) - {AIRSIM_FATO_SPAWN_CLEARANCE_M:.1f} + bias`",
                "",
                "## Mapping",
                "",
                "- `FATO 1` = `F1` = `S26`",
                "- `FATO 2` = `F2` = `S25`",
                "- `GATE 1..4` = `G1..G4` = `S16..S13`",
                "- `GATE 5..8` = `G5..G8` = `S04..S01`",
                "",
                "## Jamsil sample",
                "",
                "| point | label | S-id | X(m) | Y(m) | settings Z(m) | yaw(deg) |",
                "|---|---|---:|---:|---:|---:|---:|",
                sample_table,
                "",
                "## Files",
                "",
                f"- Primary runtime CSV: `{PRIMARY_OUT}`",
                f"- Docs CSV: `{DOCS_OUT}`",
                f"- Visualization copy: `{VIS_OUT}`",
                f"- Unreal runtime copy: `{RUNTIME_VIS_OUT}`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    rows, meta = build_rows()
    if meta["missing"]:
        raise RuntimeError(f"Missing spawn mappings: {meta['missing']}")
    for path in (PRIMARY_OUT, DOCS_OUT, VIS_OUT, RUNTIME_VIS_OUT):
        _write_csv(path, rows)
    META_OUT.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(DOCS_MD_OUT, rows, meta)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
