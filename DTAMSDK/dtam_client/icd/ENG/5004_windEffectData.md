# ICD - Wind Effect Data (MSG 5004)

| Item | Value |
|---|---|
| Message ID | 5004 |
| Message Name | Wind Effect Data |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON only |
| Direction | `operator -> server -> all modules (vehicle/visual/psu/mission/monitoring/situation_awareness)` |
| Rate | Event-based |
| DB Folder | `WindEffectData` |

> **Status: On hold (2026-06-11)** — No publisher currently exists. In the demo, wind is handled by the operator's 1002 weather selection plus the Vehicle's own wind generation. This ICD is retained as a contract for when per-vehicle wind effect sharing becomes necessary in the future.

MSG 5004 distributes per-vehicle wind effect data (no publisher at present — see the hold notice above).
When used, VehicleModule applies 5004 for dynamics wind correction (WindModel preset/localZone), Visual uses it for visualization, and PSU uses it to correct trajectory prediction.

## Payload example

```json
{
  "timestamp": "2026-06-10T09:20:00.000Z",
  "profileId": "DEMO_WIND_01",
  "windGrade": "serious",
  "windPreset": "bad",
  "windSeed": 20260610,
  "vehicleWindEffects": [
    {
      "aircraftId": "UAM0001",
      "windSpeedMps": 7.5,
      "windDirFromDeg": 270.0,
      "gustFactor": 1.3,
      "crossTrackDriftM": 120.0,
      "alongTrackDeltaMps": -2.0,
      "localZone": {
        "lat": 37.53,
        "lon": 126.98,
        "radiusM": 3000.0,
        "preset": "serious"
      }
    }
  ]
}
```

## Payload fields

| Field | Type | Unit | Range / Format | Description |
|---|---|---:|---|---|
| `timestamp` | string | - | ISO-8601 UTC, `YYYY-MM-DDTHH:MM:SS.sssZ` | Publication time |
| `profileId` | string | - | Free-form | Demo wind profile identifier |
| `windGrade` | string | - | `normal`, `warning`, `serious` | Global wind grade (same enum as MSG 1002 `wind.grade`) |
| `windPreset` | string | - | `good`, `fair`, `bad`, `serious` | WindModel intensity preset |
| `windSeed` | int | - | `>= 0` | Reproducibility seed (0 = module default) |
| `vehicleWindEffects` | array | - | >= 1 element | Per-vehicle wind effect list |
| `vehicleWindEffects[].aircraftId` | string | - | `^[A-Z]{2,8}\d{4}$` e.g. `UAM0001` | Target aircraft ID |
| `vehicleWindEffects[].windSpeedMps` | float | m/s | `>= 0` | Wind speed at the vehicle position |
| `vehicleWindEffects[].windDirFromDeg` | float | deg | `0 ~ 360` | Wind direction (direction the wind blows from, 0 = north) |
| `vehicleWindEffects[].gustFactor` | float | - | `>= 1.0` | Gust multiplier |
| `vehicleWindEffects[].crossTrackDriftM` | float | m | - | Expected cross-track drift |
| `vehicleWindEffects[].alongTrackDeltaMps` | float | m/s | - | Expected along-track speed effect (+tailwind / -headwind) |
| `vehicleWindEffects[].localZone` | object | - | optional | Local wind zone (1:1 with `WindModel.add_local_zone`) |
| `vehicleWindEffects[].localZone.lat` | float | deg | `-90 ~ 90` | Zone center latitude |
| `vehicleWindEffects[].localZone.lon` | float | deg | `-180 ~ 180` | Zone center longitude |
| `vehicleWindEffects[].localZone.radiusM` | float | m | `> 0` | Zone radius |
| `vehicleWindEffects[].localZone.preset` | string | - | `good`, `fair`, `bad`, `serious` | Wind intensity inside the zone |

## Processing

- **No publisher (on hold)** — in the demo, wind is handled by the operator's 1002 weather selection (weather dock) plus the Vehicle's own wind generation; 5004 is not published.
- IntegrationHub records 5004 and forwards it to all modules (Vehicle, Visual, PSU, Mission, Monitoring, SituationAwareness) according to the SDK forwarding policy (FORWARD_RULES). Any module needing wind data can simply override `on_wind_effect_data`.
- (When used) VehicleModule may apply 5004 for dynamics wind correction — `windPreset` maps to a WindModel preset and `localZone` maps to `WindModel.add_local_zone`.
- (When used) Visual may visualize per-vehicle wind effects from 5004.
- (When used) PSU may use 5004 to correct trajectory prediction (`crossTrackDriftM`, `alongTrackDeltaMps`, etc.) — the current demo's conflict prediction uses 4001 only.
- When `windSeed` is non-zero, the same seed must reproduce the same wind effects.
