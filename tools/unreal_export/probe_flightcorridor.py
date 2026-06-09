import unreal,json,os
out=r'D:\DTAMFramework\output\unreal_editor_dump\flightcorridor_methods_probe.json'
unreal.EditorLevelLibrary.load_level('/Game/FlyingCPP/Maps/FlyingExampleMap')
items=[]
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    cn=a.get_class().get_name(); lab=a.get_actor_label()
    if 'DTAM' in cn or 'DTAM' in lab or 'Vertiport' in cn or 'Vertiport' in lab or 'FlightCorridor' in cn or 'FlightCorridor' in lab:
        items.append({'label':lab,'class':cn,'methods':[m for m in dir(a) if 'preview' in m.lower() or 'rebuild' in m.lower() or 'verti' in m.lower() or 'corridor' in m.lower()][:100]})
# class methods from class default? spawn if none
try:
    cls=unreal.DTAMVisualizationFlightCorridorActor
    actor=unreal.EditorLevelLibrary.spawn_actor_from_class(cls, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
    items.append({'spawned_label':actor.get_actor_label(),'class':actor.get_class().get_name(),'methods':[m for m in dir(actor) if 'preview' in m.lower() or 'rebuild' in m.lower() or 'verti' in m.lower() or 'corridor' in m.lower()][:200]})
    try: unreal.EditorLevelLibrary.destroy_actor(actor)
    except Exception: pass
except Exception as e:
    items.append({'spawn_error':repr(e)})
open(out,'w',encoding='utf-8').write(json.dumps(items,ensure_ascii=False,indent=2))
