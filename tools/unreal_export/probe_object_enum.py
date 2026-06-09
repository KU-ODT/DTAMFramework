import unreal,json
out=r'D:\DTAMFramework\output\unreal_editor_dump\object_enum_probe.json'
open(out,'w').write(json.dumps({'ObjectTypeQuery':[m for m in dir(unreal.ObjectTypeQuery) if m.startswith('OBJECT')], 'TraceTypeQuery':[m for m in dir(unreal.TraceTypeQuery) if m.startswith('TRACE')]},indent=2))
