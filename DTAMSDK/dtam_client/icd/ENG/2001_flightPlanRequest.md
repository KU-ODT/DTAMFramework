# ICD — Flight Plan Request (MSG 2001)

| Item | Value |
|---|---|
| Message ID | `2001` |
| Message Name | Flight Plan Request |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON (UTF-8) |
| Rate | Event-based |

## 1. Overview

MSG 2001 requests flight plan generation based on a MSG 1003 scenario setup.
`scenarioFileName` specifies which scenario to generate flight plans for.

## 2. Layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "scenarioFileName": "<SCENARIO_FILE_NAME>"
}
```

## 3. Field definitions

| Field | Type | Value / Pattern | Description |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Request time (UTC) |
| `scenarioFileName` | str | non-empty | Target scenario file name (received from MSG 1003) |

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
