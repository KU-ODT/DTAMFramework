import unreal, json, pathlib, time
out=pathlib.Path(r'D:\DTAMFramework\output\unreal_editor_dump\spawn_preview_probe.json')
unreal.EditorLevelLibrary.load_level('/Game/FlyingCPP/Maps/FlyingExampleMap')
georef=None
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if 'CesiumGeoreference' in a.get_class().get_name(): georef=a
if not georef:
    georef=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CesiumGeoreference, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
georef.set_origin_longitude_latitude_height(unreal.Vector(126.978,37.5665,350.0))
loc=georef.transform_longitude_latitude_height_position_to_unreal(unreal.Vector(127.069068,37.514368,60.0))
rot=georef.transform_east_south_up_rotator_to_unreal(unreal.Rotator(0,83,0), loc)
# spawn actor
actor=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DTAMVisualizationVertiportPreviewActor, loc, rot)
actor.set_actor_label('PROBE_JAMSIL')
try: actor.set_editor_property('VertiportName','잠실')
except Exception as e: print('set prop failed', e)
# maybe set mesh
try:
    mesh=unreal.EditorAssetLibrary.load_asset('/Game/vp_model/Vertiport_round_KU.Vertiport_round_KU')
    smc=actor.get_component_by_class(unreal.StaticMeshComponent)
    smc.set_static_mesh(mesh)
except Exception as e: print('mesh failed', e)
try: actor.rerun_construction_scripts()
except Exception as e: print('rerun failed', e)
# wait
res={'loc':[loc.x,loc.y,loc.z], 'rot':[rot.pitch,rot.yaw,rot.roll], 'actor_loc':[actor.get_actor_location().x,actor.get_actor_location().y,actor.get_actor_location().z], 'actor_rot':[actor.get_actor_rotation().pitch,actor.get_actor_rotation().yaw,actor.get_actor_rotation().roll], 'components':[]}
for c in actor.get_components_by_class(unreal.ActorComponent):
    name=c.get_name()
    if name.startswith('GroundNodeMarker') or name.startswith('GroundNodeLabel') or name=='PreviewLabel':
        d={'name':name,'class':c.get_class().get_name()}
        try:
            v=c.get_component_location(); d['world']=[v.x,v.y,v.z]
        except Exception: pass
        try:
            v=c.get_relative_location(); d['rel']=[v.x,v.y,v.z]
        except Exception: pass
        try:
            if 'TextRender' in c.get_class().get_name(): d['text']=str(c.get_editor_property('text'))
        except Exception as e: d['text_err']=repr(e)
        res['components'].append(d)
out.write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2)[:4000])
