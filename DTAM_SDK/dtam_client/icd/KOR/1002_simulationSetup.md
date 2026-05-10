# ICD - 시뮬레이션 설정 (MSG 1002)

| 항목 | 값 |
|---|---|
| Message ID | `1002` |
| Message Name | Simulation Setup |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON (UTF-8) |
| 주기 | 이벤트 기반 / 사용자 조작 |

## 1. 최상위 구조

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

MSG 1002는 재생, 기상, 바람만 제어한다.

## 2. 최상위 필드

| 필드 | 타입 | 값 / 범위 | 설명 |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | 송신 시각 |
| `playbackSpeed` | int | `1` / `2` / `4` / `8` | 재생 배속 |
| `playState` | str | `play` / `pause` / `reset` | 재생 상태 |

## 3. weatherEffect

| 경로 | 타입 | 값 / 범위 | 설명 |
|---|---|---|---|
| `precipitation.type` | str | `none` / `rainy` / `snow` | 강수 유형 |
| `precipitation.intensity` | float | 0.0 ~ 1.0, 0.1 step | `type=none`일 때 반드시 0 |
| `fog.intensity` | float | 0.0 ~ 1.0, 0.1 step | 안개 강도 |

## 4. wind

| 경로 | 타입 | 값 / 범위 | 설명 |
|---|---|---|---|
| `grade` | str | `normal` / `warning` / `serious` | 바람 등급 |
| `gust` | dict | optional | 돌풍/국지 바람 영역 |
| `gust.lat` | float | -90 ~ 90 deg | 위도 |
| `gust.lon` | float | -180 ~ 180 deg | 경도 |
| `gust.radius` | float | 0 ~ 50000 m | 반경 |

## 5. 예시

### 5.1 맑음 / 정지

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

### 5.2 비 / 2배속 / 돌풍 포함

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

## 6. 검증 정책

- 누락, 타입, enum, 범위 위반 -> 오류 (`ok=false`)
- 강도 필드 0.1 step 위반 -> 오류
- `precipitation.type=none`이면 `intensity=0`
- `wind.gust`는 선택 필드이나, 존재하면 gust 3개 필드는 모두 필수
