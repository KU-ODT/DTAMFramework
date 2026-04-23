# ICD — Module Status (MSG 0002)

| Item | Value |
|---|---|
| Message ID | `0002` |
| Message Name | Module Status |
| Transport | UDP |
| Encoding | JSON (UTF-8) |
| Rate | 1 Hz (every 1 second) |

## 1. Top-level layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "source":    "<module name in English>",
  "status":    <int>
}
```

## 2. Field definitions

| Field | Type | Value / Pattern | Description |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Transmission time (UTC) |
| `source`    | str | English module name | Name of the reporting module |
| `status`    | int | `1` | Status code (1 = Normal) |

## 3. Example

```json
{
  "timestamp": "2026-04-16T05:30:00.000Z",
  "source": "FlightDynamics",
  "status": 1
}
```

## 4. Validation policy

- Missing field or type mismatch → error (`ok=false`)
- `source` must not be empty
- `status` value out of allowed range → error
