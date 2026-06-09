# ICD - Sim Mode Setup (MSG 1001)

| Item | Value |
|---|---|
| Message ID | `1001` |
| Message Name | Sim Mode Setup |
| Transport | UDP |
| Encoding | JSON (UTF-8) |
| Rate | Event-based |

## 1. Top-Level Layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "operationMode": "<single | traffic>",
  "singleFlight": { "...": "required only for single mode" }
}
```

## 2. Top-Level Fields

| Field | Type | Value / Pattern | Description |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Send time in UTC |
| `operationMode` | str | `single` / `traffic` | Operation mode |

## 3. Mode-Dependent Blocks

| Mode | `singleFlight` | `traffic` |
|---|---|---|
| `single` | Required | Forbidden |
| `traffic` | Forbidden | Forbidden |

Traffic Sim mode has no additional input fields. Traffic density, traffic scenario, and other Traffic Sim setup values are not included in MSG 1001.

## 4. singleFlight

`singleFlight` is present only for `single` mode. The single aircraft dynamics model and controller are configured together here.

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
| `vehicleSimType.mainVehicleController` | str | `Joystick` / `Keyboard` / `Autopilot` | Aircraft controller |

## 5. Examples

### 5.1 single

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "operationMode": "single",
  "singleFlight": {
    "vehicleSimType": {
      "dynamics": "multirotor",
      "mainVehicleController": "Keyboard"
    }
  }
}
```

### 5.2 traffic

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "operationMode": "traffic"
}
```

## 6. Validation Policy

- Missing, type mismatch, enum mismatch -> error (`ok=false`)
- `single` mode without `singleFlight` -> error
- `single` mode with a `traffic` block -> error
- `traffic` mode with a `singleFlight` or `traffic` block -> error
- `singleFlight.vehicleSimType.mainVehicleController` is not part of MSG 1002.
