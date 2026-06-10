# ICD — Tactical Separation Command (MSG 3003)

| Item | Value |
|---|---|
| Message ID | `3003` |
| Message Name | Tactical Separation Command |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON (UTF-8) |
| Direction | `mission|psu -> server -> vehicle/mission` |
| Rate | Event-based |

## 1. Overview

MSG 3003 is a tactical action command message for immediate application to a specific aircraft in flight.
This message is not for conveying analysis results, but for delivering the sequence of actions the simulator should actually execute.
Actions are defined sequentially in the `actions` array; the next action begins when the previous one completes.

MSG 3003 is issued by Mission OR PSU (`mission|psu -> server`). PSU directly issues 3003 when it detects a collision risk through continuous trajectory prediction, or in an MSG 4002 emergency situation.
Receivers are Vehicle (executes the actions) and Mission (receives PSU-issued commands — for plan consistency tracking).

## 2. Top-level layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "commandId": "<COMMAND_ID>",
  "aircraftId": "<AIRCRAFT_ID>",
  "reasonCode": "<REASON_CODE>",
  "actions": [ { ... }, { ... } ]
}
```

## 3. Top-level fields

| Field | Type | Value / Pattern | Description |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Command creation time (UTC) |
| `commandId` | str | Free-form (e.g. `TMP-20260416-011`) | Unique tactical command identifier |
| `aircraftId` | str | `^[A-Z]{2,8}\d{4}$` | Target aircraft ID |
| `reasonCode` | str | See enum below | Reason code for the command |
| `actions` | array | >= 1 element | List of actions to perform (array order = execution order) |

### 3.1 reasonCode enum

| Value | Description |
|---|---|
| `LOSS_OF_SEPARATION_RISK` | Separation distance risk |
| `LOCAL_CORRIDOR_BLOCKED` | Local corridor blocked |
| `LOW_BATTERY` | Low battery |
| `WEATHER_AVOIDANCE` | Weather avoidance |
| `OPERATOR_OVERRIDE` | Operator override |
| `EMERGENCY_LANDING` | Emergency landing |

## 4. Action common rules

- `actions` are executed in order.
- The next action begins when the current action completes.
- If a newer 3003 message (by `timestamp`) is received for the same `aircraftId`, pending incomplete actions are discarded and replaced by the new command.
- MSG 3003 expresses intent purely through action combinations, without a top-level commandType.

## 5. Action definitions

### 5.1 setSpeed

```json
{ "type": "setSpeed", "targetSpeed": <float> }
```

| Field | Type | Unit | Range | Description |
|---|---|---|---|---|
| `type` | str | - | fixed `setSpeed` | Action type |
| `targetSpeed` | float | m/s | 0 ~ 200 | Target speed to apply immediately |

### 5.2 directTo

```json
{
  "type": "directTo",
  "targetLLAs": [
    { "lat": <float>, "lon": <float>, "alt": <float>, "targetSpeed": <float> }
  ]
}
```

| Field | Type | Unit | Range | Description |
|---|---|---|---|---|
| `type` | str | - | fixed `directTo` | Action type |
| `targetLLAs` | array | - | >= 1 element | Ordered list of target coordinates |
| `targetLLAs[].lat` | float | deg | -90 ~ 90 | Latitude |
| `targetLLAs[].lon` | float | deg | -180 ~ 180 | Longitude |
| `targetLLAs[].alt` | float | m | -500 ~ 20000 | Altitude |
| `targetLLAs[].targetSpeed` | float | m/s | 0 ~ 200 | Target speed for this waypoint (required) |

### 5.3 hold

```json
{
  "type": "hold",
  "holdLLA": { "lat": <float>, "lon": <float>, "alt": <float> },
  "turnDirection": "<CW | CCW>",
  "holdingRadiusM": <float>,
  "maxHoldingCount": <int>
}
```

| Field | Type | Unit | Range | Description |
|---|---|---|---|---|
| `type` | str | - | fixed `hold` | Action type |
| `holdLLA.lat` | float | deg | -90 ~ 90 | Hold reference latitude |
| `holdLLA.lon` | float | deg | -180 ~ 180 | Hold reference longitude |
| `holdLLA.alt` | float | m | -500 ~ 20000 | Hold reference altitude |
| `turnDirection` | str | - | `CW` / `CCW` | Hold turn direction |
| `holdingRadiusM` | float | m | 1 ~ 5000 | Holding radius |
| `maxHoldingCount` | int | - | 0 ~ 9999 | Hold repeat count (0 = unlimited) |

### 5.4 rejoinPlan

```json
{ "type": "rejoinPlan", "atSeq": <int> }
```

| Field | Type | Range | Description |
|---|---|---|---|
| `type` | str | fixed `rejoinPlan` | Action type |
| `atSeq` | int | 1 ~ 9999 | `enRoute.seq` number in the active MSG 3001 plan to rejoin at |

### 5.5 land

```json
{
  "type": "land",
  "targetLLA": { "lat": <float>, "lon": <float>, "alt": <float> },
  "vertiport": "<VERTIPORT_NAME>",
  "fatoNumber": "<FATO_ID>"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | str | ✔ | fixed `land` |
| `targetLLA` | object | △ | Landing target coordinates (emergency / ad-hoc) |
| `vertiport` | str | △ | Target vertiport name |
| `fatoNumber` | str | ✖ | Target FATO number |

- At least one of `targetLLA` or `vertiport` must be present.
- `targetLLA` only → ad-hoc / emergency landing.
- `vertiport` only → vertiport landing.

## 6. Execution rules

- `actions` are executed in array order.
- `setSpeed` followed by `directTo`: speed change applies first, then the route is followed.
- `directTo.targetLLAs` are followed in array order.
- `hold` followed by `rejoinPlan`: after holding completes, rejoin the active MSG 3001 plan at the specified seq.
- A `hold` with `maxHoldingCount` = 0 continues until a new MSG 3003 arrives.
- When a new MSG 3003 is received for the same `aircraftId`, remaining actions from the previous command are cancelled.

## 7. Examples

### 7.1 Decelerate, hold twice, rejoin plan

```json
{
  "timestamp": "2026-04-16T09:06:12.000Z",
  "commandId": "TMP-20260416-011",
  "aircraftId": "UAM0004",
  "reasonCode": "LOSS_OF_SEPARATION_RISK",
  "actions": [
    { "type": "setSpeed", "targetSpeed": 18.0 },
    {
      "type": "hold",
      "holdLLA": { "lat": 37.52300, "lon": 126.93600, "alt": 180.0 },
      "turnDirection": "CW", "holdingRadiusM": 120.0, "maxHoldingCount": 2
    },
    { "type": "rejoinPlan", "atSeq": 9 }
  ]
}
```

### 7.2 Temporary detour, rejoin plan

```json
{
  "timestamp": "2026-04-16T09:11:40.000Z",
  "commandId": "TMP-20260416-012",
  "aircraftId": "UAM0004",
  "reasonCode": "LOCAL_CORRIDOR_BLOCKED",
  "actions": [
    { "type": "setSpeed", "targetSpeed": 18.0 },
    {
      "type": "directTo",
      "targetLLAs": [
        { "lat": 37.52270, "lon": 126.93680, "alt": 200.0, "targetSpeed": 25.0 },
        { "lat": 37.52090, "lon": 126.94410, "alt": 200.0, "targetSpeed": 23.0 },
        { "lat": 37.51860, "lon": 126.95240, "alt": 180.0, "targetSpeed": 23.0 }
      ]
    },
    { "type": "rejoinPlan", "atSeq": 11 }
  ]
}
```

### 7.3 Alternate vertiport landing

```json
{
  "timestamp": "2026-04-16T09:18:05.000Z",
  "commandId": "TMP-20260416-015",
  "aircraftId": "UAM0011",
  "reasonCode": "LOW_BATTERY",
  "actions": [
    {
      "type": "directTo",
      "targetLLAs": [
        { "lat": 37.55520, "lon": 126.97010, "alt": 120.0, "targetSpeed": 20.0 }
      ]
    },
    { "type": "land", "vertiport": "SeoulStation-Alt", "fatoNumber": "EF1" }
  ]
}
```

### 7.4 Emergency landing at ad-hoc location

```json
{
  "timestamp": "2026-04-16T09:20:10.000Z",
  "commandId": "TMP-20260416-016",
  "aircraftId": "UAM0013",
  "reasonCode": "EMERGENCY_LANDING",
  "actions": [
    { "type": "setSpeed", "targetSpeed": 12.0 },
    {
      "type": "directTo",
      "targetLLAs": [
        { "lat": 37.55490, "lon": 126.96995, "alt": 60.0, "targetSpeed": 12.0 }
      ]
    },
    {
      "type": "land",
      "targetLLA": { "lat": 37.55460, "lon": 126.96980, "alt": 0.0 }
    }
  ]
}
```

## 8. Validation policy

- Missing required field → error (`ok=false`)
- Type mismatch → error
- `timestamp` format mismatch → error
- `aircraftId` pattern mismatch → error
- `actions` length 0 → error
- `directTo.targetLLAs` length 0 → error
- Missing `lat`, `lon`, `alt`, `targetSpeed` in any `targetLLAs` element → error
- Missing `turnDirection`, `holdingRadiusM`, `maxHoldingCount` in `hold` → error
- `land` with neither `targetLLA` nor `vertiport` → error
- `rejoinPlan.atSeq` less than 1 → error
- `commandId` empty string → error
