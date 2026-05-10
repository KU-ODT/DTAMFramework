# ICD — Scheduled Flight (MSG 3001)

| Item | Value |
|---|---|
| Message ID | `3001` |
| Message Name | Scheduled Flight |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON (UTF-8) |
| Rate | Event-based (once per schedule) |

## 1. Overview

MSG 3001 defines the original flight plan information for a scheduled flight.
It can be stored in the DB as `flightPlanNumber`-`planVersion`.
Example: 1201-1, 1201-2, 1201-3

MSG 3001 always contains the complete plan for that version.
When a new version is created, the previous version is managed via `planStatus`.

### 1.1 Storage rules

Scheduled flights are stored by the DTAM Server Emulator under a per-session
root (`ServerStart_<UTC timestamp>`) and a per-message-type subfolder.
Each aircraft's plan is written to its own JSON file.

```
DB/
└── ServerStart_<timestamp>/
    └── ScheduledFlight/
        ├── 1201_UAM0001.json
        ├── 1202_UAM0002.json
        └── 1203_UAM0003.json
```

- **Session folder**: `ServerStart_<UTC timestamp>` (e.g. `ServerStart_20260420T103500000Z`).
  One folder is created each time the DTAM Server Emulator boots.
- **Message subfolder**: `ScheduledFlight/` (one subfolder per message type under the session).
- **File name**: `{flightPlanNumber}_{aircraftId}.json` (e.g. `1201_UAM0001.json`).
- The session folder path is referenced by MSG 2002 `DTAM Execute` via
  `flightPlanFolderName`, so downstream modules can look up the exact plan
  files used during that run.

## 2. Top-level layout

```json
{
  "flightPlanNumber": <int>,
  "planVersion": <int>,
  "planStatus": "<PLAN_STATUS>",
  "aircraftId": "<AIRCRAFT_ID>",
  "departure": { ... },
  "enRoute":   [ { ... }, ... ],
  "arrival":   { ... }
}
```

### 2.1 Top-level fields

| Field | Type | Range/Pattern | Description |
|---|---|---|---|
| `flightPlanNumber` | int | 1 ~ 9,999,999 | Flight plan number |
| `planVersion` | int | >= 1 | Plan version number (increments on each modification) |
| `planStatus` | str | `active` / `superseded` / `discarded` | Plan status |
| `aircraftId` | str | `^[A-Z]{2,8}\d{4}$` (shared with MSG 4001) | Aircraft ID (e.g. `UAM0001`) |

### 2.2 planStatus enum

| Value | Description |
|---|---|
| `active` | Current usable latest plan |
| `superseded` | Previous plan replaced by a newer version |
| `discarded` | Cancelled or invalidated plan |

## 3. departure

| Field | Type | Format | Description |
|---|---|---|---|
| `vertiport`      | str | - | Departure vertiport |
| `std`            | str | `HH:MM:SS` | Scheduled Time of Departure |
| `depGateNumber`  | str | - | Departure gate number |
| `eobt`           | str | `HH:MM:SS` | Estimated Off-Block Time |
| `depFatoNumber`  | str | - | Departure FATO number |
| `etot`           | str | `HH:MM:SS` | Estimated Take-Off Time |

## 4. enRoute (segment array)

Each element (>= 1):

| Field | Type | Unit | Range/Pattern | Required | Description |
|---|---|---|---|---|---|
| `seq`           | int   | -   | 1 ~ 9999            | ✔ | Sequence (monotonic ↑) |
| `phase`         | str   | -   | `^[A-Z]$`           | ✔ | Phase letter |
| `startLLA`      | LLA   | -   | see §4.1            | ✔ | Start point |
| `endLLA`        | LLA   | -   | see §4.1            | ✔ | End point |
| `targetSpeed`   | float | m/s | 0 ~ 200             | ✔ | Target speed |
| `turnDirection` | str   | -   | `CW` / `CCW`        | ✖ | Turn direction |
| `centerLLA`     | LLA   | -   | see §4.1            | △ | Required when `turnDirection` is present |

### 4.1 LLA (shared)

| Field | Type | Unit | Range |
|---|---|---|---|
| `lat` | float | deg | -90 ~ 90 |
| `lon` | float | deg | -180 ~ 180 |
| `alt` | float | m   | -500 ~ 20000 |

## 5. arrival

| Field | Type | Format | Description |
|---|---|---|---|
| `vertiport`      | str | - | Arrival vertiport |
| `sta`            | str | `HH:MM:SS` | Scheduled Time of Arrival |
| `arrGateNumber`  | str | - | Arrival gate number |
| `eibt`           | str | `HH:MM:SS` | Estimated In-Block Time |
| `arrFatoNumber`  | str | - | Arrival FATO number |
| `eldt`           | str | `HH:MM:SS` | Estimated Landing Time |

## 6. Example

```json
{
  "flightPlanNumber": 1201,
  "planVersion": 2,
  "planStatus": "active",
  "aircraftId": "UAM0001",
  "departure": {
    "vertiport": "Yeouido",
    "std": "09:08:00",
    "depGateNumber": "G5",
    "eobt": "09:10:00",
    "depFatoNumber": "F1",
    "etot": "09:15:00"
  },
  "enRoute": [
    {
      "seq": 1, "phase": "A",
      "startLLA": {"lat": 37.52545, "lon": 126.92142, "alt": 0},
      "endLLA": {"lat": 37.52568, "lon": 126.92205, "alt": 60},
      "targetSpeed": 8
    },
    {
      "seq": 2, "phase": "B",
      "startLLA": {"lat": 37.52568, "lon": 126.92205, "alt": 60},
      "endLLA": {"lat": 37.52490, "lon": 126.92850, "alt": 180},
      "targetSpeed": 30
    },
    {
      "seq": 3, "phase": "C",
      "startLLA": {"lat": 37.52490, "lon": 126.92850, "alt": 180},
      "endLLA": {"lat": 37.52180, "lon": 126.94450, "alt": 180},
      "targetSpeed": 45,
      "turnDirection": "CW",
      "centerLLA": {"lat": 37.52300, "lon": 126.93600, "alt": 180}
    }
  ],
  "arrival": {
    "vertiport": "Jamsil",
    "sta": "10:06:00",
    "arrGateNumber": "G1",
    "eibt": "10:04:00",
    "arrFatoNumber": "F1",
    "eldt": "09:58:00"
  }
}
```

## 7. Validation policy

- Missing required field / type mismatch / out-of-range / pattern mismatch → error (`ok=false`)
- `planVersion` less than 1 → error
- `planStatus` outside allowed values → error
- `enRoute.seq` must be monotonically increasing
- If `turnDirection` is present, `centerLLA` is required
- `aircraftId` shares its pattern with MSG 4001 (`common.AIRCRAFT_ID_PATTERN`)

## 8. Operational rules

- Simulators and DB queries must only use data where `planStatus` is `active`.
- When a new version becomes `active` for the same `flightPlanNumber`, the previous `active` version must be changed to `superseded`.
- `discarded` is used for plans cancelled by an operator or otherwise invalidated.
