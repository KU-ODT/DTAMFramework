import unreal, json, csv, os, re, time, math, traceback
from pathlib import Path

OUT_DIR = Path(r"D:\DTAMFramework\output\unreal_editor_dump")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAP_PATHS = ["/Game/FlyingCPP/Maps/FlyingExampleMap", "/Game/AutomotiveMaterials/Maps/Overview"]

def vec_dict(v):
    return {"x": float(v.x), "y": float(v.y), "z": float(v.z)}

def rot_dict(r):
    return {"pitch": float(r.pitch), "yaw": float(r.yaw), "roll": float(r.roll)}

def try_prop(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return None

def get_text(comp):
    for attr in ["text", "Text"]:
        try:
            t = comp.get_editor_property(attr)
            return str(t)
        except Exception:
            pass
    try:
        # TextRenderComponent has get_text in some versions
        return str(comp.get_text())
    except Exception:
        return ""

def get_class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        try:
            return obj.get_class().get_name()
        except Exception:
            return type(obj).__name__

def tick(seconds=5.0, step=0.1):
    # Let editor post-map-open tickers / construction logic run.
    count = int(seconds / step)
    for _ in range(max(1,count)):
        try:
            unreal.EditorAssetLibrary.save_loaded_assets([])  # harmless pump attempt, may no-op
        except Exception:
            pass
        try:
            unreal.SystemLibrary.delay(None, step)
        except Exception:
            pass

all_rows=[]
all_actors=[]
for map_path in MAP_PATHS:
    try:
        unreal.EditorLevelLibrary.load_level(map_path)
    except Exception:
        try:
            unreal.LevelEditorSubsystem().load_level(map_path)
        except Exception as e:
            print("MAP_LOAD_FAILED", map_path, e)
            continue
    # force redraw / wait a bit
    try:
        unreal.EditorLevelLibrary.editor_invalidate_viewports()
    except Exception:
        pass
    # maybe run several ticks so DTAM bootstrap spawns managed actors/previews
    for i in range(30):
        try:
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass
        time.sleep(0.2)
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
    except Exception:
        actors = unreal.EditorActorSubsystem().get_all_level_actors()
    print("MAP", map_path, "ACTORS", len(actors))
    for a in actors:
        try:
            label = a.get_actor_label()
        except Exception:
            label = a.get_name()
        cls = get_class_path(a)
        loc = a.get_actor_location()
        rot = a.get_actor_rotation()
        scl = a.get_actor_scale3d()
        tags=[]
        try:
            tags=[str(t) for t in a.tags]
        except Exception:
            pass
        record={
            "map": map_path,
            "actor_name": a.get_name(),
            "actor_label": label,
            "class": cls,
            "location_cm": vec_dict(loc),
            "rotation_deg": rot_dict(rot),
            "scale": vec_dict(scl),
            "tags": tags,
            "properties": {},
            "components": []
        }
        for pn in ["VertiportName","GroundMapTemplateId","AngleDegrees","Longitude","Latitude","HeightMeters","Ux","Uy","Uz"]:
            val=try_prop(a,pn)
            if val is not None:
                try:
                    record["properties"][pn]=float(val) if isinstance(val,(int,float)) else str(val)
                except Exception:
                    record["properties"][pn]=str(val)
        try:
            comps = a.get_components_by_class(unreal.ActorComponent)
        except Exception:
            comps = []
        for c in comps:
            cname = c.get_name()
            ccls = get_class_path(c)
            cd={"name":cname,"class":ccls}
            try: cd["world_location_cm"] = vec_dict(c.get_component_location())
            except Exception: pass
            try: cd["relative_location_cm"] = vec_dict(c.get_relative_location())
            except Exception: pass
            try: cd["world_rotation_deg"] = rot_dict(c.get_component_rotation())
            except Exception: pass
            try: cd["relative_rotation_deg"] = rot_dict(c.get_relative_rotation())
            except Exception: pass
            if "TextRender" in ccls or "Text" in cname:
                cd["text"] = get_text(c)
            record["components"].append(cd)
        all_actors.append(record)
        # rows for all components likely relevant
        relevant_actor = ("Vertiport" in label or "DTAMVisualization" in label or "Vertiport" in cls or "FlightCorridor" in cls or "DTAMVisualizationVertiport" in tags)
        if relevant_actor:
            for c in record["components"]:
                if c["name"].startswith("GroundNodeMarker_") or c["name"].startswith("GroundNodeLabel_") or c["name"] in ("PreviewLabel","CesiumGlobeAnchor"):
                    all_rows.append({
                        "map": map_path,
                        "actor_label": label,
                        "actor_name": record["actor_name"],
                        "actor_class": cls,
                        "vertiport_name_prop": record["properties"].get("VertiportName",""),
                        "component_name": c.get("name",""),
                        "component_class": c.get("class",""),
                        "component_text": c.get("text",""),
                        "actor_x_cm": record["location_cm"]["x"],
                        "actor_y_cm": record["location_cm"]["y"],
                        "actor_z_cm": record["location_cm"]["z"],
                        "actor_pitch_deg": record["rotation_deg"]["pitch"],
                        "actor_yaw_deg": record["rotation_deg"]["yaw"],
                        "actor_roll_deg": record["rotation_deg"]["roll"],
                        "component_world_x_cm": c.get("world_location_cm",{}).get("x",""),
                        "component_world_y_cm": c.get("world_location_cm",{}).get("y",""),
                        "component_world_z_cm": c.get("world_location_cm",{}).get("z",""),
                        "component_rel_x_cm": c.get("relative_location_cm",{}).get("x",""),
                        "component_rel_y_cm": c.get("relative_location_cm",{}).get("y",""),
                        "component_rel_z_cm": c.get("relative_location_cm",{}).get("z",""),
                        "prop_latitude": record["properties"].get("Latitude",""),
                        "prop_longitude": record["properties"].get("Longitude",""),
                        "prop_height_m": record["properties"].get("HeightMeters",""),
                        "prop_angle_deg": record["properties"].get("AngleDegrees","")
                    })

(OUT_DIR/"unreal_editor_all_actors.json").write_text(json.dumps(all_actors, ensure_ascii=False, indent=2), encoding="utf-8")
cols=list(all_rows[0].keys()) if all_rows else []
with (OUT_DIR/"unreal_editor_relevant_components.csv").open("w", newline="", encoding="utf-8-sig") as f:
    if cols:
        w=csv.DictWriter(f, fieldnames=cols)
        w.writeheader(); w.writerows(all_rows)
print("WROTE", OUT_DIR, "relevant rows", len(all_rows), "actors", len(all_actors))
