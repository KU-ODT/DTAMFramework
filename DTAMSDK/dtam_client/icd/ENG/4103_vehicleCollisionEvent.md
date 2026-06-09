# ICD - Vehicle Collision Event (MSG 4103)

| Item | Value |
|---|---|
| Message ID | 4103 |
| Message Name | Vehicle Collision Event |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON only |
| Direction | `visual -> server -> vehicle/monitoring/situation_awareness` |
| Rate | Event-based |
| DB Folder | `VehicleCollisionEvent` |

MSG 4103 reports a collision detected by VisualizationModule from Unreal/AirSim.
Unreal/AirSim is the collision sensor, while VehicleModule remains the authority
that decides how the aircraft state changes after the event.

## Payload example

```json
{
  "message_id": 4103,
  "message_name": "Vehicle Collision Event",
  "timestamp": "2026-05-16T15:30:00.000Z",
  "eventId": "COL-UAM0001-000001",
  "aircraftId": "UAM0001",
  "airsimVehicleName": "Drone1",
  "hasCollided": true,
  "objectName": "ObstacleActor_01",
  "objectId": -1,
  "positionNed": {
    "north": 120.3,
    "east": -55.1,
    "down": -18.2
  },
  "impactPointNed": {
    "north": 120.1,
    "east": -54.9,
    "down": -18.0
  },
  "normalNed": {
    "north": 0.0,
    "east": 0.1,
    "down": -0.99
  },
  "penetrationDepth": 0.25,
  "collisionTimeNanos": 1234567890,
  "impactSpeedMps": 8.5,
  "severity": "warning",
  "recommendedAction": "hold",
  "source": "airsim.simGetCollisionInfo",
  "metadata": {
    "note": "Example collision event"
  }
}
```

## Payload fields

| Field | Type | Required | Description |
|---|---:|:---:|---|
| `message_id` | int | Yes | Fixed value `4103`. |
| `message_name` | string | No | `Vehicle Collision Event`. |
| `timestamp` | string | Yes | UTC ISO-8601 event publication time. |
| `eventId` | string | Yes | Unique event ID for de-duplication. |
| `aircraftId` | string | Yes | DTAM aircraft ID, e.g. `UAM0001`. |
| `airsimVehicleName` | string | No | AirSim vehicle name, e.g. `Drone1`. |
| `hasCollided` | bool | Yes | Usually `true`; `false` is reserved for explicit clear/diagnostic use. |
| `objectName` | string | No | Unreal actor/object name involved in the collision. |
| `objectId` | int | No | Unreal custom depth stencil/object ID if available, otherwise `-1`. |
| `positionNed` | object | Yes | Aircraft position in local NED meters at detection time. |
| `impactPointNed` | object | Yes | Impact point in local NED meters. |
| `normalNed` | object | Yes | Contact normal in local NED frame. |
| `penetrationDepth` | number | No | AirSim/Unreal penetration depth, meters when available. |
| `collisionTimeNanos` | integer | No | AirSim collision timestamp in nanoseconds. |
| `impactSpeedMps` | number | No | Estimated impact speed in m/s. |
| `severity` | string | No | `info`, `warning`, `critical`, or `fatal`. |
| `recommendedAction` | string | No | Recommended VehicleModule response such as `none`, `hold`, `emergency_stop`, or `abort`. |
| `source` | string | No | Collision source, e.g. `airsim.simGetCollisionInfo`. |
| `metadata` | object | No | Implementation-specific extension fields. |

`positionNed`, `impactPointNed`, and `normalNed` use this shape:

```json
{
  "north": 0.0,
  "east": 0.0,
  "down": 0.0
}
```

## Processing

- VisualizationModule polls or receives collision data from Unreal/AirSim and publishes MSG 4103 only when a collision event is detected.
- IntegrationHub records the message and forwards it according to SDK policy.
- VehicleModule consumes MSG 4103 and decides the actual flight-state response, for example hold, stop, emergency stop, or abort.
- Monitoring and SituationAwareness consumers use MSG 4103 for alerts, logs, and AI reasoning.
- High-frequency pose updates remain MSG 4001; MSG 4103 is event-driven and should be de-duplicated by `eventId` or `collisionTimeNanos`.
