import unreal, json, pathlib, inspect
out=pathlib.Path(r'D:\DTAMFramework\output\unreal_editor_dump\cesium_api_probe.txt')
lines=[]
for name in dir(unreal):
    if 'CesiumGeoreference' in name or 'GlobeAnchor' in name or 'Cesium' in name:
        lines.append(name)
try:
    cls=unreal.CesiumGeoreference
    lines.append('CesiumGeoreference methods:')
    lines += [m for m in dir(cls) if 'transform' in m.lower() or 'longitude' in m.lower() or 'origin' in m.lower()]
except Exception as e:
    lines.append('no cls '+repr(e))
try:
    cls=unreal.CesiumGlobeAnchorComponent
    lines.append('CesiumGlobeAnchorComponent methods:')
    lines += [m for m in dir(cls) if 'longitude' in m.lower() or 'height' in m.lower() or 'rotation' in m.lower() or 'move' in m.lower()]
except Exception as e:
    lines.append('no anchor '+repr(e))
out.write_text('\n'.join(lines), encoding='utf-8')
print('\n'.join(lines[:200]))
