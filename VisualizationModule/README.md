# VisualizationModule

VisualizationModule is the DTAM visualization module. It communicates through the ServerRevision DTAM SDK WebSocket endpoint (`/ws/dtam`), applies vehicle status, mission guide, and camera-control ICD messages to the Unreal/AirSim runtime, and publishes module status (0002) and camera frames (4101).

## Layout

```text
VisualizationModule/
  VM_main.py                    # Entry point
  app/                          # VM Python runtime code
    config.py                   # Paths, ports, ICD lists, config loader
    api/
      server.py                 # FastAPI GUI/API/WebSocket server
    services/
      manager.py                # VM orchestration, periodic tasks, Unreal launch
    dtam/
      io.py                     # DTAM SDK WebSocket ICD I/O
    adapters/
      airsim.py                 # cosysairsim RPC adapter
    web/                        # VM GUI static files
  data/
    configs/
      vm_config.json            # Default VM config
      visualization_framework.json
      token.txt
    runtime/                    # Temporary runtime data
    exports/                    # Exported VM artifacts
    logs/                       # VM-local logs
  runtime/
    PythonClient/               # cosysairsim Python client
    Unreal/                     # Unreal project, packaged exe, runtime assets
  docs/
    external/                   # Upstream Cosys-AirSim docs/licenses
  requirements.txt
```

## Rules

- DTAM VM Python code lives under `app/`.
- FastAPI server code lives in `app/api/`; DTAM SDK transport code lives in `app/dtam/`; external AirSim/Unreal access lives in `app/adapters/`; orchestration/state services live in `app/services/`.
- `runtime/PythonClient` and `runtime/Unreal` are external runtime/build assets and must stay outside `app/`.
- The legacy `vm_app/` wrappers were removed. New code must use `VisualizationModule.app.*` or package-relative imports inside VM.
- The default config file is `data/configs/vm_config.json`. `app/config.py` still rewrites old root-level `vm_config.json` and old `VisualizationModule/Unreal` paths when they appear in stale configs.

## Run

```powershell
python VisualizationModule/VM_main.py
```

Default GUI URL: `http://127.0.0.1:8097`.

## Unreal runtime optimization settings

VisualizationModule keeps the runtime source of truth in:

```text
D:\DTAMFramework\VisualizationModule\data\configs\vm_config.json
```

The `rendering_performance` block controls DT World startup and runtime visual cost:

- `preset`: `performance`, `balanced`, `quality`, or `custom`.
- `frame_rate_limit`: Unreal `t.MaxFPS` value. Default is `30`.
- `screen_percentage`: Unreal render scale. Default is `70`.
- `scalability_level`: shared low-cost scalability tier used for view/post/effects/reflection/GI/AA/texture/shading/landscape groups.
- `maximum_screen_space_error`, `maximum_simultaneous_tile_loads`, `maximum_cached_megabytes`, `loading_descendant_limit`, `culled_screen_space_error`: Cesium tile streaming cost controls.
- `stream_camera_tile_loading`: keeps VPO/TestStream/CCTV camera tile loading off by default. Enable only when a stream really needs it.
- `sky_light_realtime_capture`: should remain `false` for normal operation. DT World performs at most a one-time recapture instead of continuous GPU recapture.
- `apply_on_launch`: when true, safe renderer CVars are appended to the Unreal launch `-ExecCmds=` argument.

The same Cesium/SkyLight persistent values are mirrored to Unreal `DefaultGame.ini` candidates when `persistent=true` is used.

## Rendering settings API

VM exposes two equivalent API names:

```text
GET   /api/settings/rendering
PATCH /api/settings/rendering
GET   /api/settings/visual-quality
PATCH /api/settings/visual-quality
```

Examples:

```powershell
curl.exe http://127.0.0.1:8097/api/settings/rendering
```

Apply a runtime preset to the running DT World:

```powershell
curl.exe -X PATCH http://127.0.0.1:8097/api/settings/rendering `
  -H "Content-Type: application/json" `
  -d "{\"preset\":\"performance\",\"apply_runtime\":true,\"runtime_scope\":\"all\"}"
```

Persist the balanced preset for the next session:

```powershell
curl.exe -X PATCH http://127.0.0.1:8097/api/settings/rendering `
  -H "Content-Type: application/json" `
  -d "{\"preset\":\"balanced\",\"persistent\":true}"
```

`runtime_scope` accepts only:

- `renderer`: safe renderer CVars only.
- `cesium`: Unreal `dtam.ApplyRenderingSettings` bridge only.
- `all`: both renderer CVars and Cesium/SkyLight/fog runtime settings.

If runtime apply is requested but AirSim/Unreal is not connected, `ok` becomes `false` and details are returned under `apply_runtime` and `warnings`.

## Final optimization checklist

Session 6 final acceptance and rollback steps are documented in:

```text
D:\DTAMFramework\Temp\2026-05-19\Unreal_Optimization_Final_Checklist.md
```

