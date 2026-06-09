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
    "dynamics": "<simple | highFidelity>",
    "mainVehicleController": "<Joystick | Keyboard | Autopilot>"
  }
}
```

| 경로 | 타입 | 허용 값 | 설명 |
|---|---|---|---|
| `vehicleSimType.dynamics` | str | `simple` / `highFidelity` | 동역학 모델 |
| `vehicleSimType.mainVehicleController` | str | `Joystick` / `Keyboard` / `Autopilot` | 주 비행체 제어방식 |
| `missionPlanning.missions[].vehicleSimType.dynamics` | str | `simple` / `highFidelity` | 개별 비행체 동역학 override; 없으면 공통 값 상속 |
| `missionPlanning.missions[].vehicleSimType.mainVehicleController` | str | `Joystick` / `Keyboard` / `Autopilot` | 개별 비행체 제어방식 override; 없으면 공통 값 상속 |

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
      "dynamics": "simple",
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


## 8. 공통/개별 비행체 Dynamics/제어방식 override

- `singleFlight.vehicleSimType.dynamics`는 전체 비행체의 공통/기본 동역학 모델이다.
- `singleFlight.vehicleSimType.mainVehicleController`는 전체 비행체의 공통/기본 제어방식이다.
- 특정 비행체만 다른 동역학 모델을 사용해야 하면 `missionPlanning.missions[].vehicleSimType.dynamics`에 개별 값을 넣는다.
- 특정 비행체만 다른 제어방식을 사용해야 하면 `missionPlanning.missions[].vehicleSimType.mainVehicleController`에 개별 값을 넣는다.
- 개별 값이 없으면 해당 비행체는 공통 제어방식을 상속한다.
- 동역학 허용 값은 `simple`(Simple Dynamics), `highFidelity`(High Fidelity : KP-2A) 두 가지이다.
- 제어방식 허용 값은 공통/개별 모두 `Joystick`, `Keyboard`, `Autopilot`이다.

```json
{
  "singleFlight": {
    "vehicleSimType": {
      "dynamics": "simple",
      "mainVehicleController": "Autopilot"
    },
    "missionPlanning": {
      "missions": [
        {
          "aircraftName": "UAM 1",
          "departureName": "잠실",
          "arrivalName": "망우",
          "vehicleSimType": { "dynamics": "highFidelity", "mainVehicleController": "Joystick" }
        },
        {
          "aircraftName": "UAM 2",
          "departureName": "성수",
          "arrivalName": "김포"
        }
      ]
    }
  }
}
```

위 예시에서 `UAM 1`은 High Fidelity : KP-2A와 `Joystick`, `UAM 2`는 개별 값이 없으므로 공통 값인 Simple Dynamics와 `Autopilot`을 사용한다.
