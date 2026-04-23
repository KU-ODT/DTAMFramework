# DTAM GUI Scaffold

FastAPI backend and modular web frontend scaffold for a digital twin air mobility dashboard.

## Why this structure

The goal is not just to render one pretty screen. The goal is to make the codebase obvious for the next person:

- `backend` owns API routes, schemas, and backend service logic.
- `frontend` owns HTML, CSS, and browser-side JavaScript.
- Each major GUI button maps to a clear feature name: `simulation`, `mission`, `environment`, `operations`, `system`.
- New developers can immediately see where to extend one feature without touching unrelated folders.

## Folder structure

```text
DTAM_GUI/
+-- backend/
|   +-- app/
|       +-- api/
|       |   +-- router.py
|       |   +-- routes/
|       +-- core/
|       +-- schemas/
|       +-- services/
|       +-- web/
|       +-- main.py
+-- frontend/
|   +-- templates/
|   +-- static/
|       +-- css/
|       +-- js/
|           +-- api/
|           +-- components/
|           +-- features/
+-- resource/
|   +-- Kp2c.png
+-- requirements.txt
+-- README.md
```

## Backend rules

- `api/routes/`: feature-specific endpoints
- `services/`: domain data or future business logic
- `schemas/`: request and response models
- `web/`: page rendering routes

If you later add real logic, keep this pattern:

- `backend/app/api/routes/simulation.py`
- `backend/app/services/simulation_service.py`
- `backend/app/schemas/simulation.py`

## Frontend rules

- `components/`: reusable UI pieces
- `features/modules/`: button-specific loading logic
- `features/dashboard/`: page-level orchestration
- `api/`: HTTP client utilities
- `css/`: shared tokens and page styling

If you later decide to move from vanilla JS to React or Vue, keep the same feature names so the project structure still reads cleanly.

## Run

The simplest way on Windows PowerShell:

```powershell
cd C:\Users\Junyong\DTAM_GUI
pip install -r requirements.txt
python .\backend\app\main.py
```

You can also run it with Uvicorn directly:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Or without activating a venv:

```powershell
cd C:\Users\Junyong\DTAM_GUI
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## What is already implemented

- Main dashboard page inspired by your reference frame
- Large hero image area using `resource/Kp2c.png`
- Modular feature dock with five primary buttons
- Backend API endpoints for each feature
- Detail panel showing what each feature folder should own

## Recommended next expansion

1. Connect each module route to real config files or a database.
2. Add subpages under each feature, for example `mission/routes`, `mission/assets`, `mission/forms`.
3. Add authentication and role separation under `system`.
4. Replace placeholder API data in `services/dashboard_service.py` with real domain services.
