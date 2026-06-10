# ICD — Flight Plan Request (MSG 2001)

| Item | Value |
|---|---|
| Message ID | `2001` |
| Message Name | Flight Plan Request |
| Direction | `user|psu|uao -> server` |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON (UTF-8) |
| Rate | Event-based |

## 1. Overview

MSG 2001 requests flight plan generation based on a MSG 1003 scenario setup.
`scenarioFileName` specifies which scenario to generate flight plans for.

Senders: `user` (via OperationModule), `psu`, `uao`.
Receivers: `mission` (forwarded by IntegrationHub).

The request may be either an initial plan request, or a re-plan request that
revises an existing flight plan (identified by `flightPlanNumber`). Re-plan
requests SHOULD carry `reasonCode` and `triggeringEventId` so downstream
auditing can correlate the request with the upstream event (e.g. MSG 4002
warning, MSG 4103 conflict).

## 2. Layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "scenarioFileName": "<SCENARIO_FILE_NAME>",
  "flightPlanNumber": <int, optional>,
  "reasonCode": "<enum, optional>",
  "triggeringEventId": "<str, optional>",
  "arrivalVertiportHint": "<str, optional>"
}
```

## 3. Field definitions

| Field | Type | Value / Pattern | Description |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Request time (UTC) |
| `scenarioFileName` | str | non-empty | Target scenario file name (received from MSG 1003) |
| `flightPlanNumber` | int (optional) | matches a MSG 3001 plan number | Target 3001 plan number to revise. Omit for a new plan. |
| `reasonCode` | str (optional) | enum, see below | Why this (re-)plan request was issued. |
| `triggeringEventId` | str (optional) | e.g. `WARN-UAM0001-20260610-0001` (4002.eventId), `COL-UAM0001-000001` (4103.eventId) | The upstream event id that triggered this request. |
| `arrivalVertiportHint` | str (optional) | vertiport id | Recommended alternate arrival vertiport selected by the sender (PSU/UAO). Mission Planner treats this as a strong hint but final routing is Mission's responsibility. |

### 3.1 `reasonCode` enum

| Value | Typical sender | Source / meaning |
|---|---|---|
| `LOW_BATTERY` | UAO / PSU | from `4002.eventType=LOW_BATTERY` |
| `BATTERY_OVERHEAT` | UAO / PSU | from `4002.eventType` |
| `BATTERY_VOLTAGE_LOW` | UAO / PSU | from `4002.eventType` |
| `TRAFFIC_CONFLICT` | PSU | PSU traffic deconfliction |
| `LOSS_OF_SEPARATION_RISK` | PSU | PSU corridor analysis |
| `CORRIDOR_BLOCKED` | PSU | PSU |
| `WEATHER` | PSU / UAO | PSU/UAO weather assessment |
| `VERTIPORT_CAPACITY` | VPO | VPO |
| `VERTIPORT_UNAVAILABLE` | VPO | VPO |
| `OPERATOR_REQUEST` | user | manual via OperationModule |

## 4. Example

```json
{
  "timestamp": "2026-04-16T10:35:00.000Z",
  "scenarioFileName": "scenarioSetup_20260416T103000000Z.json"
}
```

## 5. Validation policy

- Missing required field → error (`ok=false`)
- Type mismatch → error
- `scenarioFileName` empty string → error

## 6. Usage examples

The 4 optional fields (`flightPlanNumber`, `reasonCode`, `triggeringEventId`,
`arrivalVertiportHint`) are **all absent for S1 (initial nominal plan)** and
**all present for S2/S3 (re-plan requests)** — except `arrivalVertiportHint`,
which is only set when the sender wants to nominate a specific alternate
vertiport (S3).

### S1 — Nominal (initial flight plan from user / OperationModule)

```json
{
  "timestamp": "2026-06-10T09:00:00.000Z",
  "scenarioFileName": "morning_route_KU_Yeouido.json"
}
```

### S2 — PSU re-plan, traffic conflict

```json
{
  "timestamp": "2026-06-10T09:15:00.000Z",
  "scenarioFileName": "morning_route_KU_Yeouido.json",
  "flightPlanNumber": 1201,
  "reasonCode": "TRAFFIC_CONFLICT",
  "triggeringEventId": "PSU-CONFLICT-1201-20260610-0001"
}
```

### S3 — UAO/PSU re-plan to alternate vertiport (after 4002 LOW_BATTERY)

```json
{
  "timestamp": "2026-06-10T09:30:15.000Z",
  "scenarioFileName": "morning_route_KU_Yeouido.json",
  "flightPlanNumber": 1201,
  "reasonCode": "LOW_BATTERY",
  "triggeringEventId": "WARN-UAM0001-20260610-0001",
  "arrivalVertiportHint": "VP_KU"
}
```
