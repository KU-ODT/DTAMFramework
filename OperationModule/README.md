# OperationModule

OperationModule is the DTAM operations console. It provides the operator dashboard, mission/simulation UI, module lifecycle buttons, and ICD send/monitoring APIs.

## Layout

```text
OperationModule/
  DOC_main.py                 # Entry point
  app/                        # Runtime FastAPI package
    main.py
    comm.py
    api/
    core/
    schemas/
    services/
    web/
      router.py
      templates/
      static/
  backend/                    # Legacy compatibility wrappers for backend.app imports
  data/
  resource/                   # Large UI/map/image resources kept outside app
  requirements.txt
```

## Rules

- Runtime backend code lives under `app/`.
- Browser UI files live under `app/web/templates` and `app/web/static`.
- `backend/` is compatibility-only. New code must import `app.*`, not `backend.app.*`.
- Large static resources stay in top-level `resource/`.

## Run

```powershell
python OperationModule/DOC_main.py
```

or through the framework launcher:

```powershell
python Start_DTAM.py
```

The default GUI URL is `http://127.0.0.1:8000` unless the port is already busy.
