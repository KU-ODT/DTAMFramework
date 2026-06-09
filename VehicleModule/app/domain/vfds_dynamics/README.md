# VFDS Dynamics Dispatch

This package embeds the mission receive/validate/compile/upload dispatch server inside `VehicleModule`.
All runtime code, templates, static dashboard files, config files, and requirements are kept under this directory so VehicleModule no longer depends on the old Ref package path.

## Run

The safest entrypoint is from the VehicleModule directory:

```powershell
cd D:\DTAMFramework\VehicleModule
python -m app.domain.vfds_dynamics
```

If the repository root is on `PYTHONPATH`, this also works:

```powershell
cd D:\DTAMFramework
python -m VehicleModule.app.domain.vfds_dynamics
```

## Config

- `config/server_config.yaml`
- `config/aircraft_registry.yaml`
- Relative `output` and `inbox` paths are resolved from this `vfds_dynamics` package root.

## Naming

Use `VFDS` / `vfds_dynamics` names for new code and documentation.
