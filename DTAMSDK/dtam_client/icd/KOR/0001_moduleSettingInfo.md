# ICD - Module Setting Info (MSG 0001)

| Item | Value |
|---|---|
| Message ID | 0001 |
| Message Name | Module Setting Info |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON (UTF-8) |
| Purpose | A module reports its startup identity and role to the server. |

## Fields

| Field | Type | Description |
|---|---|---|
| `Timestamp` | string | Report time in UTC. |
| `ModuleName` | string | Module source name, e.g. `VehicleModule`. |
| `Role` | string | One of `mission`, `monitoring`, `vehicle`, `visual`, `sim_state`. |

## Validation

- Required fields must be present and type-compatible.
- `ModuleName` must not be empty.
- `Role` must be one of the SDK `Role` enum values.
