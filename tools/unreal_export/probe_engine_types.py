import unreal, json, os
out=r'D:\DTAMFramework\output\unreal_editor_dump\engine_types_probe.json'
info={}
if hasattr(unreal,'EngineTypes'):
    info['EngineTypes']=[m for m in dir(unreal.EngineTypes) if 'trace' in m.lower() or 'collision' in m.lower() or 'object' in m.lower()]
    for m in info['EngineTypes']:
        if 'convert' in m.lower():
            try: info[m]=str(getattr(unreal.EngineTypes,m))
            except Exception as e: info[m]=repr(e)
try:
    for ch in [unreal.CollisionChannel.ECC_WORLD_STATIC, unreal.CollisionChannel.ECC_VISIBILITY]:
        try:
            tq=unreal.EngineTypes.convert_to_trace_type(ch)
            info[str(ch)]=str(tq)
        except Exception as e: info[str(ch)]='ERR '+repr(e)
except Exception as e: info['err']=repr(e)
open(out,'w').write(json.dumps(info,indent=2))
