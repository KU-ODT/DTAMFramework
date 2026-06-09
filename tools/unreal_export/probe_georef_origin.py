import unreal, json, os
out=r'D:\DTAMFramework\output\unreal_editor_dump\georef_origin_probe.json'
unreal.EditorLevelLibrary.load_level('/Game/FlyingCPP/Maps/FlyingExampleMap')
actors=unreal.EditorLevelLibrary.get_all_level_actors()
items=[]
for a in actors:
    if 'CesiumGeoreference' in a.get_class().get_name():
        d={'label':a.get_actor_label(),'class':a.get_class().get_name()}
        for m in ['get_origin_longitude_latitude_height','get_origin_ecef','get_scale','get_editor_property']:
            if hasattr(a,m):
                try:
                    if m=='get_editor_property':
                        for prop in ['origin_longitude_latitude_height','origin_longitude','origin_latitude','origin_height','scale']:
                            try:
                                v=a.get_editor_property(prop)
                                d[prop]=str(v)
                            except Exception as e: d[prop]='ERR '+str(e)
                    else:
                        v=getattr(a,m)()
                        d[m]=str(v)
                        if hasattr(v,'x'): d[m+'_vec']=[float(v.x),float(v.y),float(v.z)]
                except Exception as e: d[m]='ERR '+repr(e)
        items.append(d)
open(out,'w').write(json.dumps(items,indent=2))
