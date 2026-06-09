# ICD - 비행체 충돌 이벤트 (MSG 4103)

| 항목 | 값 |
|---|---|
| Message ID | 4103 |
| Message Name | Vehicle Collision Event |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON only |
| 방향 | `visual -> server -> vehicle/monitoring/situation_awareness` |
| 주기 | 이벤트 기반 |
| DB Folder | `VehicleCollisionEvent` |

MSG 4103은 VisualizationModule이 Unreal/AirSim에서 감지한 충돌 정보를 DTAM 서버로 보고하는 이벤트 메시지입니다.
Unreal/AirSim은 충돌 감지자이며, 충돌 후 실제 비행 상태를 어떻게 바꿀지는 VehicleModule이 최종 결정합니다.

## Payload 예시

```json
{
  "message_id": 4103,
  "message_name": "Vehicle Collision Event",
  "timestamp": "2026-05-16T15:30:00.000Z",
  "eventId": "COL-UAM0001-000001",
  "aircraftId": "UAM0001",
  "airsimVehicleName": "Drone1",
  "hasCollided": true,
  "objectName": "ObstacleActor_01",
  "objectId": -1,
  "positionNed": {
    "north": 120.3,
    "east": -55.1,
    "down": -18.2
  },
  "impactPointNed": {
    "north": 120.1,
    "east": -54.9,
    "down": -18.0
  },
  "normalNed": {
    "north": 0.0,
    "east": 0.1,
    "down": -0.99
  },
  "penetrationDepth": 0.25,
  "collisionTimeNanos": 1234567890,
  "impactSpeedMps": 8.5,
  "severity": "warning",
  "recommendedAction": "hold",
  "source": "airsim.simGetCollisionInfo",
  "metadata": {
    "note": "Example collision event"
  }
}
```

## Payload 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `message_id` | int | O | 고정값 `4103`. |
| `message_name` | string | - | `Vehicle Collision Event`. |
| `timestamp` | string | O | UTC ISO-8601 이벤트 발행 시각. |
| `eventId` | string | O | 중복 제거를 위한 충돌 이벤트 고유 ID. |
| `aircraftId` | string | O | DTAM 비행체 ID. 예: `UAM0001`. |
| `airsimVehicleName` | string | - | AirSim vehicle name. 예: `Drone1`. |
| `hasCollided` | bool | O | 보통 `true`; `false`는 명시적 clear/진단용으로 예약. |
| `objectName` | string | - | 충돌 대상 Unreal actor/object 이름. |
| `objectId` | int | - | Unreal custom depth stencil/object ID. 없으면 `-1`. |
| `positionNed` | object | O | 충돌 감지 시점의 비행체 위치, local NED meter. |
| `impactPointNed` | object | O | 충돌 지점, local NED meter. |
| `normalNed` | object | O | 접촉면 normal, local NED frame. |
| `penetrationDepth` | number | - | AirSim/Unreal penetration depth. 가능한 경우 meter 기준. |
| `collisionTimeNanos` | integer | - | AirSim 충돌 timestamp, nanosecond. |
| `impactSpeedMps` | number | - | 추정 충돌 속도, m/s. |
| `severity` | string | - | `info`, `warning`, `critical`, `fatal`. |
| `recommendedAction` | string | - | VehicleModule 권장 반응. `none`, `hold`, `emergency_stop`, `abort` 등. |
| `source` | string | - | 충돌 정보 원천. 예: `airsim.simGetCollisionInfo`. |
| `metadata` | object | - | 구현별 확장 필드. |

`positionNed`, `impactPointNed`, `normalNed`는 다음 형식을 사용합니다.

```json
{
  "north": 0.0,
  "east": 0.0,
  "down": 0.0
}
```

## 처리 방식

- VisualizationModule은 Unreal/AirSim 충돌 정보를 polling 또는 이벤트 방식으로 수집하고, 충돌이 감지된 경우에만 MSG 4103을 발행합니다.
- IntegrationHub는 4103을 기록하고 SDK forwarding policy에 따라 VehicleModule, Monitoring, SituationAwareness로 전달합니다.
- VehicleModule은 4103을 수신한 뒤 hold, stop, emergency stop, abort 등 실제 비행 상태 반응을 결정합니다.
- Monitoring과 SituationAwareness는 4103을 경고 표시, 로그, AI 판단 근거로 사용합니다.
- 고주기 비행체 위치/상태는 기존 MSG 4001을 유지하고, MSG 4103은 이벤트 기반으로만 사용합니다.
- 동일 충돌의 중복 처리는 `eventId` 또는 `collisionTimeNanos` 기준으로 수행하는 것을 권장합니다.
