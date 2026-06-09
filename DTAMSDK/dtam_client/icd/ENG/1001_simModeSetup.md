# ICD - Sim Mode Setup (MSG 1001)

| Item | Value |
|---|---|
| Message ID | `1001` |
| Message Name | Sim Mode Setup |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON (UTF-8) |
| Rate | Event-based |

## 1. Top-Level Layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "operationMode": "<single | traffic | integrated>",
  "singleFlight": { "...": "required for single/integrated" },
  "traffic": { "...": "required for traffic/integrated" }
}
```

## 2. Top-Level Fields

| Field | Type | Value / Pattern | Description |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Send time in UTC |
| `operationMode` | str | `single` / `traffic` / `integrated` | Operation mode |

## 3. Mode-Dependent Blocks

| Mode | `singleFlight` | `traffic` |
|---|---|---|
| `single` | Required | Forbidden |
| `traffic` | Forbidden | Required |
| `integrated` | Required | Required |

## 4. singleFlight

`singleFlight` is present only for `single` and `integrated` modes. The common/default aircraft dynamics model and controller are configured here. Each mission entry may optionally override `dynamics` and/or `mainVehicleController`; when omitted, the common value is used.

```json
"singleFlight": {
  "vehicleSimType": {
    "dynamics": "<simple | highFidelity>",
    "mainVehicleController": "<Joystick | Keyboard | Autopilot>"
  }
}
```

| Path | Type | Allowed Values | Description |
|---|---|---|---|
| `vehicleSimType.dynamics` | str | `simple` / `highFidelity` | Common/default dynamics model. `simple` = Simple Dynamics, `highFidelity` = High Fidelity : KP-2A |
| `vehicleSimType.mainVehicleController` | str | `Joystick` / `Keyboard` / `Autopilot` | Common/default aircraft controller |
| `missionPlanning.missions[].vehicleSimType.dynamics` | str | `simple` / `highFidelity` | Optional per-aircraft dynamics override; inherits common value when omitted |
| `missionPlanning.missions[].vehicleSimType.mainVehicleController` | str | `Joystick` / `Keyboard` / `Autopilot` | Optional per-aircraft controller override; inherits common value when omitted |

## 5. traffic

```json
"traffic": {
  "trafficScenario": "<low | middle | high | customed>"
}
```

| Path | Type | Allowed Values | Description |
|---|---|---|---|
| `trafficScenario` | str | `low` / `middle` / `high` / `customed` | Traffic scenario |

## 6. Examples

### 6.1 single

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "operationMode": "single",
  "singleFlight": {
    "vehicleSimType": {
      "dynamics": "simple",
      "mainVehicleController": "Joystick"
    }
  }
}
```

### 6.2 traffic

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "operationMode": "traffic",
  "traffic": {
    "trafficScenario": "middle"
  }
}
```

### 6.3 integrated

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "operationMode": "integrated",
  "singleFlight": {
    "vehicleSimType": {
      "dynamics": "highFidelity",
      "mainVehicleController": "Autopilot"
    }
  },
  "traffic": {
    "trafficScenario": "high"
  }
}
```


### 6.4 single with per-aircraft dynamics/controller overrides

```json
{
  "timestamp": "2026-05-08T08:30:00.000Z",
  "operationMode": "single",
  "singleFlight": {
    "vehicleSimType": {
      "dynamics": "simple",
      "mainVehicleController": "Autopilot"
    },
    "missionPlanning": {
      "missions": [
        {
          "aircraftName": "UAM 1",
          "departureName": "DEP",
          "arrivalName": "ARR",
          "vehicleSimType": { "dynamics": "highFidelity", "mainVehicleController": "Joystick" }
        },
        {
          "aircraftName": "UAM 2",
          "departureName": "DEP",
          "arrivalName": "ARR"
        }
      ]
    }
  }
}
```

In this example, `UAM 1` uses High Fidelity : KP-2A with `Joystick`; `UAM 2` has no override and therefore uses the common `simple` dynamics and `Autopilot` controller.

## 7. Validation Policy

- Missing, type mismatch, enum mismatch -> error (`ok=false`)
- Mode-dependent required/forbidden block violation -> error
- `singleFlight.vehicleSimType.mainVehicleController` is not part of MSG 1002.
- Per-aircraft dynamics/controller override is optional. If present, it must use the same enums as the common settings.
- Supported dynamics values are only `simple` (Simple Dynamics) and `highFidelity` (High Fidelity : KP-2A).
