# ICD — Strategic Separation Command (MSG 3002)

| Item | Value |
|---|---|
| Message ID | `3002` |
| Message Name | Strategic Separation Command |
| Transport | UDP |
| Encoding | JSON (UTF-8) |
| Rate | Event-based |

## 1. Overview

MSG 3002 is a strategic command message for modifying existing MSG 3001 scheduled flight information.
This message specifies which flight plan to modify, at which version, and from when the modification becomes effective.
Actual modification details (seq, route specifics, resource specifics) are managed in separate data or reference structures.

## 2. Top-level layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "commandId": "<COMMAND_ID>",
  "flightPlanNumber": <int>,
  "planVersion": <int>,
  "aircraftId": "<AIRCRAFT_ID>",
  "modificationType": "<MODIFICATION_TYPE>",
  "reasonCode": "<REASON_CODE>",
  "modifyScope": "<MODIFY_SCOPE>"
}
```

## 3. Field definitions

| Field | Type | Value / Pattern | Description |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Command creation time (UTC) |
| `commandId` | str | Free-form (e.g. `SMP-20260416-001`) | Unique identifier for this modification command |
| `flightPlanNumber` | int | 1 ~ 9,999,999 | Target MSG 3001 flight plan number |
| `planVersion` | int | >= 1 | Flight plan version after modification |
| `aircraftId` | str | `^[A-Z]{2,8}\d{4}$` | Aircraft ID the command applies to |
| `modificationType` | str | See enum below | Type of modification |
| `reasonCode` | str | See enum below | Reason code for modification |
| `modifyScope` | str | See enum below | Scope of modification |

### 3.1 modificationType enum

| Value | Description |
|---|---|
| `scheduleResourceUpdate` | Schedule / resource combined update |
| `routeUpdate` | Route update |
| `aircraftSwap` | Aircraft swap |
| `delayOnly` | Delay only |
| `cancelPlan` | Plan cancellation |

### 3.2 reasonCode enum

| Value | Description |
|---|---|
| `VERTIPORT_CAPACITY` | Vertiport capacity limitation |
| `CORRIDOR_CLOSED` | Corridor closed |
| `WEATHER` | Weather conditions |
| `VEHICLE_UNAVAILABLE` | Vehicle unavailable |
| `OPERATOR_REQUEST` | Operator request |

### 3.3 modifyScope enum

| Value | Description |
|---|---|
| `departureOnly` | Departure only |
| `arrivalOnly` | Arrival only |
| `departureAndArrival` | Departure and arrival |
| `enRouteOnly` | En-route only |
| `aircraftOnly` | Aircraft only |
| `fullPlan` | Full plan |

## 4. Example

```json
{
  "timestamp": "2026-04-16T08:41:00.000Z",
  "commandId": "SMP-20260416-001",
  "flightPlanNumber": 1201,
  "planVersion": 2,
  "aircraftId": "UAM0001",
  "modificationType": "scheduleResourceUpdate",
  "reasonCode": "VERTIPORT_CAPACITY",
  "modifyScope": "departureAndArrival"
}
```

## 5. Validation policy

- Missing required field → error (`ok=false`)
- Type mismatch → error
- `timestamp` format mismatch → error
- `flightPlanNumber` out of range (1~9,999,999) → error
- `planVersion` less than 1 → error
- `aircraftId` pattern mismatch → error
- `modificationType`, `reasonCode`, `modifyScope` outside allowed values → error
- `commandId` empty string → error

## 6. Operational notes

- MSG 3002 serves as a "command header identifying what to modify."
- Actual modification details are referenced from separate data.
- When `planVersion` increases, it is appropriate to keep only the latest version active in the DB and mark previous versions as inactive or superseded.
