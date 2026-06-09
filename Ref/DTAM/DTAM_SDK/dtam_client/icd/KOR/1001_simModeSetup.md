# ICD - 시뮬레이션 모드 설정 (MSG 1001)

| 항목 | 값 |
|---|---|
| Message ID | `1001` |
| Message Name | Sim Mode Setup |
| 전송 방식 | UDP |
| 인코딩 | JSON (UTF-8) |
| 주기 | 이벤트 기반 |

## 1. 최상위 구조

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "operationMode": "<single | traffic>",
  "singleFlight": { "...": "single 모드에서만 필수" }
}
```

## 2. 최상위 필드

| 필드 | 타입 | 값 / 패턴 | 설명 |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | UTC 송신 시각 |
| `operationMode` | str | `single` / `traffic` | 운용 모드 |

## 3. 모드별 블록

| 모드 | `singleFlight` | `traffic` |
|---|---|---|
| `single` | 필수 | 금지 |
| `traffic` | 금지 | 금지 |

`traffic` 모드는 별도 입력값을 받지 않는다. 교통 밀도, 교통 시나리오 등 Traffic Sim 전용 설정값은 MSG 1001 ICD payload에 포함하지 않는다.

## 4. singleFlight

`singleFlight`는 `single` 모드에서만 포함한다. 단일 비행체의 동역학 모델과 제어방식을 이 블록에서 설정한다.

```json
"singleFlight": {
  "vehicleSimType": {
    "dynamics": "<simple | multirotor | highFidelity>",
    "mainVehicleController": "<Joystick | Keyboard | Autopilot>"
  }
}
```

| 경로 | 타입 | 허용 값 | 설명 |
|---|---|---|---|
| `vehicleSimType.dynamics` | str | `simple` / `multirotor` / `highFidelity` | 동역학 모델 |
| `vehicleSimType.mainVehicleController` | str | `Joystick` / `Keyboard` / `Autopilot` | 비행체 제어방식 |

## 5. 예시

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

## 6. 검증 정책

- 누락, 타입 불일치, enum 불일치 -> 오류 (`ok=false`)
- `single` 모드에서 `singleFlight` 누락 -> 오류
- `single` 모드에서 `traffic` 블록 포함 -> 오류
- `traffic` 모드에서 `singleFlight` 또는 `traffic` 블록 포함 -> 오류
- `singleFlight.vehicleSimType.mainVehicleController`는 MSG 1002에 포함하지 않는다.
