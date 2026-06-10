# ICD - 비행체 경고 이벤트 (MSG 4002)

| 항목 | 값 |
|---|---|
| Message ID | 4002 |
| Message Name | Vehicle Warning Event |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON only |
| 방향 | `vehicle -> server -> monitoring/situation_awareness` |
| 주기 | 이벤트 기반 |
| DB Folder | `VehicleWarningEvent` |

MSG 4002는 VehicleModule이 자체 진단을 통해 배터리/모터/GPS/IMU 등 계통의 이상을 감지했을 때 발행하는 이벤트 메시지입니다.
VehicleModule이 경고 판단의 주체이며, Monitoring과 SituationAwareness는 4002를 운영자 알림·상황 인식·통계의 근거로 사용합니다.

## Payload 예시

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

## Payload 필드

| 필드 | 타입 | 단위 | 범위 / 형식 | 설명 |
|---|---|---:|---|---|
| `messageId` | int | - | 예: `4002` | 경고 이벤트 메시지 ID |
| `messageName` | string | - | `"Vehicle Warning Event"` | 메시지 이름 |
| `timestamp` | string | - | ISO-8601 UTC, `YYYY-MM-DDTHH:MM:SS.sssZ` | 경고 판단 시각 |
| `eventId` | string | - | `WARN-{vehicleId}-{YYYYMMDD}-{SEQ}` | 경고 이벤트 고유 ID |
| `vehicleId` | string | - | `^[A-Z]{2,8}\d{4}$` 예: `UAM0001` | 경고가 발생한 비행체 ID |
| `category` | string | - | 예: `energy`, `flight`, `navigation`, `sensor`, `collision` | 경고 대분류 |
| `subsystem` | string | - | 예: `battery`, `motor`, `gps`, `imu`, `barometer` | 이상이 발생한 세부 계통 |
| `eventType` | string | - | 예: `LOW_BATTERY`, `BATTERY_OVERHEAT`, `BATTERY_VOLTAGE_LOW` | 경고 상세 유형 |
| `severity` | string | - | `info`, `warning`, `critical`, `fatal` | 경고 심각도 |
| `status` | string | - | `active`, `cleared`, `updated` | 경고 상태 |
| `detectedValue` | object | - | - | 이상 판단에 사용된 실제 측정값 |
| `detectedValue.battery_pct` | float | % | `0.0 ~ 100.0` | 감지된 배터리 잔량 |
| `detectedValue.state_of_charge_pct` | float | % | `0.0 ~ 100.0` | 감지된 SOC 값 |
| `threshold` | object | - | - | 이상 판단 기준값 |
| `threshold.warning_pct` | float | % | `0.0 ~ 100.0` | warning 판단 기준 배터리 잔량 |
| `threshold.critical_pct` | float | % | `0.0 ~ 100.0` | critical 판단 기준 배터리 잔량 |
| `recommendedAction` | string | - | 예: `continue`, `return_to_base`, `emergency_landing`, `land_immediately` | 상위 기관 또는 운용 시스템에 권고하는 조치 |
| `availableDistance` | float | m | `>= 0.0` | 현재 배터리 상태 기준 추가 비행 가능 추정 거리 |
| `description` | string | - | 자유 문자열 | 경고 상황 설명 |

## 처리 방식

- VehicleModule은 내부 진단(배터리 / 모터 / GPS / IMU / barometer 등)에서 임계값을 넘는 이상을 감지한 경우에만 MSG 4002를 발행합니다.
- IntegrationHub는 4002를 기록하고 SDK forwarding policy에 따라 Monitoring, SituationAwareness로 전달합니다.
- Monitoring(OperationModule)은 4002를 운영자 alert/dashboard 표시 및 로그에 사용합니다.
- SituationAwareness는 4002를 fleet 단위 상태 통계, AI 판단, 임무 재계획 트리거로 사용할 수 있습니다.
- 고주기 비행체 상태는 기존 MSG 4001을 유지하고, MSG 4002는 이벤트 기반으로만 사용합니다.
- 동일 상황의 갱신(예: 같은 배터리 경고의 악화) 은 `eventId`를 유지하고 `status="updated"`로 발행합니다. 해소된 경우 `status="cleared"`로 발행해 dedup/dismiss 처리를 가능하게 합니다.
