# ICD - 바람 영향 데이터 (MSG 5004)

| 항목 | 값 |
|---|---|
| Message ID | 5004 |
| Message Name | Wind Effect Data |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON only |
| 방향 | `operator -> server -> 전 모듈 (vehicle/visual/psu/mission/monitoring/situation_awareness)` |
| 주기 | 이벤트 기반 |
| DB Folder | `WindEffectData` |

MSG 5004는 OperationModule(운영자 콘솔)의 "데모 날씨" 버튼 트리거로 발행되며, 보유한 데모 바람 프로파일을 사용해 각 기체별 바람 영향 데이터를 배포하는 메시지입니다.
VehicleModule은 dynamics 바람 보정(WindModel preset/localZone)에, Visual은 시각화에, PSU는 궤적 예측 보정에 5004를 사용합니다.

## Payload 예시

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

## Payload 필드

| 필드 | 타입 | 단위 | 범위 / 형식 | 설명 |
|---|---|---:|---|---|
| `timestamp` | string | - | ISO-8601 UTC, `YYYY-MM-DDTHH:MM:SS.sssZ` | 발행 시각 |
| `profileId` | string | - | 자유 형식 | 데모 바람 프로파일 식별자 |
| `windGrade` | string | - | `normal`, `warning`, `serious` | 전역 바람 등급 (MSG 1002 `wind.grade` 동일 enum) |
| `windPreset` | string | - | `good`, `fair`, `bad`, `serious` | WindModel 강도 프리셋 |
| `windSeed` | int | - | `>= 0` | 재현성 시드 (0 = 모듈 기본값) |
| `vehicleWindEffects` | array | - | 1개 이상 | 기체별 바람 영향 목록 |
| `vehicleWindEffects[].aircraftId` | string | - | `^[A-Z]{2,8}\d{4}$` 예: `UAM0001` | 대상 기체 ID |
| `vehicleWindEffects[].windSpeedMps` | float | m/s | `>= 0` | 기체 위치 기준 풍속 |
| `vehicleWindEffects[].windDirFromDeg` | float | deg | `0 ~ 360` | 풍향 (불어오는 방향, 0 = 북) |
| `vehicleWindEffects[].gustFactor` | float | - | `>= 1.0` | 거스트 배율 |
| `vehicleWindEffects[].crossTrackDriftM` | float | m | - | 예상 횡방향 이탈량 |
| `vehicleWindEffects[].alongTrackDeltaMps` | float | m/s | - | 예상 종방향 속도 영향 (+순풍 / -역풍) |
| `vehicleWindEffects[].localZone` | object | - | optional | 국지 바람 영역 (`WindModel.add_local_zone` 1:1) |
| `vehicleWindEffects[].localZone.lat` | float | deg | `-90 ~ 90` | 영역 중심 위도 |
| `vehicleWindEffects[].localZone.lon` | float | deg | `-180 ~ 180` | 영역 중심 경도 |
| `vehicleWindEffects[].localZone.radiusM` | float | m | `> 0` | 영역 반경 |
| `vehicleWindEffects[].localZone.preset` | string | - | `good`, `fair`, `bad`, `serious` | 영역 내 바람 강도 |

## 처리 방식

- OperationModule(운영자 콘솔)은 "데모 날씨" 버튼 트리거 시 보유한 데모 바람 프로파일을 사용해 MSG 5004를 발행합니다.
- IntegrationHub는 5004를 기록하고 SDK forwarding policy(FORWARD_RULES)에 따라 전 모듈(Vehicle, Visual, PSU, Mission, Monitoring, SituationAwareness)로 전달합니다. 바람 정보가 필요한 모듈은 `on_wind_effect_data` 를 override 하면 즉시 활용 가능합니다.
- VehicleModule은 5004를 dynamics 바람 보정에 사용합니다 — `windPreset`은 WindModel preset으로, `localZone`은 `WindModel.add_local_zone`으로 적용합니다.
- Visual은 5004를 기체별 바람 영향 시각화에 사용합니다.
- PSU는 5004를 궤적 예측 보정에 사용합니다 (`crossTrackDriftM`, `alongTrackDeltaMps` 등).
- `windSeed`가 0이 아니면 동일 시드로 동일한 바람 효과가 재현되어야 합니다.
