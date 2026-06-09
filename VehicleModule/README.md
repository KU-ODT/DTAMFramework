# VehicleModule

VehicleModule receives mission/control ICD messages, simulates UAM vehicle state, handles keyboard/joystick/manual control, and publishes DTAM MSG 4001 vehicle status through `/ws/dtam`.

## Layout

```text
VehicleModule/
  AM_main.py                  # Entry point
  app/
    server.py                 # FastAPI app and REST API
    deps.py
    web/                      # VehicleModule GUI
    domain/
      dynamics/               # Flight trajectory simulation
      manual_dynamics/        # Keyboard/joystick/manual dynamics
      transform/              # Coordinate transforms
    services/
      integrated_service.py   # Main orchestration and ICD handling
      msg4001.py              # 4001 payload builder
      global_keyboard_capture.py
      global_joystick_capture.py
  data/
    configs/
    runtime/
    exports/
    logs/
  requirements.txt
```

## Rules

- Runtime code lives under `app/`.
- GUI files live under `app/web/`.
- `data/` stores runtime/config/export/log data only.
- Future DTAM transport-specific code should be isolated under `app/dtam/` when the service is split further.

## Run

```powershell
python VehicleModule/AM_main.py
```

Common options:

| Option | Description | Default |
| --- | --- | --- |
| `--host` | Bind address | `127.0.0.1` |
| `--port` | GUI/API port | `8100` |
| `--target-ip` | StateServerModule host | `127.0.0.1` |
| `--ws-port` | StateServerModule HTTP/WebSocket port | `8096` |
| `--no-browser` | Do not open a browser automatically | |
| `--plan` | Flight-plan JSON path; can be repeated | |
