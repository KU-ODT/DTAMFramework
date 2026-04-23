# ICD — Strategic Separation Command (MSG 3002)

| 항목 | 값 |
|---|---|
| Message ID | `3002` |
| Message Name | 전략 분리 명령 |
| 전송 방식 | UDP |
| 인코딩 | JSON (UTF-8) |
| 주기 | 이벤트성 |

## 1. 개요

3002는 기존 3001 정기편 정보를 수정하기 위한 전략적 명령 메시지이다.
이 메시지는 어떤 정기편을, 어떤 버전으로, 언제부터 유효하게 수정할 것인지 지정한다.
실제 수정 대상 seq, 경로 세부값, 자원 세부값은 별도 데이터 또는 참조 구조에서 관리한다.

## 2. 최상위 구조

```json
{
  "timestamp": "<ISO-8601 UTC>",
  "commandId": "<COMMAND_ID>",
  "flightPlanNumber": <int>,
  "planVersion": <int>,
  "aircraftId": "<AIRCRAFT_ID>",
  "modificationType": "<MODIFICATION_TYPE>",
  "reasonCode": "<REASON_CODE>",
  "modifyScope": "<MODIFY_SCOPE>"
}
```

## 3. 필드 정의

| 필드 | 타입 | 값/패턴 | 설명 |
|---|---|---|---|
| `timestamp` | str | `YYYY-MM-DDTHH:MM:SS.sssZ` | 3002 명령 생성 시각 (UTC) |
| `commandId` | str | 자유 형식 (예: `SMP-20260416-001`) | 수정 명령 자체의 고유 식별자 |
| `flightPlanNumber` | int | 1 ~ 9,999,999 | 수정 대상 3001 정기편 번호 |
| `planVersion` | int | 1 이상 | 수정 후 정기편 버전 번호 |
| `aircraftId` | str | `^[A-Z]{2,8}\d{4}$` | 수정 명령이 적용될 비행체 ID |
| `modificationType` | str | 아래 열거형 참조 | 수정 유형 |
| `reasonCode` | str | 아래 열거형 참조 | 수정 사유 코드 |
| `modifyScope` | str | 아래 열거형 참조 | 수정 범위 |

### 3.1 modificationType 열거형

| 값 | 설명 |
|---|---|
| `scheduleResourceUpdate` | 스케줄/자원 통합 변경 |
| `routeUpdate` | 경로 변경 |
| `aircraftSwap` | 비행체 교체 |
| `delayOnly` | 지연만 반영 |
| `cancelPlan` | 계획 취소 |

### 3.2 reasonCode 열거형

| 값 | 설명 |
|---|---|
| `VERTIPORT_CAPACITY` | 버티포트 용량 제한 |
| `CORRIDOR_CLOSED` | 회랑 폐쇄 |
| `WEATHER` | 기상 조건 |
| `VEHICLE_UNAVAILABLE` | 비행체 사용 불가 |
| `OPERATOR_REQUEST` | 운영자 요청 |

### 3.3 modifyScope 열거형

| 값 | 설명 |
|---|---|
| `departureOnly` | 출발만 |
| `arrivalOnly` | 도착만 |
| `departureAndArrival` | 출발 + 도착 |
| `enRouteOnly` | 비행 경로만 |
| `aircraftOnly` | 비행체만 |
| `fullPlan` | 전체 계획 |

## 4. 예시

```json
{
  "timestamp": "2026-04-16T08:41:00.000Z",
  "commandId": "SMP-20260416-001",
  "flightPlanNumber": 1201,
  "planVersion": 2,
  "aircraftId": "UAM0001",
  "modificationType": "scheduleResourceUpdate",
  "reasonCode": "VERTIPORT_CAPACITY",
  "modifyScope": "departureAndArrival"
}
```

## 5. 유효성 정책

- 필수 필드 누락 → 오류 (`ok=false`)
- 타입 불일치 → 오류
- `timestamp` 형식 불일치 → 오류
- `flightPlanNumber` 범위(1~9,999,999) 이탈 → 오류
- `planVersion` 1 미만 → 오류
- `aircraftId` 패턴 불일치 → 오류
- `modificationType`, `reasonCode`, `modifyScope` 허용 목록 외 → 오류
- `commandId` 빈 문자열 → 오류

## 6. 운용 메모

- 3002는 "무엇을 수정할지 식별하는 명령 헤더"로 사용한다.
- 실제 수정 상세값은 별도 데이터에서 참조한다.
- `planVersion`이 증가하면 DB에서 최신 버전만 active로 두고, 이전 버전은 inactive 또는 superseded 처리하는 방식이 적절하다.
