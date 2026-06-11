# ICD — DTAM Execute (MSG 2002)

| 항목 | 값 |
|---|---|
| Message ID | `2002` |
| Message Name | DTAM 실행 |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON (UTF-8) |
| 주기 | 이벤트성 |

## 1. 개요

2002는 DTAM 시뮬레이션 실행을 요청하는 메시지이다.
이전 단계에서 생성된 설정 파일명과 비행계획 폴더명을 모두 포함하여, 수신 측이 해당 파일들을 로드하고 시뮬레이션을 시작할 수 있도록 한다.

## 2. 구조

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "simModeFileName": "<SIM_MODE_FILE>",
  "simulationSetupFileName": "<SIMULATION_SETUP_FILE>",
  "scenarioFileName": "<SCENARIO_FILE>",
  "flightPlanFolderName": "<FLIGHT_PLAN_FOLDER>",
  "scenarioId": "<S1|S2|S3, optional>"
}
```

## 3. 필드 정의

| 필드 | 타입 | 설명 | 예시 |
|---|---|---|---|
| `timestamp` | str | 요청 시각 (UTC) | `2026-04-16T10:40:00.000Z` |
| `simModeFileName` | str | 1001 시뮬레이션 모드 설정 파일명 | `simModeSetup_20260416T103000000Z.json` |
| `simulationSetupFileName` | str | 1002 시뮬레이션 설정 파일명 | `simulationSetup_20260416T103000000Z.json` |
| `scenarioFileName` | str | 1003 시나리오 설정 파일명 | `scenarioSetup_20260416T103000000Z.json` |
| `flightPlanFolderName` | str | 3001 비행계획 저장 폴더명 | `FlightPlan_20260416T103500000Z` |
| `scenarioId` | str (optional) | 데모 시나리오 식별 — Vehicle 의 시나리오별 분기용 (`"S1"`\|`"S2"`\|`"S3"`). S3: 배터리 열화 프로필 + UAO 겸업 판단 무장, S2: PSU 속도 조정 재계획 시나리오 — Vehicle 측 특별 분기 없음 (1002 wind.weather 바람 적용·3003 setSpeed 수행은 표준 메시지 처리). 생략 시 일반 실행 | `S3` |

## 4. 예시

```json
{
  "timestamp": "2026-04-16T10:40:00.000Z",
  "simModeFileName": "simModeSetup_20260416T103000000Z.json",
  "simulationSetupFileName": "simulationSetup_20260416T103000000Z.json",
  "scenarioFileName": "scenarioSetup_20260416T103000000Z.json",
  "flightPlanFolderName": "FlightPlan_20260416T103500000Z"
}
```

데모 시나리오 실행 시 (`scenarioId` 포함):

```json
{
  "timestamp": "2026-04-16T10:40:00.000Z",
  "simModeFileName": "simModeSetup_20260416T103000000Z.json",
  "simulationSetupFileName": "simulationSetup_20260416T103000000Z.json",
  "scenarioFileName": "scenarioSetup_20260416T103000000Z.json",
  "flightPlanFolderName": "FlightPlan_20260416T103500000Z",
  "scenarioId": "S3"
}
```

## 5. 유효성 정책

- 필수 필드 누락 → 오류 (`ok=false`)
- 타입 불일치 → 오류
- 파일명/폴더명 빈 문자열 → 오류
- `scenarioId` 는 optional — 생략 시 일반 실행

## 6. 운용 메모

- 2002 수신 시, 수신 모듈은 4개 파일/폴더를 로드하여 시뮬레이션을 초기화한다.
- 파일 참조 순서: 1001(모드) → 1002(설정) → 1003(시나리오) → 3001(비행계획 폴더)
- `scenarioId` 는 Operation Console 이 실행 시점에 현재 데모 시나리오(S1/S2/S3)를 Vehicle 에 알리는 용도이다.
  Vehicle 은 `on_dtam_execute()` 에서 `scenarioId` 로 분기: S1 → 정상 실행, S2 → PSU 속도 조정 재계획 시나리오 — Vehicle 측 특별 분기 없음 (1002 wind.weather 바람 적용·3003 setSpeed 수행은 표준 메시지 처리), S3 → 배터리 열화 프로필 활성화 + UAO 겸업 판단 로직 무장 (UAO 역할은 별도 모듈이 아닌 VehicleModule 이 겸업).
- 생략 시 일반 실행. Vehicle 이 2002 를 이미 수신하므로 라우팅 변경 없음.
