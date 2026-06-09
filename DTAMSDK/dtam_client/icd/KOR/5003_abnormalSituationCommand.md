# 5003 Abnormal Situation Command

## 목적

운용자가 비정상 상황 또는 장애물을 서버를 통해 VisualizationModule/DT World에 주입하기 위한 명령입니다. 현재 구현 대상은 `bird_flock`(새떼 출현)이며, 추후 `drone_intruder`, `weather_cell`, `ground_obstacle` 등으로 확장할 수 있습니다.

## 통신

- Transport: WebSocket JSON (`/ws/dtam`)
- Direction: `operator -> server -> visual`
- Rate: 이벤트성, 필요 시 1회 전송
- DB Folder: `AbnormalSituationCommand`

## Payload

```json
{
  "timestamp": "2026-05-16T00:00:00.000Z",
  "commandId": "OBS-BIRD-001",
  "action": "create",
  "abnormalType": "bird_flock",
  "obstacleId": "bird_flock_001",
  "position": {
    "lat": 37.56,
    "lon": 126.98,
    "alt": 120.0
  },
  "radiusM": 800.0,
  "count": 9,
  "headingDeg": 0.0,
  "speedMps": 12.0,
  "durationSec": 0.0,
  "severity": "warning",
  "affectedAircraftIds": [],
  "metadata": {
    "source": "OperationModule",
    "assetKey": "birds_fab_fbx"
  }
}
```

## 필드

| Field | Type | Required | Description |
|---|---:|:---:|---|
| `timestamp` | string | O | ISO-8601 UTC timestamp |
| `commandId` | string | O | 명령 식별자 |
| `action` | string | O | `create`, `update`, `remove`, `clear` |
| `abnormalType` | string | O | `bird_flock` 등 비정상 상황/장애물 타입 |
| `obstacleId` | string | O | 생성/갱신/삭제 대상 장애물 ID |
| `position.lat` | number | O | 중심 위도 |
| `position.lon` | number | O | 중심 경도 |
| `position.alt` | number | O | 중심 고도, meter AMSL 기준 |
| `radiusM` | number | O | 출몰/활동 반경, meter |
| `count` | integer | O | 개체 수 |
| `headingDeg` | number | - | 초기 진행 방향 |
| `speedMps` | number | O | 평균 이동 속도 |
| `durationSec` | number | - | 0이면 명시적 삭제 전까지 유지 |
| `severity` | string | - | `info`, `warning`, `critical` |
| `affectedAircraftIds` | array[string] | - | 영향 대상 기체 ID |
| `metadata` | object | - | 구현별 확장 정보 |

