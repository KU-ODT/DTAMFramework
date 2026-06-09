import unreal, json, os
out = r'D:\DTAMFramework\output\unreal_editor_dump\component_methods_probe.json'
# load map
try:
    unreal.EditorLoadingAndSavingUtils.load_map('/Game/FlyingCPP/Maps/FlyingExampleMap')
except Exception as e:
    pass
actor_cls = unreal.DTAMVisualizationVertiportPreviewActor
actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_cls, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
try:
    actor.rerun_construction_scripts()
except Exception:
    pass
items=[]
for c in actor.get_components_by_class(unreal.ActorComponent):
    n = c.get_name()
    if n.startswith('GroundNodeMarker_') or n.startswith('GroundNodeLabel_') or n=='PreviewLabel':
        methods=[m for m in dir(c) if 'location' in m.lower() or 'world' in m.lower() or 'relative' in m.lower()]
        vals={}
        for m in ['get_component_location','get_world_location','k2_get_component_location','get_relative_location','get_editor_property']:
            if hasattr(c,m):
                vals[m]='exists'
        # Try exact methods
        for m in ['get_component_location','get_world_location','k2_get_component_location','get_relative_location']:
            if hasattr(c,m):
                try:
                    v=getattr(c,m)()
                    vals[m]=[float(v.x),float(v.y),float(v.z)]
                except Exception as e:
                    vals[m]='ERR '+str(e)
        try:
            v=c.get_editor_property('relative_location')
            vals['prop_relative_location']=[float(v.x),float(v.y),float(v.z)]
        except Exception as e:
            vals['prop_relative_location']='ERR '+str(e)
        try:
            v=c.get_editor_property('component_to_world').translation
            vals['prop_component_to_world.translation']=[float(v.x),float(v.y),float(v.z)]
        except Exception as e:
            vals['prop_component_to_world.translation']='ERR '+str(e)
        text=None
        if hasattr(c,'get_text'):
            try: text=str(c.get_text())
            except Exception as e: text='ERR '+str(e)
        items.append({'name':n,'class':c.get_class().get_name(),'vals':vals,'sample_methods':methods[:80],'text':text})
        if len(items)>8: break
try:
    unreal.EditorLevelLibrary.destroy_actor(actor)
except Exception: pass
os.makedirs(os.path.dirname(out),exist_ok=True)
open(out,'w',encoding='utf-8').write(json.dumps(items,ensure_ascii=False,indent=2))
