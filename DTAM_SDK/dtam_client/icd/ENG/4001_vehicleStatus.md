# ICD — Vehicle Status (MSG 4001)

| Item | Value |
|---|---|
| Message ID | `4001` |
| Message Name | Vehicle Status |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON (UTF-8) |
| Rate | Sender discretion |

## 1. Top-Level Layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "<VEHICLE_ID_1>": { "...": "..." },
  "<VEHICLE_ID_2>": { "...": "..." }
}
```

- `timestamp` is mandatory.
- All other top-level keys are vehicle IDs.
- Number of vehicles is variable and must be greater than or equal to 1.

### 1.1 Vehicle ID Rule

- Regex: `^[A-Z]{2,8}\d{4}$`
- Example: `UAM0001`

### 1.2 Timestamp

- Format: `YYYY-MM-DDTHH:MM:SS.sssZ`
- Time base: UTC

## 2. Per-Vehicle Structure

```json
{
  "currentWaypointId": "<FLIGHT_PLAN_NUMBER>-<SEQ | VERTIPORT-GATE>",
  "position": { "...": "..." },
  "attitude": { "...": "..." },
  "actuator": { "...": "..." },
  "propulsion": { "...": "..." },
  "gps": { "...": "..." },
  "imu": { "...": "..." },
  "barometer": { "...": "..." }
}
```

### 2.0 currentWaypointId

Identifies the waypoint the vehicle is currently heading toward. Linked to MSG 3001 `flightPlanNumber`.

| Field | Type | Pattern | Description |
|---|---|---|---|
| `currentWaypointId` | str | `^\d+-(\d+\|[A-Za-z0-9]+-[A-Za-z0-9]+)$` | Current target waypoint |

**Value formats:**

| Situation | Format | Example | Meaning |
|---|---|---|---|
| En-route segment | `{flightPlanNumber}-{seq}` | `1201-5` | Heading to enRoute seq 5 of plan 1201 |
| Departure vertiport | `{flightPlanNumber}-{vertiport}-{gate}` | `1201-Yeouido-G3` | At Yeouido gate G3 of plan 1201 |
| Arrival vertiport | `{flightPlanNumber}-{vertiport}-{gate}` | `1201-Jamsil-G8` | Heading to Jamsil gate G8 of plan 1201 |

### 2.1 position (NED)

`position` is a local NED coordinate. In mission replay mode, Air Mobility uses
the first emitted trajectory point as the replay origin, so the first `4001`
sample starts at approximately `{ "north": 0, "east": 0, "down": 0 }`.
AirSim/Unreal spawn coordinates are not added to this field.

| Field | Type | Unit | Range | Description |
|---|---|---:|---:|---|
| `north` | float | m | -10000 ~ 10000 | North position |
| `east` | float | m | -10000 ~ 10000 | East position |
| `down` | float | m | -5000 ~ 500 | Down position, negative means altitude above origin |

### 2.2 attitude

| Field | Type | Unit | Range | Description |
|---|---|---:|---:|---|
| `roll` | float | rad | -π ~ π | Roll angle |
| `pitch` | float | rad | -π/2 ~ π/2 | Pitch angle |
| `yaw` | float | rad | -π ~ π | Yaw angle |

### 2.3 actuator

| Field | Type | Unit | Range | Description |
|---|---|---:|---:|---|
| `tilt_left` | float | ratio | 0.0 ~ 1.0 | Left tilt command/state |
| `tilt_right` | float | ratio | 0.0 ~ 1.0 | Right tilt command/state |
| `aileron` | float | deg | -30 ~ 30 | Aileron command/state |
| `rudder_left` | float | deg | -30 ~ 30 | Left ruddervator command/state |
| `rudder_right` | float | deg | -30 ~ 30 | Right ruddervator command/state |

### 2.4 propulsion

| Field | Type | Unit | Length | Item Range | Description |
|---|---|---:|---:|---:|---|
| `motor_rpm` | list\<float\> | rpm | 4 | 0 ~ 6000 | Motor RPM values, ordered motor 1 to motor 4 |

### 2.5 gps

| Field | Type | Unit | Range | Description |
|---|---|---:|---:|---|
| `is_valid` | bool | - | `true` / `false` | GPS validity flag |
| `fix_type` | int | - | 0 ~ 3 | GNSS fix type: 0 no fix, 1 time only, 2 2D fix, 3 3D fix |
| `latitude` | float | deg | -90 ~ 90 | WGS84 latitude |
| `longitude` | float | deg | -180 ~ 180 | WGS84 longitude |
| `altitude` | float | m | -1000 ~ 20000 | WGS84 altitude |
| `velocity_north` | float | m/s | -1000 ~ 1000 | GPS velocity in local NED north axis |
| `velocity_east` | float | m/s | -1000 ~ 1000 | GPS velocity in local NED east axis |
| `velocity_down` | float | m/s | -1000 ~ 1000 | GPS velocity in local NED down axis |
| `eph` | float | - | 0 ~ 100 | Estimated horizontal position error / dilution |
| `epv` | float | - | 0 ~ 100 | Estimated vertical position error / dilution |

### 2.6 imu

| Field | Type | Unit | Range | Description |
|---|---|---:|---:|---|
| `orientation` | object | - | quaternion normalized | IMU orientation quaternion |
| `orientation.w` | float | - | -1 ~ 1 | Quaternion W |
| `orientation.x` | float | - | -1 ~ 1 | Quaternion X |
| `orientation.y` | float | - | -1 ~ 1 | Quaternion Y |
| `orientation.z` | float | - | -1 ~ 1 | Quaternion Z |
| `angular_velocity` | object | rad/s | -100 ~ 100 | Angular velocity vector |
| `angular_velocity.x` | float | rad/s | -100 ~ 100 | Angular velocity X |
| `angular_velocity.y` | float | rad/s | -100 ~ 100 | Angular velocity Y |
| `angular_velocity.z` | float | rad/s | -100 ~ 100 | Angular velocity Z |
| `linear_acceleration` | object | m/s² | -200 ~ 200 | Linear acceleration vector |
| `linear_acceleration.x` | float | m/s² | -200 ~ 200 | Linear acceleration X |
| `linear_acceleration.y` | float | m/s² | -200 ~ 200 | Linear acceleration Y |
| `linear_acceleration.z` | float | m/s² | -200 ~ 200 | Linear acceleration Z |

### 2.7 barometer

| Field | Type | Unit | Range | Description |
|---|---|---:|---:|---|
| `altitude` | float | m | -1000 ~ 20000 | Barometric altitude |
| `pressure` | float | Pa | 10000 ~ 120000 | Air pressure |
| `qnh` | float | hPa | 800 ~ 1200 | Sea-level pressure setting |

## 3. Example

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "UAM0001": {
    "currentWaypointId": "1201-5",
    "position": {
      "north": 152.4,
      "east": -37.8,
      "down": -420.0
    },
    "attitude": {
      "roll": 0.04,
      "pitch": -0.09,
      "yaw": 1.57
    },
    "actuator": {
      "tilt_left": 0.32,
      "tilt_right": 0.31,
      "aileron": 6.5,
      "rudder_left": -2.0,
      "rudder_right": 2.0
    },
    "propulsion": {
      "motor_rpm": [2450.0, 2475.0, 2440.0, 2460.0]
    },
    "gps": {
      "is_valid": true,
      "fix_type": 3,
      "latitude": 37.241231,
      "longitude": 127.177412,
      "altitude": 420.0,
      "velocity_north": 12.5,
      "velocity_east": -1.2,
      "velocity_down": -0.4,
      "eph": 0.8,
      "epv": 1.1
    },
    "imu": {
      "orientation": {
        "w": 0.7071,
        "x": 0.0,
        "y": 0.0,
        "z": 0.7071
      },
      "angular_velocity": {
        "x": 0.01,
        "y": -0.02,
        "z": 0.03
      },
      "linear_acceleration": {
        "x": 0.12,
        "y": -0.04,
        "z": 9.78
      }
    },
    "barometer": {
      "altitude": 419.3,
      "pressure": 96422.5,
      "qnh": 1013.25
    }
  }
}
```

## 4. Validation Policy

- Missing fields -> error (`ok=false`)
- Type mismatch -> error (`ok=false`)
- Out-of-range value -> error (`ok=false`)
- Vehicle ID pattern mismatch -> error (`ok=false`)
- `propulsion.motor_rpm` length mismatch -> error (`ok=false`)
- `imu.orientation` should be normalized within implementation tolerance.
