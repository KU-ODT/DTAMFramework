import unreal, pathlib, json
out=pathlib.Path(r'D:\DTAMFramework\output\unreal_editor_dump\python_actor_methods.txt')
cls=unreal.Actor
names=[n for n in dir(cls) if 'component' in n.lower() or 'construction' in n.lower() or 'transform' in n.lower()]
lines=['Actor methods']+names
try:
    c=unreal.DTAMVisualizationVertiportPreviewActor
    lines.append('Preview class exists')
except Exception as e:
    lines.append('Preview no '+repr(e))
out.write_text('\n'.join(lines),encoding='utf-8')
print('\n'.join(lines[:200]))
