# ICD - Simulation Setup (MSG 1002)

| Item | Value |
|---|---|
| Message ID | `1002` |
| Message Name | Simulation Setup |
| Transport | WebSocket (`/ws/dtam`) |
| Encoding | JSON (UTF-8) |
| Rate | Event-based / user action |

## 1. Top-Level Layout

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "playbackSpeed": <1 | 2 | 4 | 8>,
  "playState": "<play | pause | reset>",
  "weatherEffect": {
    "precipitation": { "type": "...", "intensity": 0.0 },
    "fog": { "intensity": 0.0 }
  },
  "wind": {
    "grade": "<normal | warning | serious>",
    "gust": { "lat": 0.0, "lon": 0.0, "radius": 0.0 }
  }
}
```

MSG 1002 controls playback, weather, and wind only.

## 2. Top-Level Fields

| Field | Type | Value / Range | Description |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | Send time |
| `playbackSpeed` | int | `1` / `2` / `4` / `8` | Playback speed multiplier |
| `playState` | str | `play` / `pause` / `reset` | Playback state |

## 3. weatherEffect

| Path | Type | Value / Range | Description |
|---|---|---|---|
| `precipitation.type` | str | `none` / `rainy` / `snow` | Precipitation type |
| `precipitation.intensity` | float | 0.0 ~ 1.0, 0.1 step | Must be 0 when type is `none` |
| `fog.intensity` | float | 0.0 ~ 1.0, 0.1 step | Fog intensity |

## 4. wind

| Path | Type | Value / Range | Description |
|---|---|---|---|
| `grade` | str | `normal` / `warning` / `serious` | Wind grade |
| `gust` | dict | optional | Gust area |
| `gust.lat` | float | -90 ~ 90 deg | Latitude |
| `gust.lon` | float | -180 ~ 180 deg | Longitude |
| `gust.radius` | float | 0 ~ 50000 m | Gust radius |

## 5. Examples

### 5.1 Clear and paused

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "playbackSpeed": 1,
  "playState": "pause",
  "weatherEffect": {
    "precipitation": { "type": "none", "intensity": 0.0 },
    "fog": { "intensity": 0.0 }
  },
  "wind": { "grade": "normal" }
}
```

### 5.2 Rain, 2x, with gust

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "playbackSpeed": 2,
  "playState": "play",
  "weatherEffect": {
    "precipitation": { "type": "rainy", "intensity": 0.7 },
    "fog": { "intensity": 0.4 }
  },
  "wind": {
    "grade": "warning",
    "gust": { "lat": 37.52, "lon": 126.97, "radius": 800.0 }
  }
}
```

## 6. Validation Policy

- Missing, type, enum, or range violation -> error (`ok=false`)
- 0.1 step violation for intensity fields -> error
- `precipitation.type=none` forces `intensity=0`
- `wind.gust` is optional; when present, all 3 gust fields are required
