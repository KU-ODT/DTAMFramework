import unreal,json,os,traceback
out=r'D:\DTAMFramework\output\unreal_editor_dump\trace_self_probe.json'
unreal.EditorLevelLibrary.load_level('/Game/FlyingCPP/Maps/FlyingExampleMap')
# Create actor with cube mesh at origin
actor=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
mesh=unreal.EditorAssetLibrary.load_asset('/Engine/BasicShapes/Cube.Cube')
smc=actor.get_component_by_class(unreal.StaticMeshComponent)
smc.set_static_mesh(mesh)
try: smc.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
except Exception as e: pass
try: actor.rerun_construction_scripts()
except Exception: pass
start=unreal.Vector(0,0,1000); end=unreal.Vector(0,0,-1000)
res=[]
def pack_ret(r):
    d={'str':str(r),'type':str(type(r))}
    if isinstance(r, tuple):
        d['tuple_len']=len(r); d['tuple_types']=[str(type(x)) for x in r]; d['tuple_str']=[str(x) for x in r]
        for x in r:
            if hasattr(x,'impact_point'):
                ip=x.impact_point; d['impact_point']=[ip.x,ip.y,ip.z]; d['actor']=str(x.get_editor_property('hit_object_handle')) if hasattr(x,'get_editor_property') else ''
    elif hasattr(r,'impact_point'):
        ip=r.impact_point; d['impact_point']=[ip.x,ip.y,ip.z]
    return d
calls=[
 ('line_tq1', lambda: unreal.SystemLibrary.line_trace_single(actor,start,end,unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[],unreal.DrawDebugTrace.NONE,False,unreal.LinearColor(1,0,0,1),unreal.LinearColor(0,1,0,1),0.0)),
 ('line_tq2', lambda: unreal.SystemLibrary.line_trace_single(actor,start,end,unreal.TraceTypeQuery.TRACE_TYPE_QUERY2,False,[],unreal.DrawDebugTrace.NONE,False,unreal.LinearColor(1,0,0,1),unreal.LinearColor(0,1,0,1),0.0)),
 ('objects_q1', lambda: unreal.SystemLibrary.line_trace_single_for_objects(actor,start,end,[unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1],False,[],unreal.DrawDebugTrace.NONE,False,unreal.LinearColor(1,0,0,1),unreal.LinearColor(0,1,0,1),0.0)),
 ('objects_all', lambda: unreal.SystemLibrary.line_trace_single_for_objects(actor,start,end,[getattr(unreal.ObjectTypeQuery,f'OBJECT_TYPE_QUERY{i}') for i in range(1,7)],False,[],unreal.DrawDebugTrace.NONE,False,unreal.LinearColor(1,0,0,1),unreal.LinearColor(0,1,0,1),0.0)),
]
for name,fn in calls:
    try: res.append({'name':name,'ok':True,'ret':pack_ret(fn())})
    except Exception as e: res.append({'name':name,'ok':False,'err':repr(e),'tb':traceback.format_exc()[-1200:]})
try: unreal.EditorLevelLibrary.destroy_actor(actor)
except Exception: pass
open(out,'w').write(json.dumps(res,indent=2))
