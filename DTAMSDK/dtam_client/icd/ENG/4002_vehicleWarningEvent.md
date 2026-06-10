# ICD - Vehicle Warning Event (MSG 4002)

| Item | Value |
|---|---|
| Message ID | 4002 |
| Message Name | Vehicle Warning Event |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON only |
| Direction | `vehicle -> server -> monitoring/situation_awareness` |
| Rate | Event-based |
| DB Folder | `VehicleWarningEvent` |

MSG 4002 reports an anomaly detected by VehicleModule's internal diagnostics on subsystems such as battery, motor, GPS, or IMU.
VehicleModule is the authority that decides when to raise a warning, while Monitoring and SituationAwareness consumers use the event for operator alerts, situational analysis, and statistics.

## Payload example

```json
{
  "messageId": 4002,
  "messageName": "Vehicle Warning Event",
  "timestamp": "2026-06-09T12:00:00.000Z",
  "eventId": "WARN-UAM0001-20260609-0001",
  "vehicleId": "UAM0001",
  "category": "energy",
  "subsystem": "battery",
  "eventType": "LOW_BATTERY",
  "severity": "warning",
  "status": "active",
  "detectedValue": {
    "battery_pct": 18.5,
    "state_of_charge_pct": 17.9
  },
  "threshold": {
    "warning_pct": 20.0,
    "critical_pct": 10.0
  },
  "recommendedAction": "return_to_base",
  "availableDistance": 12500.0,
  "description": "Battery below 20% — RTB recommended."
}
```

## Payload fields

| Field | Type | Unit | Range / Format | Description |
|---|---|---:|---|---|
| `messageId` | int | - | e.g., `4002` | Warning event message ID |
| `messageName` | string | - | `"Vehicle Warning Event"` | Message name |
| `timestamp` | string | - | ISO-8601 UTC, `YYYY-MM-DDTHH:MM:SS.sssZ` | Warning detection time |
| `eventId` | string | - | `WARN-{vehicleId}-{YYYYMMDD}-{SEQ}` | Unique warning event ID |
| `vehicleId` | string | - | `^[A-Z]{2,8}\d{4}$` e.g., `UAM0001` | Vehicle ID where the warning occurred |
| `category` | string | - | e.g., `energy`, `flight`, `navigation`, `sensor`, `collision` | Warning category |
| `subsystem` | string | - | e.g., `battery`, `motor`, `gps`, `imu`, `barometer` | Faulty subsystem |
| `eventType` | string | - | e.g., `LOW_BATTERY`, `BATTERY_OVERHEAT`, `BATTERY_VOLTAGE_LOW` | Detailed warning type |
| `severity` | string | - | `info`, `warning`, `critical`, `fatal` | Severity level |
| `status` | string | - | `active`, `cleared`, `updated` | Warning state |
| `detectedValue` | object | - | - | Actual measured value used for detection |
| `detectedValue.battery_pct` | float | % | `0.0 ~ 100.0` | Measured battery percentage |
| `detectedValue.state_of_charge_pct` | float | % | `0.0 ~ 100.0` | Measured SOC |
| `threshold` | object | - | - | Threshold value used for detection |
| `threshold.warning_pct` | float | % | `0.0 ~ 100.0` | Warning threshold |
| `threshold.critical_pct` | float | % | `0.0 ~ 100.0` | Critical threshold |
| `recommendedAction` | string | - | e.g., `continue`, `return_to_base`, `emergency_landing`, `land_immediately` | Recommended action |
| `availableDistance` | float | m | `>= 0.0` | Estimated remaining flight distance under current battery state |
| `description` | string | - | Free text | Human-readable description |

## Processing

- VehicleModule emits MSG 4002 only when internal diagnostics on battery / motor / GPS / IMU / barometer cross a defined threshold.
- IntegrationHub records the message and forwards it according to SDK policy.
- Monitoring (OperationModule) consumes MSG 4002 for operator alerts, dashboard display, and logs.
- SituationAwareness may use MSG 4002 for fleet-level state aggregation, AI reasoning, and mission re-planning triggers.
- High-frequency pose updates remain MSG 4001; MSG 4002 is event-driven and should be de-duplicated by `eventId`.
- Updates to the same situation (e.g., a low-battery warning getting worse) keep the same `eventId` with `status="updated"`. Clearing is signalled with `status="cleared"` to enable dismissal in dashboards.
