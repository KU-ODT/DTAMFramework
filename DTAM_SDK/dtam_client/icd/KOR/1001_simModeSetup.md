# ICD - 시뮬레이션 모드 설정 (MSG 1001)

| 항목 | 값 |
|---|---|
| Message ID | `1001` |
| Message Name | Sim Mode Setup |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON (UTF-8) |
| 주기 | 이벤트 기반 |

## 1. 최상위 구조

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "operationMode": "<single | traffic | integrated>",
  "singleFlight": { "...": "single/integrated 모드에서 필수" },
  "traffic": { "...": "traffic/integrated 모드에서 필수" }
}
```

## 2. 최상위 필드

| 필드 | 타입 | 값 / 패턴 | 설명 |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | UTC 송신 시각 |
| `operationMode` | str | `single` / `traffic` / `integrated` | 운용 모드 |

## 3. 모드별 블록

| 모드 | `singleFlight` | `traffic` |
|---|---|---|
| `single` | 필수 | 금지 |
| `traffic` | 금지 | 필수 |
| `integrated` | 필수 | 필수 |

## 4. singleFlight

`singleFlight`는 `single`, `integrated` 모드에서만 포함한다. 주 비행체의 동역학 모델과 비행체 제어방식은 이 블록에서 함께 설정한다.

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
| `vehicleSimType.mainVehicleController` | str | `Joystick` / `Keyboard` / `Autopilot` | 주 비행체 제어방식 |

## 5. traffic

```json
"traffic": {
  "trafficScenario": "<low | middle | high | customed>"
}
```

| 경로 | 타입 | 허용 값 | 설명 |
|---|---|---|---|
| `trafficScenario` | str | `low` / `middle` / `high` / `customed` | 교통 시나리오 |

## 6. 예시

### 6.1 single

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "operationMode": "single",
  "singleFlight": {
    "vehicleSimType": {
      "dynamics": "multirotor",
      "mainVehicleController": "Joystick"
    }
  }
}
```

### 6.2 traffic

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "operationMode": "traffic",
  "traffic": {
    "trafficScenario": "middle"
  }
}
```

### 6.3 integrated

```json
{
  "timestamp": "2026-04-15T03:01:00.123Z",
  "operationMode": "integrated",
  "singleFlight": {
    "vehicleSimType": {
      "dynamics": "highFidelity",
      "mainVehicleController": "Autopilot"
    }
  },
  "traffic": {
    "trafficScenario": "high"
  }
}
```

## 7. 검증 정책

- 누락, 타입 불일치, enum 불일치 -> 오류 (`ok=false`)
- 모드별 필수/금지 블록 위반 -> 오류
- `singleFlight.vehicleSimType.mainVehicleController`는 MSG 1002에 포함하지 않는다.
