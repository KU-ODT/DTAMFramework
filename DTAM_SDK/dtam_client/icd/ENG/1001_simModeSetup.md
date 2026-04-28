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

`singleFlight` is present only for `single` and `integrated` modes. The primary aircraft dynamics model and controller are configured together here.

```json
"singleFlight": {
  "vehicleSimType": {
    "dynamics": "<simple | multirotor | highFidelity>",
    "mainVehicleController": "<Joystick | Keyboard | Autopilot>"
  }
}
```

| Path | Type | Allowed Values | Description |
|---|---|---|---|
| `vehicleSimType.dynamics` | str | `simple` / `multirotor` / `highFidelity` | Dynamics model |
| `vehicleSimType.mainVehicleController` | str | `Joystick` / `Keyboard` / `Autopilot` | Main aircraft controller |

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
      "dynamics": "multirotor",
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

## 7. Validation Policy

- Missing, type mismatch, enum mismatch -> error (`ok=false`)
- Mode-dependent required/forbidden block violation -> error
- `singleFlight.vehicleSimType.mainVehicleController` is not part of MSG 1002.
