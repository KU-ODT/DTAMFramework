# ICD — Tactical Separation Command (MSG 3003)

| 항목 | 값 |
|---|---|
| Message ID | `3003` |
| Message Name | 전술 분리 명령 |
| 전송 방식 | WebSocket (`/ws/dtam`) |
| 인코딩 | JSON (UTF-8) |
| 방향 | `mission|psu -> server -> vehicle/mission` |
| 주기 | 이벤트성 |

## 1. 개요

3003은 운항 중인 특정 비행체에 대해 즉시 적용할 전술 행동 명령 메시지이다.
이 메시지는 판단 결과를 담는 용도가 아니라, 시뮬레이터가 실제로 수행할 행동 순서를 전달하는 용도이다.
행동은 `actions` 배열에 순차적으로 정의하며, 앞선 행동이 완료되면 다음 행동을 수행한다.

3003은 Mission 또는 PSU가 발행한다 (`mission|psu -> server`). PSU는 지속 궤적 예측으로 충돌 위험을 감지한 경우 또는 MSG 4002 긴급 상황 시 3003을 직접 발행한다.
수신자는 Vehicle(행동 수행)과 Mission(PSU 발행분 수신 — plan 정합성 추적)이다.

## 2. 최상위 구조

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "commandId": "<COMMAND_ID>",
  "aircraftId": "<AIRCRAFT_ID>",
  "reasonCode": "<REASON_CODE>",
  "actions": [ { ... }, { ... } ]
}
```

## 3. 최상위 필드

| 필드 | 타입 | 값/패턴 | 설명 |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | 명령 생성 시각 (UTC) |
| `commandId` | str | 자유 형식 (예: `TMP-20260416-011`) | 전술 명령 고유 식별자 |
| `aircraftId` | str | `^[A-Z]{2,8}\d{4}$` | 명령 대상 비행체 ID |
| `reasonCode` | str | 아래 열거형 참조 | 명령 발생 사유 코드 |
| `actions` | array | 1개 이상 | 수행할 행동 목록 (배열 순서 = 실행 순서) |

### 3.1 reasonCode 열거형

| 값 | 설명 |
|---|---|
| `LOSS_OF_SEPARATION_RISK` | 이격 거리 위험 |
| `LOCAL_CORRIDOR_BLOCKED` | 지역 회랑 차단 |
| `LOW_BATTERY` | 배터리 부족 |
| `WEATHER_AVOIDANCE` | 기상 회피 |
| `OPERATOR_OVERRIDE` | 운영자 개입 |
| `EMERGENCY_LANDING` | 비상 착륙 |

## 4. Action 공통 규칙

- `actions`는 순서대로 수행한다.
- 현재 action이 완료되면 다음 action을 수행한다.
- 동일 `aircraftId`에 대해 더 최신 `timestamp`의 3003이 수신되면, 기존 미완료 actions는 폐기하고 새 명령으로 대체한다.
- 3003은 상위 commandType 없이 actions 조합만으로 의미를 표현한다.

## 5. Action 상세 정의

### 5.1 setSpeed

```json
{ "type": "setSpeed", "targetSpeed": <float> }
```

| 필드 | 타입 | 단위 | 범위 | 설명 |
|---|---|---|---|---|
| `type` | str | - | 고정값 `setSpeed` | 액션 타입 |
| `targetSpeed` | float | m/s | 0 ~ 200 | 즉시 적용할 목표 속도 |

### 5.2 directTo

```json
{
  "type": "directTo",
  "targetLLAs": [
    { "lat": <float>, "lon": <float>, "alt": <float>, "targetSpeed": <float> }
  ]
}
```

| 필드 | 타입 | 단위 | 범위 | 설명 |
|---|---|---|---|---|
| `type` | str | - | 고정값 `directTo` | 액션 타입 |
| `targetLLAs` | array | - | 1개 이상 | 순서대로 따라갈 목표 좌표 목록 |
| `targetLLAs[].lat` | float | deg | -90 ~ 90 | 위도 |
| `targetLLAs[].lon` | float | deg | -180 ~ 180 | 경도 |
| `targetLLAs[].alt` | float | m | -500 ~ 20000 | 고도 |
| `targetLLAs[].targetSpeed` | float | m/s | 0 ~ 200 | 해당 목표점 이동 시 목표 속도 (필수) |

### 5.3 hold

```json
{
  "type": "hold",
  "holdLLA": { "lat": <float>, "lon": <float>, "alt": <float> },
  "turnDirection": "<CW | CCW>",
  "holdingRadiusM": <float>,
  "maxHoldingCount": <int>
}
```

| 필드 | 타입 | 단위 | 범위 | 설명 |
|---|---|---|---|---|
| `type` | str | - | 고정값 `hold` | 액션 타입 |
| `holdLLA.lat` | float | deg | -90 ~ 90 | 홀드 기준 위도 |
| `holdLLA.lon` | float | deg | -180 ~ 180 | 홀드 기준 경도 |
| `holdLLA.alt` | float | m | -500 ~ 20000 | 홀드 기준 고도 |
| `turnDirection` | str | - | `CW` / `CCW` | 홀드 선회 방향 |
| `holdingRadiusM` | float | m | 1 ~ 5000 | 홀드 반경 |
| `maxHoldingCount` | int | - | 0 ~ 9999 | 홀드 반복 횟수 (0 = 무제한) |

### 5.4 rejoinPlan

```json
{ "type": "rejoinPlan", "atSeq": <int> }
```

| 필드 | 타입 | 범위 | 설명 |
|---|---|---|---|
| `type` | str | 고정값 `rejoinPlan` | 액션 타입 |
| `atSeq` | int | 1 ~ 9999 | active 3001 계획에서 재합류할 `enRoute.seq` 번호 |

### 5.5 land

```json
{
  "type": "land",
  "targetLLA": { "lat": <float>, "lon": <float>, "alt": <float> },
  "vertiport": "<VERTIPORT_NAME>",
  "fatoNumber": "<FATO_ID>"
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `type` | str | ✔ | 고정값 `land` |
| `targetLLA` | object | △ | 착륙 목표 좌표 (비상착륙/임의 지점) |
| `vertiport` | str | △ | 착륙 대상 버티포트 이름 |
| `fatoNumber` | str | ✖ | 착륙 대상 FATO 번호 |

- `targetLLA`와 `vertiport` 중 최소 하나는 있어야 한다.
- `targetLLA`만 있으면 임의 지점/비상착륙으로 해석.
- `vertiport`만 있으면 해당 버티포트 착륙으로 해석.

## 6. 실행 규칙

- `actions` 배열은 정의된 순서대로 실행한다.
- `setSpeed` 후 `directTo`를 두면, 먼저 속도 변경 후 경로를 수행한다.
- `directTo`의 `targetLLAs`는 배열 순서대로 따라간다.
- `hold` 후 `rejoinPlan`을 두면, 홀드 종료 후 active 3001 계획의 지정 seq로 재합류한다.
- `maxHoldingCount`가 0인 `hold`는 새 3003 명령 도착 전까지 계속 유지할 수 있다.
- 동일 `aircraftId`에 대해 새 3003 명령이 수신되면, 이전 명령의 남은 action은 취소된다.

## 7. 예시

### 7.1 감속 후 2회 홀드 후 계획 복귀

```json
{
  "timestamp": "2026-04-16T09:06:12.000Z",
  "commandId": "TMP-20260416-011",
  "aircraftId": "UAM0004",
  "reasonCode": "LOSS_OF_SEPARATION_RISK",
  "actions": [
    { "type": "setSpeed", "targetSpeed": 18.0 },
    {
      "type": "hold",
      "holdLLA": { "lat": 37.52300, "lon": 126.93600, "alt": 180.0 },
      "turnDirection": "CW", "holdingRadiusM": 120.0, "maxHoldingCount": 2
    },
    { "type": "rejoinPlan", "atSeq": 9 }
  ]
}
```

### 7.2 임시 우회 후 계획 복귀

```json
{
  "timestamp": "2026-04-16T09:11:40.000Z",
  "commandId": "TMP-20260416-012",
  "aircraftId": "UAM0004",
  "reasonCode": "LOCAL_CORRIDOR_BLOCKED",
  "actions": [
    { "type": "setSpeed", "targetSpeed": 18.0 },
    {
      "type": "directTo",
      "targetLLAs": [
        { "lat": 37.52270, "lon": 126.93680, "alt": 200.0, "targetSpeed": 25.0 },
        { "lat": 37.52090, "lon": 126.94410, "alt": 200.0, "targetSpeed": 23.0 },
        { "lat": 37.51860, "lon": 126.95240, "alt": 180.0, "targetSpeed": 23.0 }
      ]
    },
    { "type": "rejoinPlan", "atSeq": 11 }
  ]
}
```

### 7.3 대체 버티포트 착륙

```json
{
  "timestamp": "2026-04-16T09:18:05.000Z",
  "commandId": "TMP-20260416-015",
  "aircraftId": "UAM0011",
  "reasonCode": "LOW_BATTERY",
  "actions": [
    {
      "type": "directTo",
      "targetLLAs": [
        { "lat": 37.55520, "lon": 126.97010, "alt": 120.0, "targetSpeed": 20.0 }
      ]
    },
    { "type": "land", "vertiport": "SeoulStation-Alt", "fatoNumber": "EF1" }
  ]
}
```

### 7.4 임의 지점 비상착륙

```json
{
  "timestamp": "2026-04-16T09:20:10.000Z",
  "commandId": "TMP-20260416-016",
  "aircraftId": "UAM0013",
  "reasonCode": "EMERGENCY_LANDING",
  "actions": [
    { "type": "setSpeed", "targetSpeed": 12.0 },
    {
      "type": "directTo",
      "targetLLAs": [
        { "lat": 37.55490, "lon": 126.96995, "alt": 60.0, "targetSpeed": 12.0 }
      ]
    },
    {
      "type": "land",
      "targetLLA": { "lat": 37.55460, "lon": 126.96980, "alt": 0.0 }
    }
  ]
}
```

## 8. 유효성 정책

- 필수 필드 누락 → 오류 (`ok=false`)
- 타입 불일치 → 오류
- `timestamp` 형식 불일치 → 오류
- `aircraftId` 패턴 불일치 → 오류
- `actions` 길이 0 → 오류
- `directTo.targetLLAs` 길이 0 → 오류
- `targetLLAs` 각 원소에서 `lat`, `lon`, `alt`, `targetSpeed` 누락 → 오류
- `hold`에서 `turnDirection`, `holdingRadiusM`, `maxHoldingCount` 누락 → 오류
- `land`에서 `targetLLA`와 `vertiport` 모두 없으면 → 오류
- `rejoinPlan.atSeq` 1 미만 → 오류
- `commandId` 빈 문자열 → 오류
