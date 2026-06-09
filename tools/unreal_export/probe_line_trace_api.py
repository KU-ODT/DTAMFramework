import unreal, json, os, inspect
out=r'D:\DTAMFramework\output\unreal_editor_dump\line_trace_api_probe.json'
info=[]
for name in dir(unreal.SystemLibrary):
    if 'trace' in name.lower(): info.append(name)
extra={}
for nm in ['line_trace_single','line_trace_single_new','sphere_trace_single','box_trace_single']:
    if hasattr(unreal.SystemLibrary,nm):
        f=getattr(unreal.SystemLibrary,nm)
        try: extra[nm]=str(inspect.signature(f))
        except Exception as e: extra[nm]='sig_err '+repr(e)
chan=[]
for n in dir(unreal):
    if n in ['TraceTypeQuery','CollisionChannel','DrawDebugTrace','ObjectTypeQuery','EngineTypes']:
        chan.append(n)
try: chan += ['CollisionChannel members:'+ ','.join([m for m in dir(unreal.CollisionChannel) if m.startswith('ECC')][:50])]
except Exception as e: chan.append('coll err '+str(e))
try: chan += ['TraceTypeQuery members:'+ ','.join([m for m in dir(unreal.TraceTypeQuery) if m.startswith('TRACE')][:50])]
except Exception as e: chan.append('trace err '+str(e))
try: chan += ['DrawDebugTrace members:'+ ','.join([m for m in dir(unreal.DrawDebugTrace) if m.isupper()][:50])]
except Exception as e: chan.append('draw err '+str(e))
open(out,'w').write(json.dumps({'methods':info,'extra':extra,'enums':chan},indent=2))
