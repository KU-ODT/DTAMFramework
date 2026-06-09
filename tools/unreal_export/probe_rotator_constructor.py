import unreal, pathlib, json
r=unreal.Rotator(0,83,0)
path=pathlib.Path(r'D:\DTAMFramework\output\unreal_editor_dump\rotator_constructor_probe.json')
path.write_text(json.dumps({'pitch':r.pitch,'yaw':r.yaw,'roll':r.roll},indent=2),encoding='utf-8')
print(r.pitch,r.yaw,r.roll)
