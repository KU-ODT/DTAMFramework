# ICD — DTAM Execute (MSG 2002)

| Item | Value |
|---|---|
| Message ID | `2002` |
| Message Name | DTAM Execute |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON (UTF-8) |
| Rate | Event-based |

## 1. Overview

MSG 2002 requests DTAM simulation execution.
It includes all configuration file names and the flight plan folder name from previous setup steps, so the receiver can load them and start the simulation.

## 2. Layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "simModeFileName": "<SIM_MODE_FILE>",
  "simulationSetupFileName": "<SIMULATION_SETUP_FILE>",
  "scenarioFileName": "<SCENARIO_FILE>",
  "flightPlanFolderName": "<FLIGHT_PLAN_FOLDER>",
  "scenarioId": "<S1|S2|S3, optional>"
}
```

## 3. Field definitions

| Field | Type | Description | Example |
|---|---|---|---|
| `timestamp` | str | Request time (UTC) | `2026-04-16T10:40:00.000Z` |
| `simModeFileName` | str | MSG 1001 sim mode setup file | `simModeSetup_20260416T103000000Z.json` |
| `simulationSetupFileName` | str | MSG 1002 simulation setup file | `simulationSetup_20260416T103000000Z.json` |
| `scenarioFileName` | str | MSG 1003 scenario setup file | `scenarioSetup_20260416T103000000Z.json` |
| `flightPlanFolderName` | str | MSG 3001 flight plan folder | `FlightPlan_20260416T103500000Z` |
| `scenarioId` | str (optional) | Demo scenario identifier — used by Vehicle for per-scenario branching (`"S1"`\|`"S2"`\|`"S3"`). S3: battery degradation profile + arming the combined UAO decision logic, S2: PSU speed-adjustment re-plan scenario — no vehicle-side special arming (5004 wind and 3003 setSpeed are standard message handling). Omitted → normal execution | `S3` |

## 4. Example

```json
{
  "timestamp": "2026-04-16T10:40:00.000Z",
  "simModeFileName": "simModeSetup_20260416T103000000Z.json",
  "simulationSetupFileName": "simulationSetup_20260416T103000000Z.json",
  "scenarioFileName": "scenarioSetup_20260416T103000000Z.json",
  "flightPlanFolderName": "FlightPlan_20260416T103500000Z"
}
```

With demo scenario (`scenarioId` included):

```json
{
  "timestamp": "2026-04-16T10:40:00.000Z",
  "simModeFileName": "simModeSetup_20260416T103000000Z.json",
  "simulationSetupFileName": "simulationSetup_20260416T103000000Z.json",
  "scenarioFileName": "scenarioSetup_20260416T103000000Z.json",
  "flightPlanFolderName": "FlightPlan_20260416T103500000Z",
  "scenarioId": "S3"
}
```

## 5. Validation policy

- Missing required field → error (`ok=false`)
- Type mismatch → error
- Empty string for any file/folder name → error
- `scenarioId` is optional — when omitted, normal execution

## 6. Operational notes

- On receiving MSG 2002, the module loads all 4 files/folders and initializes the simulation.
- Load order: 1001 (mode) → 1002 (setup) → 1003 (scenario) → 3001 (flight plans folder)
- `scenarioId` lets the Operation Console tell Vehicle which demo scenario (S1/S2/S3) is running at execution time.
  Vehicle branches on `scenarioId` in `on_dtam_execute()`: S1 → normal run, S2 → PSU speed-adjustment re-plan scenario — no vehicle-side special arming (5004 wind and 3003 setSpeed are standard message handling), S3 → activate battery degradation profile + arm the combined UAO decision logic (the UAO role is handled by VehicleModule itself, not a separate module).
- Omitted → normal execution. Vehicle already receives MSG 2002, so no routing change is required.
