# ICD — Scenario Setup (MSG 1003)

| Item | Value |
|---|---|
| Message ID | `1003` |
| Message Name | Scenario Setup |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON (UTF-8) |
| Rate | Event-based (once per scenario load/change) |

## 1. Overview

MSG 1003 defines the base scenario configuration data for a simulation.

It delivers operation time, vertiport information, route waypoint network, total aircraft count, and main vehicle type in a single message.

MSG 1003 does not represent individual flight plans. It provides source scenario data used for subsequent flight plan generation or simulation initialization.

## 2. Top-level layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "operationTime": { ... },
  "vertiports": [ ... ],
  "routeNetwork": { "waypoints": [ ... ] },
  "totalAircraftCount": <int>,
  "mainVehicleType": "<KP2A | JobyS4>"
}
```

### 2.1 Top-level fields

| Field | Type | Value / Range | Description |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Send time (UTC) |
| `scenarioFileName` | str | `scenarioSetup_<timestamp>.json` | File name for saving on receive |
| `operationTime` | object | - | Scenario operation time |
| `vertiports` | array | >= 1 | Vertiport list |
| `routeNetwork` | object | - | Route network |
| `totalAircraftCount` | int | 1 ~ 100000 | Total aircraft count |
| `mainVehicleType` | str | `KP2A` / `JobyS4` | Main vehicle type |

## 3. operationTime

| Field | Type | Format | Description |
|---|---|---|---|
| `startTime` | str | `HH:MM:SS` | Operation start time |
| `endTime` | str | `HH:MM:SS` | Operation end time |

## 4. vertiports

| Field | Type | Unit | Range | Description |
|---|---|---|---|---|
| `name` | str | - | non-empty | Vertiport name |
| `class` | str | - | `port` / `hub` | Vertiport class |
| `lat` | float | deg | -90 ~ 90 | Latitude |
| `lon` | float | deg | -180 ~ 180 | Longitude |
| `angleDegrees` | float | deg | 0 ~ 360 | Reference angle |

## 5. routeNetwork

| Field | Type | Unit | Range | Description |
|---|---|---|---|---|
| `waypointId` | str | - | `^[A-Za-z0-9_-]{1,32}$` | Waypoint ID |
| `waypointName` | str | - | non-empty | Waypoint display name |
| `lat` | float | deg | -90 ~ 90 | Latitude |
| `lon` | float | deg | -180 ~ 180 | Longitude |
| `altFt` | float | ft | 0 ~ 60000 | Altitude |
| `links` | array\<str\> | - | >= 1 | Adjacent waypoint IDs |

### 5.1 links rules

- Must reference only `waypointId` values present in the same message
- Self-reference is forbidden
- Duplicate links are forbidden

## 6. Example

```json
{
  "timestamp": "2026-04-16T10:30:00.000Z",
  "scenarioFileName": "scenarioSetup_20260416T103000000Z.json",
  "operationTime": {
    "startTime": "08:00:00",
    "endTime": "20:00:00"
  },
  "vertiports": [
    { "name": "Yeouido", "class": "port", "lat": 37.526513, "lon": 126.922845, "angleDegrees": 322.0 },
    { "name": "Jamsil",  "class": "port", "lat": 37.514368, "lon": 127.069068, "angleDegrees": 83.0 },
    { "name": "Sangam",  "class": "hub",  "lat": 37.562282, "lon": 126.890156, "angleDegrees": 38.0 }
  ],
  "routeNetwork": {
    "waypoints": [
      { "waypointId": "WP001", "waypointName": "Gayang Bridge S", "lat": 37.569391, "lon": 126.861026, "altFt": 1000.0, "links": ["WP002", "WP003"] },
      { "waypointId": "WP002", "waypointName": "Yeomchang Bridge", "lat": 37.553824, "lon": 126.875819, "altFt": 1000.0, "links": ["WP001", "WP003"] },
      { "waypointId": "WP003", "waypointName": "Mokdong Bridge",   "lat": 37.530667, "lon": 126.888262, "altFt": 1000.0, "links": ["WP002"] }
    ]
  },
  "totalAircraftCount": 20,
  "mainVehicleType": "JobyS4"
}
```

## 7. Validation policy

- Missing required field → error (`ok=false`)
- Type mismatch → error
- `operationTime.startTime >= endTime` → error
- `vertiports` length 0 → error
- `vertiports.name` duplicate → error
- `routeNetwork.waypoints` length 0 → error
- `waypointId` duplicate → error
- `links` referencing non-existent `waypointId` → error
- `links` containing self-reference → error
- `totalAircraftCount` less than 1 → error
- `mainVehicleType` outside allowed values → error

## 8. Operational notes

- MSG 1003 is source scenario data; it does not directly represent individual flights.
- `altFt` preserves the original ft unit from scenario input. Convert to m as needed for flight execution.
- This version supports a single main vehicle type. The main controller is configured by MSG 1001 at `singleFlight.vehicleSimType.mainVehicleController`.
