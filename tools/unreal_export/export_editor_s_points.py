# -*- coding: utf-8 -*-
"""
Export S01~S29 ground-node coordinates by instantiating the real
ADTAMVisualizationVertiportPreviewActor in the Unreal editor runtime and reading
its GroundNodeMarker_* / GroundNodeLabel_* components.

This intentionally does NOT read MissionModule/resources_vp.csv as the source of
point coordinates. The source of the exported U coordinates is the component
world transform after the preview actor builds the same markers visible in the
editor viewport.
"""
import csv
import datetime as _dt
import json
import os
import pathlib
import re
import traceback

import unreal

ROOT = pathlib.Path(r"D:\DTAMFramework")
PROJECT_DIR = ROOT / "VisualizationModule_Source" / "Unreal" / "Environments" / "DTAMVisualization"
DATA_DIR = PROJECT_DIR / "Data" / "coordinateDB"
DOCS_DIR = ROOT / "docs"
OUT_DIR = ROOT / "output" / "unreal_editor_dump"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAP_PATH = "/Game/FlyingCPP/Maps/FlyingExampleMap"
VERTIPORT_CSV = DATA_DIR / "vertiport_UE.csv"
GROUND_MAP_CSV = DATA_DIR / "vertiportMap_KU.csv"
MESH_PATH = "/Game/vp_model/Vertiport_round_KU.Vertiport_round_KU"
PREVIEW_CLASS_NAME = "DTAMVisualizationVertiportPreviewActor"
FALLBACK_HEIGHT_M = 60.0
SURFACE_LIFT_CM = 8.0
TRACE_ABOVE_CM = 150000.0
TRACE_BELOW_CM = 300000.0

CSV_OUT = DOCS_DIR / "unreal_editor_s_points.csv"
# User previously referenced this path; overwrite it with the corrected editor-preview export.
LEGACY_NAMED_CSV_OUT = DOCS_DIR / "unreal_vertiport_resource_points.csv"
JSON_OUT = OUT_DIR / "unreal_editor_s_points.json"
META_OUT = DOCS_DIR / "unreal_editor_s_points_meta.json"
MD_OUT = DOCS_DIR / "unreal_editor_s_points.md"


