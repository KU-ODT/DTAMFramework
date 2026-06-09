# MissionModule

MissionModule provides mission planning, route generation, altitude/DEM handling, and scheduled-flight ICD export for DTAM.

## Layout

```text
MissionModule/
  MP_main.py                  # Entry point
  app/
    config.py
    server.py
    state.py
    routes/                   # HTTP routes
    services/                 # Mission planning/export services
    domain/                   # Coordinate/route domain logic
    web/                      # Mission planner GUI
  data/                       # CSV coordinate data and mission exports
    configs/
    runtime/
    exports/
    logs/
    groundmaps/
    mission_exports/
  resources/                  # Large static map/image resources kept outside app
  requirements.txt
```

## Rules

- Runtime code lives under `app/`.
- GUI files live under `app/web/`.
- Large map/image resources stay in top-level `resources/` for compatibility.
- `data/` stores coordinate tables, mission exports, runtime/config/log data.

## Run

```powershell
python MissionModule/MP_main.py
```

The default GUI URL is `http://127.0.0.1:8090`.
