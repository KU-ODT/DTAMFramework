import unreal, json, os, traceback
out=r'D:\DTAMFramework\output\unreal_editor_dump\line_trace_call_probe.json'
try:
    unreal.EditorLevelLibrary.load_level('/Game/FlyingCPP/Maps/FlyingExampleMap')
except Exception:
    pass
actor=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DTAMVisualizationVertiportPreviewActor, unreal.Vector(0,0,0), unreal.Rotator(0,0,0))
start=unreal.Vector(0,0,1000); end=unreal.Vector(0,0,-1000)
res=[]
argslist=[
    ('old_trace1', [actor,start,end,unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[],unreal.DrawDebugTrace.NONE,False,unreal.LinearColor(1,0,0,1),unreal.LinearColor(0,1,0,1),0.0]),
    ('old_trace2', [actor,start,end,unreal.TraceTypeQuery.TRACE_TYPE_QUERY2,False,[],unreal.DrawDebugTrace.NONE,False,unreal.LinearColor(1,0,0,1),unreal.LinearColor(0,1,0,1),0.0]),
    ('old_str', [actor,start,end,'TraceTypeQuery1',False,[],unreal.DrawDebugTrace.NONE,False,unreal.LinearColor(1,0,0,1),unreal.LinearColor(0,1,0,1),0.0]),
]
for name,args in argslist:
    try:
        r=unreal.SystemLibrary.line_trace_single(*args)
        res.append({'name':name,'ok':True,'ret':str(r),'type':str(type(r))})
    except Exception as e:
        res.append({'name':name,'ok':False,'err':repr(e),'tb':traceback.format_exc()[-1000:]})
for name,args in argslist:
    try:
        r=unreal.SystemLibrary.line_trace_single_new(*args)
        res.append({'name':name+'_new','ok':True,'ret':str(r),'type':str(type(r))})
    except Exception as e:
        res.append({'name':name+'_new','ok':False,'err':repr(e),'tb':traceback.format_exc()[-1000:]})
try: unreal.EditorLevelLibrary.destroy_actor(actor)
except Exception: pass
open(out,'w').write(json.dumps(res,indent=2))
