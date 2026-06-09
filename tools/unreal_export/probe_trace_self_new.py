import unreal,json,traceback
out=r'D:\DTAMFramework\output\unreal_editor_dump\trace_self_new_probe.json'
unreal.EditorLevelLibrary.load_level('/Game/FlyingCPP/Maps/FlyingExampleMap')
actor=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
mesh=unreal.EditorAssetLibrary.load_asset('/Engine/BasicShapes/Cube.Cube')
smc=actor.get_component_by_class(unreal.StaticMeshComponent); smc.set_static_mesh(mesh)
try: smc.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
except Exception as e: pass
start=unreal.Vector(0,0,1000); end=unreal.Vector(0,0,-1000)
res=[]
for name,fn in [
 ('line_new', lambda: unreal.SystemLibrary.line_trace_single_new(actor,start,end,unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[],unreal.DrawDebugTrace.NONE,False,unreal.LinearColor(1,0,0,1),unreal.LinearColor(0,1,0,1),0.0)),
 ('objects_new', lambda: unreal.SystemLibrary.line_trace_single_for_objects(actor,start,end,[unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1],False,[],unreal.DrawDebugTrace.NONE,False,unreal.LinearColor(1,0,0,1),unreal.LinearColor(0,1,0,1),0.0)),
]:
 try:
  r=fn(); res.append({'name':name,'type':str(type(r)),'str':str(r),'repr':repr(r)})
 except Exception as e: res.append({'name':name,'err':repr(e),'tb':traceback.format_exc()[-1000:]})
try: unreal.EditorLevelLibrary.destroy_actor(actor)
except Exception: pass
open(out,'w').write(json.dumps(res,indent=2))
