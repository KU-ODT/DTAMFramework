# ICD - Camera Control Command (MSG 5002)

| Item | Value |
|---|---|
| Message ID | `5002` |
| Message Name | Camera Control Command |
| Transport | WebSocket (`/ws/dtam`) |
| Direction | operator/server -> visual |
| Rate | Event driven |

## Purpose

MSG 5002 carries visualization camera control commands through the DTAM server. It replaces direct Air Mobility -> Visualization REST calls for joystick hat camera pan/zoom in the normal path.

## Payload

```json
{
  "timestamp": "2026-04-29T12:00:00.000Z",
  "aircraftId": "UAM0001",
  "vehicleName": "",
  "cameraName": "front_center",
  "source": "joystick",
  "action": "adjust",
  "sequence": 1,
  "yawDeltaDeg": 6.0,
  "pitchDeltaDeg": 0.0,
  "focalLengthDelta": 0.0
}
```

## Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `timestamp` | string | yes | UTC ISO-8601 timestamp. |
| `aircraftId` | string | yes | DTAM aircraft ID used for vehicle-map lookup. |
| `vehicleName` | string | no | Direct AirSim vehicle name. Empty means VM resolves it from `aircraftId`. |
| `cameraName` | string | no | AirSim camera name. Default `front_center`. |
| `source` | string | no | `joystick`, `keyboard`, `api`, or `script`. |
| `action` | string | no | Currently `adjust`; reserved for future commands. |
| `sequence` | int | no | Monotonic sender-side sequence. |
| `yawDeltaDeg` | float | no | Camera yaw delta in degrees. |
| `pitchDeltaDeg` | float | no | Camera pitch delta in degrees. |
| `focalLengthDelta` | float | no | Focal length delta. Positive zooms in, negative zooms out. |

## Routing

- Forwarding rule: `5002 -> visual`
- Visualization resolves `aircraftId` through its vehicle map when `vehicleName` is empty.
- The VM applies the command through AirSim camera director/RPC and records the event in its manager log.
