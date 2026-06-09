# DTAM Visualization Unreal Source

This folder contains Unreal development/source artifacts for DT World.

Runtime path used by OperationModule/VisualizationModule:

```text
D:\DTAMFramework\VisualizationModule\runtime\Unreal\Environments\DTAMVisualization
```

Source project path:

```text
D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization
```

## Source/runtime rule

- Unreal C++ source, plugin source, `.uproject`, and build scripts live under `VisualizationModule_Source`.
- Packaged runtime assets and binaries used by `Start_DTAM.py` live under `VisualizationModule\runtime`.
- The packaged launcher expected by `vm_config.json` is:

```text
D:\DTAMFramework\VisualizationModule\runtime\Unreal\Environments\DTAMVisualization\Saved\StagedBuilds\Windows\DTAMVisualization.exe
```

- The large packaged binary is:

```text
D:\DTAMFramework\VisualizationModule\runtime\Unreal\Environments\DTAMVisualization\Saved\StagedBuilds\Windows\DTAMVisualization\Binaries\Win64\DTAMVisualization.exe
```

## Build/package

For a source-only Development build:

```powershell
& 'C:\Program Files\Epic Games\UE_5.5\Engine\Build\BatchFiles\Build.bat' DTAMVisualization Win64 Development -Project='D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization\DTAMVisualization.uproject' -WaitMutex -NoHotReloadFromIDE
```

For packaged runtime deployment, use:

```powershell
D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization\package.bat
```

By default `package.bat` deploys to the runtime staged path used by `VisualizationModule`:

```text
D:\DTAMFramework\VisualizationModule\runtime\Unreal\Environments\DTAMVisualization\Saved\StagedBuilds\Windows
```

## Optimization settings sync

Runtime visual settings are controlled primarily by:

```text
D:\DTAMFramework\VisualizationModule\data\configs\vm_config.json
```

When `PATCH /api/settings/rendering` is called with `persistent=true`, VisualizationModule saves:

1. `vm_config.json`
2. Unreal `DefaultGame.ini` candidates in source/runtime/staged config folders

Renderer CVars for startup are also appended through `-ExecCmds=` when `rendering_performance.apply_on_launch=true`.

The Unreal C++ side exposes the runtime command:

```text
dtam.ApplyRenderingSettings key=value ...
```

This command is registered in the AirSim `SimHUD.cpp` source and applies Cesium tile, fog, SkyLight, stream-camera tile-loading, FPS, and screen-percentage values to the running world.
