# DTAMFramework dependency policy

## Quick install

Install the active DTAM stack from the repository root:

```powershell
pip install -r requirements.txt
```

The root `requirements.txt` is an aggregate file. It only includes active modules:

- `DTAMSDK/requirements.txt`
- `IntegrationHub/requirements.txt`
- `MissionModule/requirements.txt`
- `OperationModule/requirements.txt`
- `VehicleModule/requirements.txt`
- `VisualizationModule/requirements.txt`

## Module rule

Each runnable module keeps its own `requirements.txt` at the module root so the module can also be installed/tested independently.

```text
<ModuleName>/
  XX_main.py
  app/
  data/
  requirements.txt
```

`IntegrationHub` has two runnable submodules. Their local requirement files are compatibility entry points and defer to `IntegrationHub/requirements.txt`:

```text
IntegrationHub/
  requirements.txt
  CoreServerModule/requirements.txt      # -r ../requirements.txt
  StateServerModule/requirements.txt     # -r ../requirements.txt
```

## VisualizationModule exception

`VisualizationModule/runtime/PythonClient/requirements.txt` is kept because it belongs to the bundled Cosys-AirSim Python client. `VisualizationModule/requirements.txt` includes it, so normal users still only need the module-level file or the repository root file.

## Optional integrations

- `OperationModule` can use `pyopensky` if installed, but it falls back to OpenSky REST when `pyopensky` is absent. Therefore `pyopensky` is not required for normal startup.
- Mission DEM support uses `rasterio`; it is listed in `MissionModule/requirements.txt` because altitude/terrain behavior depends on it.
- Plug-ins under `PlugIn/` keep their own `requirements.txt` and are installed only when that plug-in is used. For example:
  - `PlugIn/TrafficSim/requirements.txt`
  - `PlugIn/SituationAwareness/requirements.txt`
