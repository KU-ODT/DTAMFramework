# ICD - Operator Control Input (MSG 5001)

| Item | Value |
|---|---|
| Message ID | `5001` |
| Message Name | Operator Control Input |
| Transport | WebSocket (`/ws/dtam`) |
| Direction | operator/server -> vehicle |
| Nominal Rate | 20 Hz while active |

## Purpose

MSG 5001 carries normalized keyboard, joystick, or manual API input through the DTAM server. The server stores/parses the payload and forwards it to the Air Mobility (`vehicle`) module.

## Payload

```json
{
  "timestamp": "2026-04-29T12:00:00.000Z",
  "aircraftId": "UAM0001",
  "source": "keyboard",
  "controlMode": "keyboard",
  "sequence": 1,
  "active": true,
  "axes": {
    "roll": 0.0,
    "pitch": 0.5,
    "yaw": 0.0,
    "throttle": 0.2
  },
  "buttons": [],
  "hats": [],
  "rawAxes": {}
}
```

## Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `timestamp` | string | yes | UTC ISO-8601 timestamp. |
| `aircraftId` | string | yes | Target DTAM aircraft ID, for example `UAM0001`. |
| `source` | string | yes | `keyboard`, `joystick`, `api`, or `script`. |
| `controlMode` | string | yes | `keyboard`, `joystick`, `manual`, or `mission`. |
| `sequence` | int | no | Monotonic sender-side sequence. |
| `active` | bool | no | `false` means neutral axes/stop input. |
| `axes.roll` | float | yes | Right/left command, normalized `-1.0..1.0`. |
| `axes.pitch` | float | yes | Forward/back command, normalized `-1.0..1.0`. |
| `axes.yaw` | float | yes | Yaw command, normalized `-1.0..1.0`. |
| `axes.throttle` | float | yes | Up/down command, normalized `-1.0..1.0`. |
| `buttons` | list<int> | no | Pressed joystick buttons. |
| `hats` | list<[int,int]> | no | Joystick hat states. |
| `rawAxes` | object | no | Optional raw joystick axis values before shaping. |

## Routing

- Forwarding rule: `5001 -> vehicle`
- Air Mobility applies the input to the manual kinematic dynamics and continues publishing `4001 Vehicle Status`.
- If `controlMode` is `mission`, the vehicle module returns to mission/autopilot mode and neutralizes manual input.
