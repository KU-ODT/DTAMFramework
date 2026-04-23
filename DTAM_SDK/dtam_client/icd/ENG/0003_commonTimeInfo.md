# ICD — Common Time Info (MSG 0003)

| Item | Value |
|---|---|
| Message ID | `0003` |
| Message Name | Common Time Info |
| Transport | UDP |
| Encoding | JSON (UTF-8) |
| Rate | 1 Hz (every 1 second) |

## 1. Overview

MSG 0003 provides a shared time reference for all modules.
`timestamp` is the actual send time, while `simTime` is the simulation's internal clock.

## 2. Layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "simTime": "<ISO-8601 UTC>"
}
```

## 3. Field definitions

| Field | Type | Value / Pattern | Description |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Actual send time (UTC) |
| `simTime` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Simulation internal time (UTC) |

## 4. Example

```json
{
  "timestamp": "2026-04-16T12:00:01.000Z",
  "simTime": "2026-04-16T09:30:15.000Z"
}
```

## 5. Validation policy

- Missing required field → error (`ok=false`)
- Type mismatch → error
- `timestamp`, `simTime` format mismatch → error

## 6. Operational notes

- `timestamp` and `simTime` may differ (fast-forward, pause, etc.).
- Receiving modules should use `simTime` as the reference for simulation logic.
