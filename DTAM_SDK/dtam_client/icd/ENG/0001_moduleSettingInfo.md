# ICD — Module Setting Info (MSG 0001)

| Item | Value |
|---|---|
| Message ID | `0001` |
| Message Name | Module Setting Info |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON (UTF-8) |
| Purpose | Each module reports its identity (name + role) to the server |

> **Change log**: The legacy UDP specification included `IP` / `UDPPort` / `TCPPort`.
> Under the WebSocket-only architecture, modules *connect* to the server, so endpoint
> reporting is unnecessary. A `Role` field replaces them.

## 1. Top-level layout

```json
{
  "Timestamp": "<ISO-8601 UTC>",
  "ModuleName": "<module name>",
  "Role": "<role>"
}
```

## 2. Field definitions

| Field | Type | Value / Pattern | Description |
|---|---|---|---|
| `Timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | UTC report time |
| `ModuleName` | str | Non-empty string | Reporting module identifier (e.g. `DTAMAirMobility`) |
| `Role` | str | `mission` \| `monitoring` \| `vehicle` \| `visual` \| `sim_state` | Module role |

## 3. Example

```json
{
  "Timestamp": "2026-04-28T00:00:00.000Z",
  "ModuleName": "DTAM_MissionPlanner",
  "Role": "mission"
}
```

## 4. Validation policy

- Missing required fields or type mismatches are errors.
- `ModuleName` must not be empty.
- `Role` must be one of the SDK's `Role` enum values.

## 5. Notes

- Modules also identify themselves via the `register` handshake on `/ws/dtam`
  (`{"type": "register", "role": "vehicle", "source": "DTAMAirMobility"}`).
  MSG 0001 is used when the module wants to formally publish identity metadata
  (startup time, capabilities, etc.) as an ICD message.