def fnum(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def vec3(v):
    return [float(v.x), float(v.y), float(v.z)]


def read_csv_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def get_text(component):
    try:
        return str(component.get_editor_property("text"))
    except Exception:
        return ""


def parse_label_u(text):
    m = re.search(r"U\s*([+-]?\d+(?:\.\d+)?)\s*/\s*([+-]?\d+(?:\.\d+)?)\s*/\s*([+-]?\d+(?:\.\d+)?)", text or "")
    if not m:
        return None
    return [float(m.group(1)), float(m.group(2)), float(m.group(3))]


def try_line_trace(context_actor, start, end):
    """Best effort mirror of C++ line trace. In commandlet/no Cesium tiles this usually returns no hit."""
    results = []
    # Python Kismet line trace exposes project TraceTypeQuery entries, not raw ECC_*.
    # Query1/Query2 are both attempted and recorded only for diagnostics; actor position
    # is updated only if we get a hit result object with impact_point.
    for name, trace_channel in [
        ("TraceTypeQuery1", unreal.TraceTypeQuery.TRACE_TYPE_QUERY1),
        ("TraceTypeQuery2", unreal.TraceTypeQuery.TRACE_TYPE_QUERY2),
    ]:
        try:
            r = unreal.SystemLibrary.line_trace_single(
                context_actor,
                start,
                end,
                trace_channel,
                False,
                [],
                unreal.DrawDebugTrace.NONE,
                False,
                unreal.LinearColor(1.0, 0.0, 0.0, 1.0),
                unreal.LinearColor(0.0, 1.0, 0.0, 1.0),
                0.0,
            )
            if hasattr(r, "impact_point"):
                results.append({"channel": name, "hit": True, "impact_point": vec3(r.impact_point), "raw": str(r)})
                return r, results
            results.append({"channel": name, "hit": False, "raw": str(r)})
        except Exception as exc:
            results.append({"channel": name, "hit": False, "error": repr(exc)})
    return None, results


def main():
    started = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    # Load the same editor map that contains CesiumGeoreferenceDefault and where preview actors are spawned.
    unreal.EditorLevelLibrary.load_level(MAP_PATH)

    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    georef = None
    for actor in actors:
        if "CesiumGeoreference" in actor.get_class().get_name():
            georef = actor
            break
    if georef is None:
        georef = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.CesiumGeoreference, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0)
        )
        georef.set_actor_label("CesiumGeoreferenceDefault_export_temp")
        georef.set_origin_longitude_latitude_height(unreal.Vector(126.978, 37.5665, 350.0))

    origin_llh = georef.get_origin_longitude_latitude_height()
    georef_scale = None
    try:
        georef_scale = float(georef.get_editor_property("scale"))
    except Exception:
        georef_scale = None

    vertiports = read_csv_rows(VERTIPORT_CSV)
    ground_nodes = [row for row in read_csv_rows(GROUND_MAP_CSV) if row.get("template_id", "").strip().upper() == "KU"]

    preview_cls = getattr(unreal, PREVIEW_CLASS_NAME)
    mesh = unreal.EditorAssetLibrary.load_asset(MESH_PATH)
    rows = []
    actor_summaries = []
    errors = []
    temp_actors = []

    for vp_index, vp in enumerate(vertiports, start=1):
        name = (vp.get("Name") or "").strip()
        cls = (vp.get("Class") or "").strip()
        lat = fnum(vp.get("Latitude"))
        lon = fnum(vp.get("Longitude"))
        angle = fnum(vp.get("AngleDegrees"))
        try:
            # Match C++: GlobeAnchor->MoveToLongitudeLatitudeHeight(lon, lat, 60m)
            actor_loc = georef.transform_longitude_latitude_height_position_to_unreal(
                unreal.Vector(lon, lat, FALLBACK_HEIGHT_M)
            )
            # Match C++ FRotator(0, AngleDegrees, 0). In UE Python the constructor order
            # is Roll, Pitch, Yaw, so use explicit yaw via third arg.
            esu_rot = unreal.Rotator(0.0, 0.0, angle)
            actor_rot = georef.transform_east_south_up_rotator_to_unreal(esu_rot, actor_loc)

            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(preview_cls, actor_loc, actor_rot)
            temp_actors.append(actor)
            actor.set_actor_label("EXPORT_PREVIEW_VERTIPORT_%02d_%s" % (vp_index, name))
            try:
                actor.set_editor_property("VertiportName", name)
                actor.set_editor_property("GroundMapTemplateId", "KU")
            except Exception:
                pass
            try:
                smc = actor.get_component_by_class(unreal.StaticMeshComponent)
                if smc and mesh:
                    smc.set_static_mesh(mesh)
            except Exception as exc:
                errors.append({"vertiport": name, "stage": "set_mesh", "error": repr(exc)})

            # Try to mirror the C++ surface trace. In this commandlet run, Cesium ion terrain
            # is unavailable, so most/all rows remain fallback. The status is recorded.
            trace_status = "NO_HIT_COMMANDLET_FALLBACK_H60"
            trace_debug = []
            try:
                up = actor.get_actor_up_vector()
                world_loc_before_trace = actor.get_actor_location()
                start = world_loc_before_trace + up * TRACE_ABOVE_CM
                end = world_loc_before_trace - up * TRACE_BELOW_CM
                hit, trace_debug = try_line_trace(actor, start, end)
                if hit is not None and hasattr(hit, "impact_point"):
                    actor.set_actor_location(hit.impact_point + up * SURFACE_LIFT_CM, False, True)
                    trace_status = "HIT_UPDATED_BY_PY_TRACE_PLUS_8CM"
            except Exception as exc:
                trace_status = "TRACE_ERROR_FALLBACK_H60"
                trace_debug.append({"error": repr(exc)})

            # The actual preview actor constructs GroundNodeMarker/Label during OnConstruction.
            # After any transform adjustment, refresh metadata if the public method is exposed.
            try:
                if hasattr(actor, "refresh_preview_metadata"):
                    actor.refresh_preview_metadata()
            except Exception as exc:
                errors.append({"vertiport": name, "stage": "refresh_preview_metadata", "error": repr(exc)})

            actor_actual_loc = actor.get_actor_location()
            actor_actual_rot = actor.get_actor_rotation()
            try:
                actor_actual_llh = georef.transform_unreal_position_to_longitude_latitude_height(actor_actual_loc)
            except Exception:
                actor_actual_llh = unreal.Vector(lon, lat, FALLBACK_HEIGHT_M)

            markers = {}
            labels = {}
            for comp in actor.get_components_by_class(unreal.ActorComponent):
                comp_name = comp.get_name()
                if comp_name.startswith("GroundNodeMarker_"):
                    try:
                        idx = int(comp_name.rsplit("_", 1)[1])
                    except Exception:
                        continue
                    markers[idx] = comp
                elif comp_name.startswith("GroundNodeLabel_"):
                    try:
                        idx = int(comp_name.rsplit("_", 1)[1])
                    except Exception:
                        continue
                    labels[idx] = comp

            actor_summaries.append({
                "vertiport": name,
                "class": cls,
                "lat": lat,
                "lon": lon,
                "angle_deg": angle,
                "actor_location_cm": vec3(actor_actual_loc),
                "actor_rotation_deg": [float(actor_actual_rot.pitch), float(actor_actual_rot.yaw), float(actor_actual_rot.roll)],
                "actor_llh": [float(actor_actual_llh.x), float(actor_actual_llh.y), float(actor_actual_llh.z)],
                "trace_status": trace_status,
                "trace_debug": trace_debug,
                "marker_count": len(markers),
                "label_count": len(labels),
            })

            for idx, node in enumerate(ground_nodes):
                marker = markers.get(idx)
                label = labels.get(idx)
                if marker is None:
                    errors.append({"vertiport": name, "stage": "missing_marker", "index": idx})
                    continue
                node_id = (node.get("node_id") or str(idx + 1)).strip()
                try:
                    node_num = int(node_id)
                except Exception:
                    node_num = idx + 1
                s_id = "S%02d" % node_num
                semantic_id = (node.get("semantic_id") or "").strip()
                node_type = (node.get("node_type") or "").strip()
                display_id = s_id + (" " + semantic_id if semantic_id else "")
                label_text = get_text(label) if label else ""
                label_u = parse_label_u(label_text)
                marker_world = marker.get_world_location()
                try:
                    marker_llh = georef.transform_unreal_position_to_longitude_latitude_height(marker_world)
                except Exception:
                    marker_llh = unreal.Vector(0, 0, 0)
                rows.append({
                    "vertiport": name,
                    "vertiport_class": cls,
                    "vertiport_lat_deg": "%.12f" % lat,
                    "vertiport_lon_deg": "%.12f" % lon,
                    "vertiport_angle_deg": "%.6f" % angle,
                    "s_id": s_id,
                    "node_id": node_id,
                    "semantic_id": semantic_id,
                    "display_id": display_id,
                    "node_type": node_type,
                    "source_layout_marker": (node.get("source_layout_marker") or "").strip(),
                    "local_x_cm": "%.6f" % fnum(node.get("local_x_cm")),
                    "local_y_cm": "%.6f" % fnum(node.get("local_y_cm")),
                    "local_z_cm": "%.6f" % fnum(node.get("local_z_cm")),
                    "actor_x_cm": "%.6f" % float(actor_actual_loc.x),
                    "actor_y_cm": "%.6f" % float(actor_actual_loc.y),
                    "actor_z_cm": "%.6f" % float(actor_actual_loc.z),
                    "marker_x_cm": "%.6f" % float(marker_world.x),
                    "marker_y_cm": "%.6f" % float(marker_world.y),
                    "marker_z_cm": "%.6f" % float(marker_world.z),
                    "label_u_x_cm": "" if label_u is None else "%.0f" % label_u[0],
                    "label_u_y_cm": "" if label_u is None else "%.0f" % label_u[1],
                    "label_u_z_cm": "" if label_u is None else "%.0f" % label_u[2],
                    "airsim_x_m": "%.6f" % (float(marker_world.x) / 100.0),
                    "airsim_y_m": "%.6f" % (float(marker_world.y) / 100.0),
                    "airsim_z_m": "%.6f" % (float(marker_world.z) / 100.0),
                    "lla_lon_deg": "%.12f" % float(marker_llh.x),
                    "lla_lat_deg": "%.12f" % float(marker_llh.y),
                    "lla_height_m": "%.6f" % float(marker_llh.z),
                    "unreal_label_text": label_text.replace("\r", "").replace("\n", " | "),
                    "source_component_marker": "GroundNodeMarker_%d" % idx,
                    "source_component_label": "GroundNodeLabel_%d" % idx,
                    "trace_status": trace_status,
                    "extraction_source": "UnrealEditor spawned ADTAMVisualizationVertiportPreviewActor -> GroundNodeMarker.get_world_location()",
                })
        except Exception as exc:
            errors.append({"vertiport": name, "stage": "vertiport_export", "error": repr(exc), "traceback": traceback.format_exc()})

    # Clean temporary preview actors so commandlet does not dirty/save the map.
    for actor in temp_actors:
        try:
            unreal.EditorLevelLibrary.destroy_actor(actor)
        except Exception:
            pass

    fieldnames = [
        "vertiport", "vertiport_class", "vertiport_lat_deg", "vertiport_lon_deg", "vertiport_angle_deg",
        "s_id", "node_id", "semantic_id", "display_id", "node_type", "source_layout_marker",
        "local_x_cm", "local_y_cm", "local_z_cm",
        "actor_x_cm", "actor_y_cm", "actor_z_cm",
        "marker_x_cm", "marker_y_cm", "marker_z_cm",
        "label_u_x_cm", "label_u_y_cm", "label_u_z_cm",
        "airsim_x_m", "airsim_y_m", "airsim_z_m",
        "lla_lon_deg", "lla_lat_deg", "lla_height_m",
        "unreal_label_text", "source_component_marker", "source_component_label",
        "trace_status", "extraction_source",
    ]
    for out_path in [CSV_OUT, LEGACY_NAMED_CSV_OUT]:
        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    payload = {
        "generated_at": started,
        "project_dir": str(PROJECT_DIR),
        "map_path": MAP_PATH,
        "vertiport_csv": str(VERTIPORT_CSV),
        "ground_map_csv": str(GROUND_MAP_CSV),
        "mesh_path": MESH_PATH,
        "georeference_origin_llh": {"lon": float(origin_llh.x), "lat": float(origin_llh.y), "height_m": float(origin_llh.z)},
        "georeference_scale": georef_scale,
        "fallback_height_m": FALLBACK_HEIGHT_M,
        "surface_lift_cm": SURFACE_LIFT_CM,
        "row_count": len(rows),
        "vertiport_count": len(vertiports),
        "ground_node_count": len(ground_nodes),
        "actor_summaries": actor_summaries,
        "errors": errors,
        "outputs": {"csv": str(CSV_OUT), "legacy_named_csv": str(LEGACY_NAMED_CSV_OUT), "json": str(JSON_OUT), "meta": str(META_OUT), "md": str(MD_OUT)},
        "notes": [
            "Coordinates are read from Unreal component world locations, not MissionModule/resources_vp.csv.",
            "The marker labels visible in the editor are produced by DTAMVisualizationVertiportPreviewActor::UpdateGroundMapPreview.",
            "Commandlet run records trace_status per row; if NO_HIT_COMMANDLET_FALLBACK_H60, terrain/surface line trace was unavailable and actor remains at fallback LLH height 60 m.",
        ],
    }
    JSON_OUT.write_text(json.dumps({"meta": payload, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    META_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Build compact markdown document with Jamsil table and extraction method.
    jamsil = [r for r in rows if r["vertiport"] == "잠실"]
    ports = sorted({r["vertiport"] for r in rows})
    md_lines = []
    md_lines.append("# Unreal Editor Preview S-Point 좌표 추출")
    md_lines.append("")
    md_lines.append(f"- 생성시각: `{started}`")
    md_lines.append(f"- Unreal 프로젝트: `{PROJECT_DIR}`")
    md_lines.append(f"- 맵: `{MAP_PATH}`")
    md_lines.append(f"- 추출 row: `{len(rows)}` = 버티포트 `{len(vertiports)}`개 × S-point `{len(ground_nodes)}`개")
    md_lines.append(f"- CesiumGeoreference origin LLH: lon `{float(origin_llh.x):.6f}`, lat `{float(origin_llh.y):.6f}`, h `{float(origin_llh.z):.3f} m`, scale `{georef_scale}`")
    md_lines.append("")
    md_lines.append("## 정정 사항")
    md_lines.append("")
    md_lines.append("기존 `unreal_vertiport_resource_points.csv`는 Mission/coordinateDB 리소스 좌표를 섞어 만든 값이라, 에디터에서 보이는 `GroundNodeMarker_*`/`GroundNodeLabel_*` 좌표 그 자체가 아니었습니다. 이번 파일은 Unreal Python으로 실제 `ADTAMVisualizationVertiportPreviewActor`를 생성한 뒤, 에디터에 표시되는 점 컴포넌트의 `get_world_location()` 값을 읽어서 만들었습니다.")
    md_lines.append("")
    md_lines.append("## 사용한 Unreal 코드 경로")
    md_lines.append("")
    md_lines.append("- 버티포트 배치: `Source/DTAMVisualization/DTAMVisualizationFlightCorridorActor.cpp::SpawnVertiports`")
    md_lines.append("  - `vertiport_UE.csv`의 `Latitude/Longitude/AngleDegrees`를 사용")
    md_lines.append("  - `MoveToLongitudeLatitudeHeight(Longitude, Latitude, 60m)` 후 ESU yaw 회전 적용")
    md_lines.append("- S-point 생성/라벨: `Source/DTAMVisualization/DTAMVisualizationVertiportPreviewActor.cpp::UpdateGroundMapPreview`")
    md_lines.append("  - `vertiportMap_KU.csv`의 29개 `local_x/y/z_cm`로 `GroundNodeMarker_0~28` 생성")
    md_lines.append("  - 라벨의 `U +x / +y / +z`는 `GroundNodeMarker.GetComponentLocation()` 값")
    md_lines.append("")
    md_lines.append("## 산출물")
    md_lines.append("")
    md_lines.append(f"- CSV: `{CSV_OUT}`")
    md_lines.append(f"- 기존 경로 덮어쓴 CSV: `{LEGACY_NAMED_CSV_OUT}`")
    md_lines.append(f"- 원본 JSON: `{JSON_OUT}`")
    md_lines.append(f"- 메타: `{META_OUT}`")
    md_lines.append("")
    md_lines.append("## 주의: 고도/trace 상태")
    md_lines.append("")
    no_hit = sum(1 for r in rows if r["trace_status"].startswith("NO_HIT"))
    md_lines.append(f"이번 commandlet 추출에서는 `{no_hit}`개 row가 `NO_HIT_COMMANDLET_FALLBACK_H60` 상태입니다. 즉, 현재 배치/회전/S-point 컴포넌트 좌표는 Unreal Editor에서 직접 생성해 읽었지만, Cesium 지형 surface line trace가 commandlet 환경에서 맞지 않아 actor 기준 고도는 C++ 기본 fallback `60 m` 상태로 남아 있습니다. 라이브 에디터에서 Cesium 지형이 로드된 상태로 같은 스크립트를 실행하면 trace 반영 Z까지 다시 떨어집니다.")
    md_lines.append("")
    md_lines.append("## 잠실 S01~S29 추출값")
    md_lines.append("")
    md_lines.append("| S | semantic | type | marker_x_cm | marker_y_cm | marker_z_cm | LLA lat | LLA lon | h_m | label | trace |")
    md_lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---|---|")
    for r in jamsil:
        md_lines.append(
            f"| {r['s_id']} | {r['semantic_id']} | {r['node_type']} | {float(r['marker_x_cm']):.3f} | {float(r['marker_y_cm']):.3f} | {float(r['marker_z_cm']):.3f} | {float(r['lla_lat_deg']):.9f} | {float(r['lla_lon_deg']):.9f} | {float(r['lla_height_m']):.3f} | `{r['unreal_label_text']}` | {r['trace_status']} |"
        )
    md_lines.append("")
    md_lines.append("## 전체 버티포트 목록")
    md_lines.append("")
    md_lines.append(", ".join(ports))
    md_lines.append("")
    MD_OUT.write_text("\n".join(md_lines), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "row_count": len(rows),
        "vertiport_count": len(vertiports),
        "ground_node_count": len(ground_nodes),
        "csv": str(CSV_OUT),
        "legacy_named_csv": str(LEGACY_NAMED_CSV_OUT),
        "md": str(MD_OUT),
        "meta": str(META_OUT),
        "json": str(JSON_OUT),
        "errors": len(errors),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
