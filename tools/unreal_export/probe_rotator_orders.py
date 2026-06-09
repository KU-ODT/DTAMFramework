import unreal,json,pathlib
vals=[]
for args in [(83,0,0),(0,83,0),(0,0,83)]:
 r=unreal.Rotator(*args); vals.append({'args':args,'pitch':r.pitch,'yaw':r.yaw,'roll':r.roll})
pathlib.Path(r'D:\DTAMFramework\output\unreal_editor_dump\rotator_orders.json').write_text(json.dumps(vals,indent=2),encoding='utf-8')
print(vals)
