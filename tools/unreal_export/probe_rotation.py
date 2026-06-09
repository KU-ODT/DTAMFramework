import unreal, pathlib, json
out=pathlib.Path(r'D:\DTAMFramework\output\unreal_editor_dump\rotation_probe.json')
unreal.EditorLevelLibrary.load_level('/Game/FlyingCPP/Maps/FlyingExampleMap')
georef=None
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if 'CesiumGeoreference' in a.get_class().get_name(): georef=a
if not georef:
    georef=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CesiumGeoreference, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
georef.set_origin_longitude_latitude_height(unreal.Vector(126.978,37.5665,350.0))
res=[]
for args in [(unreal.Rotator(0,83,0),),(unreal.Vector(127.069068,37.514368,60),unreal.Rotator(0,83,0)),(unreal.Rotator(0,83,0),unreal.Vector(127.069068,37.514368,60))]:
    try:
        r=georef.transform_rotator_east_south_up_to_unreal(*args)
        res.append({'args':len(args),'out':[r.pitch,r.yaw,r.roll]})
    except Exception as e:
        res.append({'args':len(args),'err':repr(e)})
out.write_text(json.dumps(res,indent=2),encoding='utf-8')
print(json.dumps(res,indent=2))
