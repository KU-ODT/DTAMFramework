import unreal, pathlib, json
out=pathlib.Path(r'D:\DTAMFramework\output\unreal_editor_dump\georef_transform_probe.json')
unreal.EditorLevelLibrary.load_level('/Game/FlyingCPP/Maps/FlyingExampleMap')
actors=unreal.EditorLevelLibrary.get_all_level_actors()
georef=None
for a in actors:
    if a.get_actor_label()=='CesiumGeoreferenceDefault' or 'CesiumGeoreference' in a.get_class().get_name():
        georef=a
        break
if not georef:
    georef=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CesiumGeoreference, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
# set origin
try:
    georef.set_origin_longitude_latitude_height(unreal.Vector(126.978,37.5665,350.0))
except Exception as e:
    try: georef.set_georeference_origin_longitude_latitude_height(unreal.Vector(126.978,37.5665,350.0))
    except Exception as e2: print('set origin failed', e, e2)
points=[('jamsil_anchor',127.069068,37.514368,60.0),('jamsil_gate8',127.06929,37.51481713,33.6081235)]
res=[]
for name,lon,lat,h in points:
    for method in ['transform_longitude_latitude_height_to_unreal','transform_longitude_latitude_height_position_to_unreal','inaccurate_transform_longitude_latitude_height_to_unreal']:
        try:
            v=getattr(georef,method)(unreal.Vector(lon,lat,h))
            res.append({'name':name,'method':method,'input':[lon,lat,h],'out':[v.x,v.y,v.z]})
        except Exception as e:
            res.append({'name':name,'method':method,'err':repr(e)})
out.write_text(json.dumps(res,indent=2),encoding='utf-8')
print(json.dumps(res,indent=2))
