# ICD - Module Setting Info (MSG 0001)

| Item | Value |
|---|---|
| Message ID | `0001` |
| Message Name | Module Setting Info |
| Transport | UDP |
| Encoding | JSON (UTF-8) |
| Purpose | Each module reports its receive IP and open ports to the server |

## 1. Top-level layout

```json
{
  "Timestamp": "<ISO-8601 UTC>",
  "ModuleName": "<module name>",
  "IP": "<IPv4 address>",
  "UDPPort": 17000,
  "TCPPort": 17001
}
```

## 2. Field definitions

| Field | Type | Value / Pattern | Description |
|---|---|---|---|
| `Timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Report time in UTC |
| `ModuleName` | str | Non-empty string | Name of the reporting module |
| `IP` | str | IPv4 address | IP of the computer running the module |
| `UDPPort` | int | `1`-`65535` | UDP receive port opened by the module |
| `TCPPort` | int | `1`-`65535` | TCP receive port opened by the module |

## 3. Example

```json
{
  "Timestamp": "2026-04-17T00:00:00.000Z",
  "ModuleName": "MissionPlanner",
  "IP": "192.168.0.21",
  "UDPPort": 17000,
  "TCPPort": 17001
}
```

## 4. Validation policy

- Missing fields and type mismatches are errors.
- `ModuleName` must not be empty.
- `IP` must be a valid IPv4 address.
- `UDPPort` and `TCPPort` must be valid TCP/UDP port numbers.
