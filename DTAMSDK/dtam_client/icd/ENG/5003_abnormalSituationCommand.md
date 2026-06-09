# 5003 Abnormal Situation Command

## Purpose

Operator command for injecting abnormal situations or obstacles into the DT World through the server. The first supported type is `bird_flock`; the schema is intentionally generic for future types such as `drone_intruder`, `weather_cell`, or `ground_obstacle`.

## Transport

- Transport: WebSocket JSON (`/ws/dtam`)
- Direction: `operator -> server -> visual`
- Rate: event-based, normally sent once per spawn/update/remove action
- DB Folder: `AbnormalSituationCommand`

## Payload

```json
{
  "timestamp": "2026-05-16T00:00:00.000Z",
  "commandId": "OBS-BIRD-001",
  "action": "create",
  "abnormalType": "bird_flock",
  "obstacleId": "bird_flock_001",
  "position": {
    "lat": 37.56,
    "lon": 126.98,
    "alt": 120.0
  },
  "radiusM": 800.0,
  "count": 9,
  "headingDeg": 0.0,
  "speedMps": 12.0,
  "durationSec": 0.0,
  "severity": "warning",
  "affectedAircraftIds": [],
  "metadata": {
    "source": "OperationModule",
    "assetKey": "birds_fab_fbx"
  }
}
```

## Fields

| Field | Type | Required | Description |
|---|---:|:---:|---|
| `timestamp` | string | Yes | ISO-8601 UTC timestamp |
| `commandId` | string | Yes | Command identifier |
| `action` | string | Yes | `create`, `update`, `remove`, `clear` |
| `abnormalType` | string | Yes | Abnormal/obstacle type, e.g. `bird_flock` |
| `obstacleId` | string | Yes | Target obstacle identifier |
| `position.lat` | number | Yes | Center latitude |
| `position.lon` | number | Yes | Center longitude |
| `position.alt` | number | Yes | Center altitude in meters AMSL |
| `radiusM` | number | Yes | Activity radius in meters |
| `count` | integer | Yes | Number of entities |
| `headingDeg` | number | No | Initial heading |
| `speedMps` | number | Yes | Average movement speed |
| `durationSec` | number | No | 0 means keep until removed |
| `severity` | string | No | `info`, `warning`, `critical` |
| `affectedAircraftIds` | array[string] | No | Affected aircraft IDs |
| `metadata` | object | No | Implementation-specific metadata |

